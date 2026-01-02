from abstract.models import STATES
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user, is_superuser
from abstract.logic.callbacks import save_error


def run_b_action(obj, *args, **kwargs):
    # obj should be an A instance, access obj.b to get the B instance
    from abstract.models import A
    if not isinstance(obj, A):
        raise ValueError(f"run_b_action expects an A instance, got {type(obj).__name__}")
    obj.refresh_from_db()
    # Use getattr with a default to safely check if 'b' exists and is not None
    b_instance = getattr(obj, 'b', None)
    if b_instance is None:
        raise ValueError(f"Object {obj} does not have a related 'b' object")
    process = BProcess(instance=b_instance)
    print(f"Running b action with args: {args} and kwargs: {kwargs}")
    print(f"Process available actions: {process.get_available_actions()}")
    # Remove process_class and other parent-specific kwargs to avoid passing them to nested transitions
    # The nested transition should determine its own process_class
    nested_kwargs = {k: v for k, v in kwargs.items() if k not in ('process_class', 'tr_id', 'root_id', 'parent_id')}
    process.go_to_B(**nested_kwargs)

def run_c_action(obj, *args, **kwargs):
    # obj should be a B instance, access obj.c to get the C instance
    from abstract.models import B
    if not isinstance(obj, B):
        raise ValueError(f"run_c_action expects a B instance, got {type(obj).__name__}")
    obj.refresh_from_db()
    # Use getattr with a default to safely check if 'c' exists and is not None
    c_instance = getattr(obj, 'c', None)
    if c_instance is None:
        raise ValueError(f"Object {obj} does not have a related 'c' object")
    process = CProcess(instance=c_instance)
    # Remove process_class and other parent-specific kwargs to avoid passing them to nested transitions
    # The nested transition should determine its own process_class
    nested_kwargs = {k: v for k, v in kwargs.items() if k not in ('process_class', 'tr_id', 'root_id', 'parent_id')}
    process.go_to_B(**nested_kwargs)

class AProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, 
            side_effects=[run_b_action], 
            failure_callbacks=[save_error]
        ),
    ]

class BProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, 
            side_effects=[run_c_action], 
            failure_callbacks=[save_error]
        ),
    ]

class CProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, 
            permissions=[is_user], 
        ),
        Transition('go_to_B', [STATES.A], STATES.B, 
            permissions=[is_superuser], 
            side_effects=[error_for_superuser], 
            failure_callbacks=[save_error]
        ),
    ]
