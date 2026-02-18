from django.utils import timezone
from django_logic.utils import restore_action
from django_logic.exceptions import TransitionNotAllowed

from django_logic_ext.models import TransitionMessage
from django_logic.utils import restore_user_object



class TransitionMessageHandler:
    """ Class that handles transition messages. """
    message: TransitionMessage = None

    def __init__(self, message: TransitionMessage):
        self.message = message

    def handle_message(self, logger=None):

        restore_user_object(self.message.kwargs)
        try:
            process, action = restore_action(
                app_label=self.message.app_label,
                model_name=self.message.model_name,
                instance_id=self.message.instance_id,
                field_name=self.message.field_name,
                process_class=self.message.process_class,
                action_name=self.message.transition_name,
                user=self.message.kwargs.get('user'),
            )
        except TransitionNotAllowed as e:
            self.message.mark_as_completed()
            return

        action.transition_message = self.message
        try:
            self.message.kwargs['background_mode_phase_2'] = True
            action.change_state(process.state, **self.message.kwargs)
        except Exception as e:
            self.message.errors_count += 1
            self.message.last_error_message = str(e)
            self.message.last_error_dt = timezone.now()
            self.message.save(update_fields=['errors_count', 'last_error_message', 'last_error_dt'])
            if logger:
                logger.error(f'Failed to run side effects for {self.message}: {e}')
        else:
            self.message.mark_as_completed()

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
