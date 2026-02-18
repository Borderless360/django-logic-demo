import logging
from uuid import UUID

from django.utils import timezone
from django_logic import Transition, SideEffects, Callbacks
from django_logic.state import State
from django_logic.transition import Transition

from django_logic_ext.apps import DjangoLogicExtAppConfig as AppConfig
from django_logic_ext.models import TransitionMessage

logger = logging.getLogger(__name__)


class MQTransition(Transition):
    """ Transition that implements message queue pattern for django_logic """
    transition_message: TransitionMessage

    def __init__(self, action_name: str, sources: list, target: str, queue_name: str = 'celery', **kwargs):
        self.queue_name = queue_name
        super().__init__(action_name=action_name, sources=sources, target=target, **kwargs)

    def __str__(self):
        return f"MQTransition: {self.action_name} to {self.target}"

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

    def change_state(self, state: State, **kwargs):
        """
        Change the state to the in-progress state.
        """
        kwargs.pop('background_mode', None)  # avoid duplicate kwarg when caller passes it
        return super().change_state(state, background_mode=True, **kwargs)

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
            field_name=state.field_name,
            process_class=kwargs.get('process_class'),
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

    def complete_transition(self, state: State, **kwargs):
        super().complete_transition(state, **kwargs)
        # nested transition have no transition_message
        transition_message = getattr(self, 'transition_message', None)
        if transition_message is not None:
            transition_message.mark_as_completed()


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
            transition_message = getattr(self, 'transition_message', None)
            if transition_message is not None:
                transition_message.mark_as_completed()

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
