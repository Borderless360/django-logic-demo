from django_logic import Process, Transition, Action, ProcessManager
from .models import A, B, C, A_STATES, B_STATES, C_STATES
from .side_effects import run_process_B, fail, save_error_code, fail_always


class AProcess(Process):
    # permissions = [is_user]
    transitions = [
        # Multiple ways from A0
        Transition(action_name='A0_A1', sources=[A_STATES.A0], target=A_STATES.A1),
        Transition(action_name='A0_A2', sources=[A_STATES.A0], target=A_STATES.A2),
        Transition(action_name='A0_A3', sources=[A_STATES.A0], target=A_STATES.A3,
            side_effects=[run_process_B],
        ),
        # Multiple sources to reach A4
        Transition(action_name='to_A4', sources=[A_STATES.A1, A_STATES.A2, A_STATES.A3], target=A_STATES.A4),
        # Different ways to reach A5 from one source
        Transition(action_name='A4_A5_1', sources=[A_STATES.A4], target=A_STATES.A5),
        Transition(action_name='A4_A5_2', sources=[A_STATES.A4], target=A_STATES.A5),
    ]
ProcessManager.bind_model_process(A, AProcess, 'status')


class BProcess(Process):
    transitions = [
        Transition(action_name='B0_B1', sources=[B_STATES.B0], target=B_STATES.B1, failed_state=B_STATES.Err),
        Transition(action_name='B1_B2', sources=[B_STATES.B1], target=B_STATES.B2, failed_state=B_STATES.Err,
            side_effects=[fail],
            failure_callbacks=[save_error_code, fail_always],
        ),
        Transition(action_name='fix_B0', sources=[B_STATES.Err, B_STATES.B0], target=B_STATES.B0),
        Transition(action_name='fix_B1', sources=[B_STATES.Err, B_STATES.B1], target=B_STATES.B1),
    ]
ProcessManager.bind_model_process(B, BProcess, 'status')

# failure_callbacks=[
#                 actions.fail_tech_issue_handler_3pl,
#             ]

class CProcess(Process):
    transitions = [
        Transition(action_name='C0_C1', sources=[C_STATES.C0], target=C_STATES.C1),
        Transition(action_name='C1_C2', sources=[C_STATES.C1], target=C_STATES.C2),
        # Last state can be crashed if ... ?
        Transition(action_name='C2_C3', sources=[C_STATES.C2], target=C_STATES.C3),
    ]
ProcessManager.bind_model_process(C, CProcess, 'status')