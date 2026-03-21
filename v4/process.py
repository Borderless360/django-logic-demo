from __future__ import annotations

import logging
from typing import Callable, Iterator, Sequence

from v4.commands import Conditions, Permissions
from v4.context import TransitionContext
from v4.exceptions import DjangoLogicException, TransitionNotAllowed
from v4.state import State
from v4.transition import BaseTransition

logger = logging.getLogger('django-logic.transition')


class Process:
    """Groups transitions & nested sub-processes for a model's state field."""

    nested_processes: Sequence[type[Process]] = ()
    transitions: Sequence[BaseTransition] = ()
    conditions: Sequence[Callable] = ()
    permissions: Sequence[Callable] = ()
    state_class = State
    process_name: str = 'process'
    queryset_name: str = 'objects'

    def __init__(
        self,
        field_name: str = '',
        instance: object | None = None,
        state: State | None = None,
    ) -> None:
        if state is not None:
            self.field_name = state.field_name
            self.instance = state.instance
            self.state = state
        elif field_name and instance is not None:
            self.field_name = field_name
            self.instance = instance
            self.state = self.state_class(
                instance=instance,
                field_name=field_name,
                process_name=self.process_name,
                queryset_name=self.queryset_name,
            )
        else:
            raise TypeError(
                'Process requires either (field_name + instance) or a State object'
            )

    # -- public API ------------------------------------------------------------

    def run(self, action_name: str, ctx: TransitionContext | None = None):
        """Execute a transition by name.

        Errors are **always** propagated to the caller.
        """
        if ctx is None:
            ctx = TransitionContext()

        if not ctx.process_class:
            ctx.process_class = f'{self.__class__.__module__}.{self.__class__.__name__}'

        transition = self._resolve_transition(action_name, ctx)

        token = ctx.activate()
        try:
            return transition.change_state(self.state, ctx)
        finally:
            TransitionContext.reset(token)

    # -- validation / introspection --------------------------------------------

    def is_valid(self, user: object | None = None) -> bool:
        ctx = TransitionContext(user=user)
        try:
            Permissions(self.permissions).execute(self.state, ctx)
            Conditions(self.conditions).execute(self.state, ctx)
            return True
        except DjangoLogicException:
            return False

    def get_available_actions(
        self,
        user: object | None = None,
        action_name: str | None = None,
    ) -> list[str]:
        return sorted({
            t.action_name
            for t in self.get_available_transitions(user, action_name)
        })

    def get_available_transitions(
        self,
        user: object | None = None,
        action_name: str | None = None,
        ignore_state: bool = False,
    ) -> Iterator[BaseTransition]:
        if not self.is_valid(user):
            return

        if not ignore_state and self.state.is_locked():
            return

        current = self.state.get_state()
        for transition in self.transitions:
            if action_name is not None and transition.action_name != action_name:
                continue
            if current in transition.sources and transition.is_valid(self.state, user):
                yield transition

        for sub_cls in self.nested_processes:
            sub = sub_cls(state=self.state)
            yield from sub.get_available_transitions(
                user=user, action_name=action_name, ignore_state=ignore_state,
            )

    # -- internals -------------------------------------------------------------

    def _resolve_transition(
        self, action_name: str, ctx: TransitionContext,
    ) -> BaseTransition:
        matches = list(self.get_available_transitions(
            action_name=action_name, user=ctx.user, ignore_state=True,
        ))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise TransitionNotAllowed(
                f'Ambiguous: {len(matches)} transitions match "{action_name}" '
                f'for {self.state.instance_key}'
            )
        raise TransitionNotAllowed(
            f'{self.__class__.__name__} has no transition "{action_name}" '
            f'for {self.state.instance_key} (user={ctx.user})'
        )


class ProcessManager:
    """Binds a Process class to a Django model as a property."""

    @classmethod
    def bind_model_process(
        cls,
        model: type,
        process_class: type[Process],
        state_field: str = 'state',
    ) -> None:
        def make_getter(field_name: str, proc_cls: type[Process]):
            return lambda self: proc_cls(field_name=field_name, instance=self)

        setattr(
            model,
            process_class.process_name,
            property(make_getter(state_field, process_class)),
        )
