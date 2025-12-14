import os
from django.utils.module_loading import import_string
from django.conf import settings
from django_logic.transition import BaseTransition
from django_logic.state import State


class ProxyTransition(BaseTransition):
    """
    Proxy transition that mimics/replicates a transition from settings.
    All method calls and attribute access are delegated to the underlying transition
    instance loaded from settings.TRANSITIONS.
    """
    
    def __init__(self, action_name: str, sources: list, target: str, **kwargs):
        """
        Initialize the proxy transition by creating an instance of the transition
        class specified in settings.TRANSITIONS.
        
        :param action_name: callable action name which used in a process
        :param sources: a list of source states which could be triggered the transition from
        :param target: a state which will be set to, after the side-effects executed
        :param kwargs: additional keyword arguments passed to the underlying transition
        """
        transition_class = import_string(settings.TRANSITIONS)
        self.transition = transition_class(action_name, sources, target, **kwargs)
    
    def __getattr__(self, name):
        """
        Proxy attribute access to the underlying transition instance.
        This allows access to all attributes like action_name, target, sources, etc.
        """
        return getattr(self.transition, name)
    
    def is_valid(self, state: State, user=None) -> bool:
        """Proxy is_valid method to the underlying transition."""
        return self.transition.is_valid(state, user)

    def change_state(self, state: State, **kwargs):
        """Proxy change_state method to the underlying transition."""
        return self.transition.change_state(state, **kwargs)

    def complete_transition(self, state: State, **kwargs):
        """Proxy complete_transition method to the underlying transition."""
        return self.transition.complete_transition(state, **kwargs)

    def fail_transition(self, state: State, exception: Exception, **kwargs):
        """Proxy fail_transition method to the underlying transition."""
        return self.transition.fail_transition(state, exception, **kwargs)
    
    def __str__(self):
        """Proxy string representation to the underlying transition."""
        return str(self.transition)
    
    def __repr__(self):
        """Proxy representation to the underlying transition."""
        return repr(self.transition)


class ProxyAction(BaseTransition):
    """
    Proxy action that mimics/replicates an action from settings.
    All method calls and attribute access are delegated to the underlying action
    instance loaded from settings.ACTIONS (or default Action class).
    """
    
    def __init__(self, action_name: str, sources: list, **kwargs):
        """
        Initialize the proxy action by creating an instance of the action
        class specified in settings.ACTIONS (or default).
        
        :param action_name: callable action name which used in a process
        :param sources: a list of source states which could be triggered the action from
        :param kwargs: additional keyword arguments passed to the underlying action
        """
        action_class = import_string(settings.ACTIONS)
        self.action = action_class(action_name, sources, **kwargs)
    
    def __getattr__(self, name):
        """
        Proxy attribute access to the underlying action instance.
        This allows access to all attributes like action_name, sources, etc.
        """
        return getattr(self.action, name)
    
    def is_valid(self, state: State, user=None) -> bool:
        """Proxy is_valid method to the underlying action."""
        return self.action.is_valid(state, user)

    def change_state(self, state: State, **kwargs):
        """Proxy change_state method to the underlying action."""
        return self.action.change_state(state, **kwargs)

    def complete_transition(self, state: State, **kwargs):
        """Proxy complete_transition method to the underlying action."""
        return self.action.complete_transition(state, **kwargs)

    def fail_transition(self, state: State, exception: Exception, **kwargs):
        """Proxy fail_transition method to the underlying action."""
        return self.action.fail_transition(state, exception, **kwargs)
    
    def __str__(self):
        """Proxy string representation to the underlying action."""
        return str(self.action)
    
    def __repr__(self):
        """Proxy representation to the underlying action."""
        return repr(self.action)
