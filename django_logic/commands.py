from django_logic.logger import transition_logger as logger, TransitionEventType
from django_logic.state import State
from django_logic.constants import LogType
from django_logic.logger import get_logger


class BaseCommand(object):
    """
    Implements pattern Command
    """
    def __init__(self, commands=None, transition=None):
        self._commands = commands or []
        self._transition = transition
        # DEPRECATED
        self.logger = get_logger(module_name=__name__)

    @property
    def commands(self):
        return self._commands

    def execute(self, *args, **kwargs):
        raise NotImplementedError


class Conditions(BaseCommand):
    def execute(self, state: State, **kwargs):
        """
        It checks every condition for the provided instance by executing every command
        :param state: State object
        :return: True or False
        """
        return all(command(state.instance, **kwargs) for command in self._commands)


class Permissions(BaseCommand):
    def execute(self, state: State, user: any, **kwargs):
        """
        It checks the permissions for the provided user and instance by executing evey command
        If user is None then permissions passed
        :param state: State object
        :param user: any or None
        :return: True or False
        """
        return user is None or all(command(state.instance,  user, **kwargs) for command in self._commands)


class SideEffects(BaseCommand):
    def execute(self, state: State, **kwargs):
        """Side-effects execution"""
        # DEPRECATED
        self.logger.info(f"{state.instance_key} side effects of '{self._transition.action_name}' started",
                         log_type=LogType.TRANSITION_DEBUG,
                         log_data=state.get_log_data())
        try:
            logger.info(f'{kwargs.get("tr_id")} SideEffects {len(self._commands)}')
            for command in self._commands:
                logger.info(
                    f'{kwargs.get("tr_id")} {TransitionEventType.SIDE_EFFECT.value} {command.__name__}'
                )
                command(state.instance, **kwargs)
        except Exception as error:
            # DEPRECATED
            self.logger.info(f"{state.instance_key} side effects of '{self._transition.action_name}' failed "
                             f"with {error}",
                             log_type=LogType.TRANSITION_DEBUG,
                             log_data=state.get_log_data())
            self.logger.error(error, log_type=LogType.TRANSITION_ERROR, log_data=state.get_log_data())

            logger.error(f'{kwargs.get("tr_id")} {error}')
            self._transition.fail_transition(state, error, **kwargs)
            raise  # Re-raise the exception to propagate to parent transitions
        else:
            # DEPRECATED
            self.logger.info(f"{state.instance_key} side-effects of '{self._transition.action_name}' succeeded",
                             log_type=LogType.TRANSITION_DEBUG,
                             log_data=state.get_log_data())
            self._transition.complete_transition(state, **kwargs)


class Callbacks(BaseCommand):
    def execute(self, state: State, **kwargs):
        """
        Callback execution method.
        It runs commands one by one, if any of them raises an exception
        it will stop execution and send a message to the logger.
        Please note, it doesn't run failure callbacks in case of exception.
        """
        try:
            logger.info(f'{kwargs.get("tr_id")} Callbacks {len(self._commands)}')
            for command in self.commands:
                logger.info(
                    f'{kwargs.get("tr_id")} {TransitionEventType.CALLBACK.value} {command.__name__}'
                )
                command(state.instance, **kwargs)
        except Exception as error:
            logger.error(error)
            # ignore any errors in callbacks


class FailureSideEffects(BaseCommand):
    def execute(self, state: State, **kwargs):
        """
        Failure side-effects execution method.
        Runs after side-effects fail and before the state is unlocked.
        If any command raises an exception it will stop execution and log the error.
        """
        try:
            logger.info(f'{kwargs.get("tr_id")} FailureSideEffects {len(self._commands)}')
            for command in self.commands:
                logger.info(
                    f'{kwargs.get("tr_id")} {TransitionEventType.FAILURE_SIDE_EFFECT.value} {command.__name__}'
                )
                command(state.instance, **kwargs)
        except Exception as error:
            # DEPRECATED
            self.logger.info(f"{state.instance_key} callbacks of '{self._transition.action_name}` failed with {error}",
                             log_type=LogType.TRANSITION_DEBUG,
                             log_data=state.get_log_data())
            self.logger.error(error, log_type=LogType.TRANSITION_ERROR, log_data=state.get_log_data())

            logger.error(error)
            # ignore any errors in failure side effects


class NextTransition(object):
    """
    Runs next transition if it is specified
    Note: we cannot use side-effect or callback to run next transition,
    because the next transition should be executed after state is unlocked in the same thread.
    Callbacks can be executed in another thread.
    """
    _next_transition: str

    def __init__(self, next_transition: str = None):
        self._next_transition = next_transition

    def execute(self, state: State, **kwargs):
        if not self._next_transition:
            return

        process = getattr(state.instance, state.process_name)
        transitions = list(process.get_available_transitions(action_name=self._next_transition,
                                                             user=kwargs.get('user', None)))
        if not transitions:
            return None

        transition = transitions[0]
        transition.change_state(state, **kwargs)
