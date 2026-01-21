from abstract.models import STATES
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user, is_superuser
from abstract.logic.callbacks import save_error


def run_b_action(obj, **kwargs):
    b_process = BProcess(instance=obj.b)
    b_process.go_to_B(**kwargs)  # kwargs is a context of the parent transition

def run_c_action(obj, **kwargs):
    c_process = CProcess(instance=obj.c)
    c_process.go_to_B(**kwargs)


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
