from celery import shared_task
from django_logic.utils import restore_user_object, restore_action
from django_logic.process import _transition_context


@shared_task(acks_late=True)
def django_logic_background(**kwargs):
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
    # Phase 2 bypasses Process._get_transition_method, so _transition_context
    # is never set. Propagate it here so nested callbacks inherit root_id/parent_id.
    token = _transition_context.set({
        'root_id': kwargs.get('root_id'),
        'tr_id': kwargs.get('tr_id'),
    })
    try:
        transition.change_state(process.state, **kwargs)
    finally:
        _transition_context.reset(token)


@shared_task(acks_late=True)
def django_logic_defer(
    func_path: str,
    app_label: str,
    model_name: str,
    instance_id,
    context: dict,
):
    """Execute a callable deferred from a transition side effect (separate task)."""
    from django_logic.defer import execute_deferred

    execute_deferred(func_path, app_label, model_name, instance_id, context)
