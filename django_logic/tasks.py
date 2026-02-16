from celery import shared_task

from django_logic.utils import get_process_and_state, restore_user_object


@shared_task(acks_late=True)
def run_transition_in_background(**kwargs):
    """
    Restore the object and re-run the transition without background flag.
    """
    restore_user_object(kwargs)
    process, state = get_process_and_state(
        app_label=kwargs['app_label'],
        model_name=kwargs['model_name'],
        instance_id=kwargs['instance_id'],
        process_name=kwargs['process_name'],
        process_class=kwargs.get('process_class'),
        field_name=kwargs.get('field_name', 'status'),
    )
    del kwargs['background_mode']
    kwargs['background_mode_phase_2'] = True
    action_name = kwargs.pop('action_name')
    getattr(process, action_name)(**kwargs)
