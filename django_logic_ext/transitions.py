import logging
from importlib import import_module

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
    transition_message: TransitionMessage

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

    @staticmethod
    def _make_json_serializable(obj):
        """Convert non-JSON-serializable values (e.g. UUID) to JSON-serializable form."""
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, dict):
            return {k: MQTransition._make_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [MQTransition._make_json_serializable(v) for v in obj]
        return obj

    def _get_kwargs_without_non_serializable_objects(self, kwargs: dict) -> dict:
        """
        Removes non serializeable objects from kwargs and add user_id for logging in HistoryMixin.
        TODO: avoid using project specific code inside django_logic_ext
        """
        # make a copy of kwargs to avoid modifying the original dictionary
        kwargs = dict(kwargs)
        request = kwargs.get('request')
        if request:
            del kwargs['request']

        user = kwargs.get('user')
        if user:
            del kwargs['user']

        if request or user:
            if request:
                user = request.user
            kwargs['user_id'] = user.id

        return self._make_json_serializable(kwargs)

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

        self.transition_message = TransitionMessage.objects.create(
            **instance_lookup,
            transition_name=self.action_name,
            kwargs=kwargs
        )

    def mark_transition_message_with_errors_as_completed(self, state: State, **kwargs) -> int:
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

        def _change_state():
            with transaction.atomic():
                self.set_in_progress_state(state)
                self.create_transition_message(state, **kwargs)

        def _handle_unkown_error(e):
            logger.error(f'Failed to create TransitionMessage: {e}')
            raise e

        # main code of function
        try:
            _change_state()
        except IntegrityError:
            # try to complete existed message with max number of errors
            if not self.mark_transition_message_with_errors_as_completed(state, **kwargs):
                raise TransitionNotAllowed('Instance already is in progress.')

            # then try to create new message again
            try:
                _change_state()
            except Exception as e:
                _handle_unkown_error(e)
        except Exception as e:
            _handle_unkown_error(e)

    def complete_transition(self, state: State, **kwargs):
        if not AppConfig.get_setting('ENABLED'):
            super().complete_transition(state, **kwargs)
            return

        state.set_state(self.target)
        self.transition_message.mark_as_completed()

        log_data = state.get_log_data()
        log_data.update({'user': kwargs.get('user', None)})
        self.logger.info(f'{state.instance_key} state changed to {self.target}',
                        #  log_type=LogType.TRANSITION_COMPLETED,
                         log_data=log_data)

        self.callbacks.execute(state, **kwargs)
        self.next_transition.execute(state, **kwargs)

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
        if AppConfig.get_setting('ENABLED'):
            self.transition_message.mark_as_completed()

        self.callbacks.execute(state, **kwargs)
        self.next_transition.execute(state, **kwargs)

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
