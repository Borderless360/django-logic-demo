from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.conditions import is_user, is_superuser
from abstract.models import STATES
from abstract.logic.callbacks import save_error


# -- Instance-based conditions for conditional branching --

def is_special(instance, **kwargs):
    """Condition: instance name is 'special'."""
    return instance.name == 'special'


def is_not_special(instance, **kwargs):
    """Condition: instance name is NOT 'special'."""
    return instance.name != 'special'


# -- Callback helper to chain transitions within BranchProcess --

def run_action(action_name):
    def callback(obj, *args, **kwargs):
        process = BranchProcess(instance=obj)
        action_method = getattr(process, action_name)
        action_method(*args, **kwargs)
    return callback


# NOTE: don't declare process class in the test file,
# Pytest imports modules with short names, so the process class will not be found.
class BranchProcess(BaseProcess):
    transitions = [
        # ── Permission-based branch ──
        # Same action name, different targets selected by user type.
        Transition('go_next', [STATES.A], STATES.B, permissions=[is_user]),
        Transition('go_next', [STATES.A], STATES.C, permissions=[is_superuser]),

        # ── Convergence ──
        # Multiple source states converge to the same target.
        Transition('go_to_D', [STATES.B, STATES.C], STATES.D),

        # ── Condition-based branch ──
        # Same action name, different targets selected by instance data.
        Transition('conditional_go', [STATES.A], STATES.E, conditions=[is_special]),
        Transition('conditional_go', [STATES.A], STATES.F, conditions=[is_not_special]),

        # ── Branch + chain ──
        # Branch to B for regular user, then auto-continue to D via callback.
        Transition('go_and_chain', [STATES.A], STATES.B,
            permissions=[is_user],
            callbacks=[run_action('go_to_D')],
        ),
    ]
