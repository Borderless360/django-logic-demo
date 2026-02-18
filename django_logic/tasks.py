from celery import shared_task
from django_logic.logger import transition_logger, TransitionEventType
from django_logic.utils import restore_user_object, restore_action


@shared_task(acks_late=True)
def run_transition_in_background(**kwargs):
    """
    Restore the object, find the transition by action_name, and run it directly
    with background_mode_phase_2 (no lock, run side effects).
    """
    restore_user_object(kwargs)
    process, transition = restore_action(
        app_label=kwargs['app_label'],
        model_name=kwargs['model_name'],
        instance_id=kwargs['instance_id'],
        field_name=kwargs.get('field_name', 'status'),
        process_class=kwargs.get('process_class'),
        action_name=kwargs['action_name'],
        user=kwargs.get('user'),
    )
    kwargs['background_mode_phase_2'] = True
    transition.change_state(process.state, **kwargs)
