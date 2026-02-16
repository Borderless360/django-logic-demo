from celery import shared_task

from django_logic.utils import get_process_and_state, restore_user_object


def _get_transition_by_action(process, action_name: str, state):
    """
    Find the transition by action_name. If multiple transitions share the same
    action_name (e.g. different conditions), pick the one whose in_progress_state
    matches the current state (the one we're continuing in phase 2).
    """
    candidates = [t for t in process.transitions if t.action_name == action_name]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Multiple transitions with same action_name: use the one we're in progress for
    return next(
        (t for t in candidates if t.in_progress_state == state.cached_state),
        candidates[0],
    )


@shared_task(acks_late=True)
def run_transition_in_background(**kwargs):
    """
    Restore the object, find the transition by action_name, and run it directly
    with background_mode_phase_2 (no lock, run side effects).
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
    transition = _get_transition_by_action(process, kwargs['action_name'], state)
    if transition is None:
        raise ValueError(
            f"No transition found for action_name={kwargs['action_name']!r} "
            f"in process {process.process_name!r}"
        )
    kwargs['background_mode_phase_2'] = True
    transition.change_state(state, **kwargs)