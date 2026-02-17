from celery import shared_task

from django_logic.logger import transition_logger, TransitionEventType
from django_logic.utils import get_process_and_state, restore_user_object


def _get_transition_by_action(process, action_name: str, state, target=None):
    """
    Find the transition by action_name. If multiple transitions share the same
    action_name (e.g. branching by permissions), use the target state passed from
    the caller (phase 1) to pick the same transition in the worker (phase 2).
    Otherwise fall back to in_progress_state match, then first candidate.
    """
    candidates = [t for t in process.transitions if t.action_name == action_name]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if target is not None:
        match = next((t for t in candidates if t.target == target), None)
        if match is not None:
            return match
    # Multiple transitions with same action_name: use the one we're in progress for
    return next(
        (t for t in candidates if t.in_progress_state == state.cached_state),
        candidates[0],
    )


def restore_transition(app_label, model_name, instance_id, field_name, process_name, process_class, action_name):
    process, state = get_process_and_state(
        app_label=app_label,
        model_name=model_name,
        instance_id=instance_id,
        process_name=process_name,
        process_class=process_class,
        field_name=field_name,
    )
    transition = None 
    return transition, state

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
    transition = _get_transition_by_action(
        process, kwargs['action_name'], state, target=kwargs.get('target')
    )
    if transition is None:
        raise ValueError(
            f"No transition found for action_name={kwargs['action_name']!r} "
            f"in process {process.process_name!r}"
        )
    kwargs['background_mode_phase_2'] = True
    tr_id = kwargs.get('tr_id')
    try:
        transition.change_state(state, **kwargs)
    except Exception as e:
        transition_logger.error(
            f"{tr_id} {TransitionEventType.FAIL.value}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        raise