from abstract.models import STATES
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user
from abstract.logic.callbacks import save_error


def run_action(action_name):
    def callback(obj, *args, **kwargs):
        process = ChainProcess(instance=obj)
        action_method = getattr(process, action_name)
        action_method(*args, **kwargs)
    return callback

class ChainProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, callbacks=[run_action('go_to_C')]),
        Transition('go_to_C', [STATES.B], STATES.C, callbacks=[run_action('go_to_D')], side_effects=[error_for_superuser], failure_callbacks=[save_error]), 
        Transition('go_to_D', [STATES.C], STATES.D, permissions=[is_user]),
    ]
