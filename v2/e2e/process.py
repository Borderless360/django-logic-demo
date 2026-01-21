from django_logic import Process
from core.logic.side_effects import do_something_a, do_something_b, do_something_c
from core.logic.conditions import is_staff, is_user
from abstract.models import A_STATES, B, B_STATES, C_STATES
from abstract.logic.side_effects import run_process_B, fail, save_error_code, fail_always
from typing import Final
from .locker import ModelState

"""
Action - is a main entity in the process.
Process - is a group of actions.

Request an action.
Run action.
Callbacks after action is done.

For an action we should be able to set place of execution.
    - for celery it should be a queue name


"""

class Order():
    state = 'test'

class OrderState(ModelState[Order]):
    FIELD_NAME: Final[str] = 'status'

class OrderStateProcess(Process[OrderState]):
    STATE_CLASS = OrderState

class AProcess(OrderStateProcess):
    CONDITIONS = [is_user]
    ACTIONS = {
        # Multiple ways from A0
        'A0_A1': {'sources': [A_STATES.A0], 'target': A_STATES.A1},
        'A0_A2': {'sources': [A_STATES.A0], 'target': A_STATES.A2},
        'A0_A3': {'sources': [A_STATES.A0], 'target': A_STATES.A3, 'steps': [run_process_B]},
        # Multiple sources to reach A4
        'to_A4': {'sources': [A_STATES.A1, A_STATES.A2, A_STATES.A3], 'target': A_STATES.A4},
        # Different ways to reach A5 from one source
        'A4_A5_1': {'sources': [A_STATES.A4], 'target': A_STATES.A5},
        'A4_A5_2': {'sources': [A_STATES.A4], 'target': A_STATES.A5},
        # Action 
        'Do something without change the state': {'sources': [A_STATES.A4]},
        # Async example
        'Async example': {'sources': [A_STATES.A4], 'target': A_STATES.A5,
            # Steps(do_something_a)
            # side_effects is steps before state was changed
            # callbacks is steps after state was changed
            'runner': CeleryRunner('celery_queue'),
        },
    }


def next_action(target: str):
    pass

B0_B1 = {
    'sources': [B_STATES.B0], 'target': B_STATES.B1, 
    'failed_state': B_STATES.Err, 
    'steps': [do_something_a, do_something_b, do_something_c],
    'on_success': [next_action('B1_B2')], 
}

class BProcess(OrderStateProcess):
    ACTIONS = {
        # Action can be without the process? Or should it be a separate process?
        'B0_B1': B0_B1,
        'B1_B2': {
            'sources': [B_STATES.B1], 'target': B_STATES.B2, 
            'failed_state': B_STATES.Err,
            'conditions': [is_staff], 
            'steps': [fail], 
            'on_success': [do_something_c],
            'on_failure': [save_error_code, fail_always], 
        },
        'fix_B0': {'sources': [B_STATES.Err, B_STATES.B0], 'target': B_STATES.B0},
        'fix_B1': {'sources': [B_STATES.Err, B_STATES.B1], 'target': B_STATES.B1},
    }

# Gather all processes into one process
class OrderAllProcesses(OrderStateProcess):
    CHILDREN: Final[list[OrderStateProcess]] = [
        AProcess,
        BProcess,
    ]

def ProcessDescriptor(process_class: type[OrderStateProcess]):
    pass

# Bind process to Order model
Order.process = ProcessDescriptor(OrderAllProcesses)

user = None
obj = Order()
#
process = OrderAllProcesses(obj)
process.A0_A1(user=user)
process.B0_B1(user=user)
# Alternative way to call action
obj.process.A0_A1(user=user)
obj.process.B0_B1(user=user)
