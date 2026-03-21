from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable
from uuid import UUID

from v4.commands import (
    Callbacks,
    Conditions,
    FailureSideEffects,
    NextTransition,
    Permissions,
    SideEffects,
)
from v4.context import ExecutionMode, TransitionContext
from v4.exceptions import DjangoLogicException, StateLocked
from v4.state import State

logger = logging.getLogger('django-logic.transition')


class BaseTransition(ABC):
    action_name: str
    sources: list[str]
    permissions: Permissions
    conditions: Conditions

    def is_valid(self, state: State, user: object | None = None) -> bool:
        try:
            ctx = TransitionContext(user=user)
            self.permissions.execute(state, ctx)
            self.conditions.execute(state, ctx)
            return True
        except DjangoLogicException:
            return False

    @abstractmethod
    def change_state(self, state: State, ctx: TransitionContext) -> UUID | None: ...


class Transition(BaseTransition):
    """State transition: sources -> (in_progress) -> target | failed.

    ``change_state`` is the single orchestrator:
    lock -> in_progress -> side_effects -> complete / fail.
    """

    def __init__(
        self,
        action_name: str,
        sources: list[str],
        target: str,
        *,
        in_progress_state: str | None = None,
        failed_state: str | None = None,
        permissions: list[Callable] | None = None,
        conditions: list[Callable] | None = None,
        side_effects: list[Callable] | None = None,
        callbacks: list[Callable] | None = None,
        failure_callbacks: list[Callable] | None = None,
        failure_side_effects: list[Callable] | None = None,
        next_transition: str | None = None,
    ) -> None:
        self.action_name = action_name
        self.sources = sources
        self.target = target
        self.in_progress_state = in_progress_state
        self.failed_state = failed_state

        self.permissions = Permissions(permissions)
        self.conditions = Conditions(conditions)
        self.side_effects = SideEffects(side_effects)
        self.callbacks = Callbacks(callbacks)
        self.failure_callbacks = Callbacks(failure_callbacks)
        self.failure_side_effects = FailureSideEffects(failure_side_effects)
        self.next_transition = NextTransition(next_transition)

    def __repr__(self) -> str:
        return f'Transition({self.action_name}: {self.sources} -> {self.target})'

    # -- main flow (single orchestrator) ---------------------------------------

    def change_state(self, state: State, ctx: TransitionContext) -> UUID | None:
        logger.info(
            '%s Start %s %s %s (root=%s parent=%s)',
            ctx.tr_id, ctx.process_class.split('.')[-1] if ctx.process_class else '',
            self.action_name, state.instance_key, ctx.root_id, ctx.parent_id,
        )

        if ctx.execution_mode == ExecutionMode.BACKGROUND_EXECUTE and ctx.is_root:
            if not state.is_locked():
                raise StateLocked(
                    f'{state.instance_key} lock expired before background execution'
                )
            self._run_side_effects(state, ctx)
        elif ctx.execution_mode == ExecutionMode.BACKGROUND_DISPATCH and ctx.is_root:
            self._acquire_lock(state, ctx)
            self._set_in_progress(state, ctx)
            self.run_in_background(state, ctx)
        else:
            self._acquire_lock(state, ctx)
            self._set_in_progress(state, ctx)
            self._run_side_effects(state, ctx)

        return ctx.tr_id

    def _acquire_lock(self, state: State, ctx: TransitionContext) -> None:
        if not state.lock():
            raise StateLocked(f'{state.instance_key} is locked')
        logger.info('%s Lock', ctx.tr_id)

    def _set_in_progress(self, state: State, ctx: TransitionContext) -> None:
        if self.in_progress_state:
            state.set_state(self.in_progress_state)
            logger.info('%s SetState %s', ctx.tr_id, self.in_progress_state)

    def _run_side_effects(self, state: State, ctx: TransitionContext) -> None:
        try:
            self.side_effects.execute(state, ctx)
            self.complete_transition(state, ctx)
        except Exception as exc:
            logger.error(
                '%s SideEffect failed: %s: %s',
                ctx.tr_id, type(exc).__name__, exc,
                exc_info=True,
            )
            self.fail_transition(state, exc, ctx)
            raise

    # -- completion / failure --------------------------------------------------

    def complete_transition(self, state: State, ctx: TransitionContext) -> None:
        state.set_state(self.target)
        logger.info('%s SetState %s', ctx.tr_id, self.target)

        state.unlock()
        logger.info('%s Unlock', ctx.tr_id)

        self.callbacks.execute(state, ctx)
        self.next_transition.execute(state, ctx)

    def fail_transition(self, state: State, exc: Exception, ctx: TransitionContext) -> None:
        if self.failed_state:
            state.set_state(self.failed_state)
            logger.info('%s SetState %s', ctx.tr_id, self.failed_state)

        self.failure_side_effects.execute(state, ctx, exception=exc)

        state.unlock()
        logger.info('%s Unlock', ctx.tr_id)

        self.failure_callbacks.execute(state, ctx)

    # -- background hook (override in CeleryTransition, etc.) ------------------

    def run_in_background(self, state: State, ctx: TransitionContext) -> None:
        raise NotImplementedError(
            'Override run_in_background or use ExecutionMode.SYNC'
        )


class Action(BaseTransition):
    """Runs side-effects without changing state.

    No lock, no in_progress, no state transition.
    Supports ``failed_state`` for error scenarios.
    """

    def __init__(
        self,
        action_name: str,
        sources: list[str],
        *,
        failed_state: str | None = None,
        permissions: list[Callable] | None = None,
        conditions: list[Callable] | None = None,
        side_effects: list[Callable] | None = None,
        callbacks: list[Callable] | None = None,
        failure_callbacks: list[Callable] | None = None,
        failure_side_effects: list[Callable] | None = None,
    ) -> None:
        self.action_name = action_name
        self.sources = sources
        self.failed_state = failed_state

        self.permissions = Permissions(permissions)
        self.conditions = Conditions(conditions)
        self.side_effects = SideEffects(side_effects)
        self.callbacks = Callbacks(callbacks)
        self.failure_callbacks = Callbacks(failure_callbacks)
        self.failure_side_effects = FailureSideEffects(failure_side_effects)

    def __repr__(self) -> str:
        return f'Action({self.action_name})'

    def change_state(self, state: State, ctx: TransitionContext) -> UUID | None:
        try:
            self.side_effects.execute(state, ctx)
            self.callbacks.execute(state, ctx)
        except Exception as exc:
            logger.error(
                '%s Action %s failed: %s: %s',
                ctx.tr_id, self.action_name, type(exc).__name__, exc,
                exc_info=True,
            )
            if self.failed_state:
                state.set_state(self.failed_state)
            self.failure_side_effects.execute(state, ctx, exception=exc)
            self.failure_callbacks.execute(state, ctx)
            raise
        return ctx.tr_id
