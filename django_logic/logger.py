import logging
from enum import Enum

# The main logger for logging all activity of django-logic.
logger: logging.Logger = logging.getLogger('django-logic')
# A special logger for logging only activity of transitions.
transition_logger: logging.Logger = logging.getLogger('django-logic.transition')

class TransitionEventType(Enum):
    START = 'Start'
    COMPLETE = 'Complete'
    FAIL = 'Fail'
    SIDE_EFFECT = 'SideEffect'
    CALLBACK = 'Callback'
    FAILURE_SIDE_EFFECT = 'FailureSideEffect'
    SET_STATE = 'Set State'
    LOCK = 'Lock'
    UNLOCK = 'Unlock'
    NEXT_TRANSITION = 'Next Transition'
