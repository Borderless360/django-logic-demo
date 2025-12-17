from typing import Optional

from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone

from django_logic_ext.models import TransitionMessage

User = get_user_model()


class TransitionMessageHandler:
    """ Class that handles transition messages. """
    message = None

    def __init__(self, message: TransitionMessage):
        self.message = message

    @classmethod
    def get_action_and_state_from_message(cls, message: TransitionMessage, user: Optional[User] = None):
        app = apps.get_app_config(message.app_label)
        model = app.get_model(message.model_name)

        try:
            instance = model.objects.get(id=message.instance_id)
        except model.DoesNotExist:
            return None, None

        process = getattr(instance, message.process_name)
        transitions = list(process.get_available_transitions(action_name=message.transition_name, user=user))
        if not transitions:
            return None, None

        return transitions[0], process.state

    def mark_as_complete(self):
        self.message.is_completed = True
        self.message.save(update_fields=['is_completed'])

    def handle_message(self, logger=None):
        """
        Runs side effects for a transition message.
        If side effects are failed, increments errors_count and saves error message.
        If side effects are successful, marks message as completed.
        Should be called inside atomic transaction.
        """
        kwargs = self.message.kwargs
        if user_id := kwargs.get('user_id'):
            kwargs['user'] = User.objects.get(id=user_id)
            del kwargs['user_id']

        action, state = self.get_action_and_state_from_message(self.message, user=kwargs.get('user'))
        if not action:
            self.mark_as_complete()
            return

        try:
            action.side_effects.execute(state, **kwargs)
        except Exception as e:
            self.message.errors_count += 1
            self.message.last_error_message = str(e)
            self.message.last_error_dt = timezone.now()
            self.message.save(update_fields=['errors_count', 'last_error_message', 'last_error_dt'])
            if logger:
                logger.error(f'Failed to run side effects for {self.message}: {e}')
        else:
            self.mark_as_complete()

    @classmethod
    def fetch_message(cls, transition_message_id: int) -> TransitionMessage:
        """
        Tries to fetch transition message and lock it for update.
        Should be called inside atomic transaction.
        :raises TransitionMessage.DoesNotExist: if message does not exist or already completed
        :raises OperationalError: if messaged already locked by another transaction
        """
        return TransitionMessage.objects\
            .select_for_update(nowait=True)\
            .get(id=transition_message_id, is_completed=False)
