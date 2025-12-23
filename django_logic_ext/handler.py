import importlib
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
    def get_process_instance(cls, instance, process_name, kwargs):
        """Get process instance from model or process_class in kwargs"""
        # First, try to get process from model attribute (if bound)
        try:
            return getattr(instance, process_name)
        except AttributeError:
            # Process is not bound to the model, try to use process_class from kwargs
            process_class = kwargs.get('process_class')
            field_name = kwargs.get('field_name', 'status')
            
            if process_class:
                try:
                    # Try to import and instantiate the process class
                    module_path, class_name = process_class.rsplit('.', 1)
                    module = importlib.import_module(module_path)
                    process_class_obj = getattr(module, class_name)
                    return process_class_obj(field_name=field_name, instance=instance)
                except (ImportError, AttributeError, ValueError) as e:
                    # If import fails, raise with helpful error message
                    raise AttributeError(
                        f"'{instance.__class__.__name__}' object has no attribute '{process_name}' "
                        f"and failed to import process_class '{process_class}': {e}"
                    )
            else:
                # No process_class provided and process is not bound
                raise AttributeError(
                    f"'{instance.__class__.__name__}' object has no attribute '{process_name}' "
                    f"and no process_class was provided in kwargs"
                )

    @classmethod
    def get_action_and_state_from_message(cls, message: TransitionMessage, user: Optional[User] = None):
        app = apps.get_app_config(message.app_label)
        model = app.get_model(message.model_name)

        try:
            instance = model.objects.get(id=message.instance_id)
        except model.DoesNotExist:
            return None, None

        # Get process instance, handling both bound and unbound cases
        kwargs = message.kwargs.copy()
        try:
            process = cls.get_process_instance(instance, message.process_name, kwargs)
        except AttributeError:
            return None, None

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
