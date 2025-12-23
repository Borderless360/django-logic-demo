import logging
from importlib import import_module
from uuid import UUID

from django.db import transaction, IntegrityError
from django.utils import timezone
from django_logic import Transition, SideEffects, Callbacks
from django_logic.exceptions import TransitionNotAllowed
from django_logic.state import State
from django_logic_celery import CeleryTransition, CallbacksSingleTask

from django_logic_ext.apps import DjangoLogicExtAppConfig as AppConfig
from django_logic_ext.models import TransitionMessage
from django_logic_ext.utils import extract_command_for_state

logger = logging.getLogger(__name__)


class MQSideEffects(SideEffects):
    """ Overrides base SideEffects to execute string commands as plain functions """

    def execute(self, state: State, **kwargs):
        """ Crash of one side effect should stop the execution of other side effects. """
        try:
            logging.info(f"{state.instance_key} side effects of '{self._transition.action_name}' started")
            for command in self.commands:
                if isinstance(command, str):
                    function, function_kwargs = extract_command_for_state(command, state, **kwargs)
                    function(**function_kwargs)
                else:
                    command(state.instance, **kwargs)
        except Exception as error:
            logging.info(f"{state.instance_key} side effects of '{self._transition.action_name}' failed with {error}")
            logging.exception(error)
            self._transition.fail_transition(state, error, **kwargs)
        else:
            logging.info(f"{state.instance_key} side-effects of '{self._transition.action_name}' succeeded")
            self._transition.complete_transition(state, **kwargs)


class MQCallbacks(Callbacks):
    """ Overrides base Callbacks to execute string commands as plain functions """

    def execute(self, state: State, **kwargs):
        """ Crash of one callback shouldn't stop the execution of other callbacks. """
        for command in self.commands:
            try:
                if isinstance(command, str):
                    function, function_kwargs = extract_command_for_state(command, state, **kwargs)
                    function(**function_kwargs)
                else:
                    command(state.instance, **kwargs)
            except Exception as error:
                logging.info(f"{state.instance_key} callback {command} of '{state.process_name}' failed with {error}")
                logging.exception(error)


class MQTransition(Transition):
    """ Transition that implements message queue pattern for django_logic """

    def __init__(self, action_name: str, sources: list, target: str, **kwargs):
        # use plain functions for side effects and callbacks
        # needed to be able to inherit in CeleryMQTransition, etc
        if AppConfig.get_setting('ENABLED'):
            self.side_effects_class = MQSideEffects
            self.callbacks_class = MQCallbacks
        super().__init__(action_name, sources, target, **kwargs)

        if AppConfig.get_setting('ENABLED'):
            if self.in_progress_state and self.in_progress_state not in self.sources:
                self.sources.append(self.in_progress_state)

    def __str__(self):
        return f"MQTransition: {self.action_name} to {self.target}"

    def is_valid(self, state: State, user=None) -> bool:
        if not AppConfig.get_setting('ENABLED'):
            return super().is_valid(state, user)
        return self.permissions.execute(state, user) and self.conditions.execute(state)

    def _get_kwargs_without_non_serializable_objects(self, kwargs: dict) -> dict:
        """
        Removes non serializeable objects from kwargs and add user_id for logging in HistoryMixin.
        Converts UUID objects to strings for JSON serialization.
        TODO: avoid using project specific code inside django_logic_ext
        """
        # from hijack_app.actions import get_actual_user_from_request

        # Make a copy to avoid mutating the original
        result = {}
        
        request = kwargs.get('request')
        user = kwargs.get('user')
        
        for key, value in kwargs.items():
            # Skip request and user objects
            if key in ('request', 'user'):
                continue
            
            # Convert UUID to string
            if isinstance(value, UUID):
                result[key] = str(value)
            else:
                result[key] = value

        if request or user:
            # if request:
            #     user = get_actual_user_from_request(request)
            if user:
                result['user_id'] = user.id

        return result

    @staticmethod
    def get_instance_lookup(state: State):
        return {
            'app_label': state.instance._meta.app_label,
            'model_name': state.instance._meta.model_name,
            'instance_id': state.instance.pk,
            'process_name': state.process_name,
        }

    def create_transition_message(self, state: State, **kwargs):
        """ Creates TransitionMessage instance based on state instance and provided kwargs """
        instance_lookup = self.get_instance_lookup(state)
        kwargs = self._get_kwargs_without_non_serializable_objects(kwargs)

        TransitionMessage.objects.create(
            **instance_lookup,
            transition_name=self.action_name,
            kwargs=kwargs
        )

    def complete_transition_message_with_errors(self, state: State, **kwargs) -> int:
        """ Marks uncompleted TransitionMessage instance with errors as completed """
        instance_lookup = self.get_instance_lookup(state)

        result = TransitionMessage.objects.filter(
            **instance_lookup,
            is_completed=False,
            errors_count=AppConfig.get_setting('MAX_ERRORS_COUNT')
        ).update(is_completed=True, modified=timezone.now())
        return result

    def change_state(self, state: State, **kwargs):
        """
        Sets in_progress_state and creates TransitionMessage instance.
        In case of failure, raises TransitionNotAllowed to
        If MQTransition is disabled, runs plain Transition change_state. It is not perfect switch,
        but better than nothing.
        """
        if not AppConfig.get_setting('ENABLED'):
            super().change_state(state, **kwargs)
            return

        # Lock state first (same as base Transition)
        from django_logic.logger import logger as transition_logger, TransitionEventType
        from django_logic.exceptions import TransitionNotAllowed
        extra = {
            'event_type': TransitionEventType.START.value,
            'action_name': self.action_name,
            'transition': self.action_name,
            'instance_pk': state.instance.pk,
        }
        extra.update(state.get_log_data())
        extra.update(kwargs)
        transition_logger.info(
            f'{kwargs.get("tr_id")} {TransitionEventType.START.value} {self.action_name} {state.instance.pk} {kwargs.get("root_id")} {kwargs.get("parent_id")}',
            extra=extra
        )
        try:
            if state.is_locked() or not state.lock():
                raise TransitionNotAllowed("State is locked")
        except TransitionNotAllowed as e:
            transition_logger.error(e, extra=kwargs)
            raise e
        
        # Log lock (same as base Transition)
        transition_logger.info(
            f'{kwargs.get("tr_id")} Lock',
            extra={
                'tr_id': kwargs.get('tr_id'), 
                'activity': TransitionEventType.LOCK.value, 
            }
        )

        def _change_state():
            with transaction.atomic():
                self.set_in_progress_state(state)
                self.create_transition_message(state, **kwargs)

        def _handle_unkown_error(e):
            logger.error(f'Failed to create TransitionMessage: {e}')
            raise TransitionNotAllowed('Temporary error: try again later.')

        # main code of function
        try:
            _change_state()
        except IntegrityError:
            # try to complete existed message with max number of errors
            if not self.complete_transition_message_with_errors(state, **kwargs):
                raise TransitionNotAllowed('Instance already is in progress.')

            # then try to create new message again
            try:
                _change_state()
            except Exception as e:
                _handle_unkown_error(e)
        except Exception as e:
            _handle_unkown_error(e)

    def fail_transition(self, state: State, exception: Exception, **kwargs):
        """ Handles transition failure but still raises exception """
        super().fail_transition(state, exception, **kwargs)
        if AppConfig.get_setting('ENABLED'):
            # raise exception to bubble up to handle_message and update TransitionMessage with errors
            raise exception

    def set_in_progress_state(self, state: State):
        if self.in_progress_state:
            state.set_state(self.in_progress_state)
            logger.info(f'{state.instance_key} state changed to {self.in_progress_state}')


class MQAction(MQTransition):
    """ Action that implements message queue pattern for django_logic """

    def __init__(self, action_name: str, sources: list, **kwargs):
        # use plain functions for side effects and callbacks
        if AppConfig.get_setting('ENABLED'):
            self.side_effects_class = SideEffects
            self.callbacks_class = Callbacks
        super().__init__(action_name=action_name, sources=sources, target='', **kwargs)

    def __str__(self):
        return f"MQAction: {self.action_name}"

    def complete_transition(self, state: State, **kwargs):
        """ Only apply callbacks, do not change state """
        self.callbacks.execute(state, **kwargs)

    def fail_transition(self, state: State, exception: Exception, **kwargs):
        """ Apply failure callbacks and raise exception """
        if self.failed_state:
            state.set_state(self.failed_state)
            logging.info(f'{state.instance_key} state changed to {self.failed_state}')

        self.failure_callbacks.execute(state, exception=exception, **kwargs)
        if AppConfig.get_setting('ENABLED'):
            # raise exception to bubble up to handle_message and update TransitionMessage with errors
            raise exception

    def set_in_progress_state(self, state: State):
        """ Skip for MQAction """
        pass
