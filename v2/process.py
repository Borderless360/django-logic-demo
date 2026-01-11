import uuid
from functools import partial
from django_logic.exceptions import TransitionNotAllowed
from django_logic.state import State
from abc import ABC


class Process[T](ABC):
    """ """

    STATE_CLASS = State
    ACTIONS = []
    NESTED_PROCESSES = []

    def __init__(self, instance=None):
        self.instance = instance
        self.state = self.STATE_CLASS(instance)

    def __getattr__(self, *args, **kwargs) -> callable:
        return partial(self._get_transition_method, *args, **kwargs)

    def _get_action_method(self, action_name: str, **kwargs):
        """
        It returns a callable transition method for the provided action name.
        """
        user = kwargs['user'] if 'user' in kwargs else None
        transitions = list(self.get_available_transitions(action_name=action_name, user=user))

        if len(transitions) == 1:
            transition = transitions[0]

            tr_id = uuid.uuid4()
            kwargs['root_id'] = kwargs.get('root_id', tr_id)
            kwargs['parent_id'] = kwargs.get('tr_id', tr_id)
            kwargs['tr_id'] = tr_id
            # Pass process class for cases where process is not bound to model
            if 'process_class' not in kwargs:
                process_class = f"{self.__class__.__module__}.{self.__class__.__name__}"
                kwargs['process_class'] = process_class
            return transition.change_state(self.state, **kwargs)

        elif len(transitions) > 1:
            raise TransitionNotAllowed("There are several transitions available")

        raise TransitionNotAllowed(f"Process class {self.__class__} for object {self.instance.id} has no transition "
                                   f"with action name {action_name}, user {user}")

    def is_valid(self, user=None) -> bool:
        conditions = self.conditions_class(commands=self.conditions)
        return conditions.execute(self.state))

    @property
    def available_actions(self, *args, **kwargs) -> set[str]:
        """ It returns all available actions which meet conditions.
        Including nested processes.
        """
        result = set()
        # return set([transition.action_name for transition in
        #             self.get_available_transitions(user, action_name)])
        for condition in self.conditions:
            if not condition(self.instance, *args, **kwargs):
                return result

        if self.state.is_locked:
            return result

        state = self.state.get()
        for action in self.ACTIONS:
            if state in action['sources']:
                result.add(action.name)

        for process in self.NESTED_PROCESSES:
            sub_process = process(state=self.state)
            result.update(sub_process.available_actions(*args, **kwargs))

        return result

