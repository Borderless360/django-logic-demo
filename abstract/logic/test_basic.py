from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser, short_action
from abstract.models import STATES
from abstract.logic.callbacks import save_error

# NOTE: don't declar process class in the test file,
# Pytest imports modules with short names, so the process class will not be found.
class BasicProcess(BaseProcess):
    transitions = [
        Transition(
            action_name='go_to_B', sources=[STATES.A], target=STATES.B,
            side_effects=[error_for_superuser],
            failure_side_effects=[save_error],
        ),
        Transition(
            action_name='fail_callback', sources=[STATES.A], target=STATES.B,
            callbacks=[error_for_superuser, short_action],
        ),
    ]
