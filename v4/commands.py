from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from v4.exceptions import ConditionNotMet, PermissionDenied

if TYPE_CHECKING:
    from v4.context import TransitionContext
    from v4.state import State

logger = logging.getLogger('django-logic.transition')


class Conditions:
    """Each function receives ``(instance, ctx=ctx)`` and must return True."""

    def __init__(self, commands: list[Callable] | None = None) -> None:
        self._commands = commands or []

    def execute(self, state: State, ctx: TransitionContext) -> None:
        for fn in self._commands:
            if not fn(state.instance, ctx=ctx):
                raise ConditionNotMet(
                    f"Condition {fn.__name__} not met for {state.instance}"
                )


class Permissions:
    """Strict: user is required when permission functions exist.

    Each function receives ``(instance, user, ctx=ctx)`` and must return True.
    """

    def __init__(self, commands: list[Callable] | None = None) -> None:
        self._commands = commands or []

    def execute(self, state: State, ctx: TransitionContext) -> None:
        if not self._commands:
            return
        if ctx.user is None:
            raise PermissionDenied("User is required for this transition")
        for fn in self._commands:
            if not fn(state.instance, ctx.user, ctx=ctx):
                raise PermissionDenied(
                    f"Permission {fn.__name__} denied for user {ctx.user}"
                )


class SideEffects:
    """Runs side-effect functions sequentially: ``fn(instance, ctx=ctx)``.

    Only runs the functions — orchestration (complete/fail) stays in Transition.
    """

    def __init__(self, commands: list[Callable] | None = None) -> None:
        self._commands = commands or []

    def execute(self, state: State, ctx: TransitionContext) -> None:
        for fn in self._commands:
            logger.info('%s SideEffect %s', ctx.tr_id, fn.__name__)
            fn(state.instance, ctx=ctx)


class FailureSideEffects:
    """Run after side-effects fail, before state is unlocked.

    Errors are logged but do not propagate.
    """

    def __init__(self, commands: list[Callable] | None = None) -> None:
        self._commands = commands or []

    def execute(self, state: State, ctx: TransitionContext, exception: Exception | None = None) -> None:
        for fn in self._commands:
            try:
                logger.info('%s FailureSideEffect %s', ctx.tr_id, fn.__name__)
                fn(state.instance, ctx=ctx, exception=exception)
            except Exception as exc:
                logger.error(
                    '%s FailureSideEffect %s failed: %s',
                    ctx.tr_id, fn.__name__, exc,
                    exc_info=True,
                )


class Callbacks:
    """Post-transition callbacks. Errors are logged but do not propagate."""

    def __init__(self, commands: list[Callable] | None = None) -> None:
        self._commands = commands or []

    def execute(self, state: State, ctx: TransitionContext) -> None:
        for fn in self._commands:
            try:
                logger.info('%s Callback %s', ctx.tr_id, fn.__name__)
                fn(state.instance, ctx=ctx)
            except Exception as exc:
                logger.error(
                    '%s Callback %s failed: %s',
                    ctx.tr_id, fn.__name__, exc,
                    exc_info=True,
                )


class NextTransition:
    """Triggers the next transition after the current one completes.

    Delegates to ``process.run()`` so that resolution and ambiguity
    checks are applied consistently.
    """

    def __init__(self, next_transition: str | None = None) -> None:
        self._next_transition = next_transition

    def execute(self, state: State, ctx: TransitionContext) -> None:
        if not self._next_transition:
            return

        if not state.process_name:
            logger.warning(
                '%s NextTransition skipped: process_name not set on State',
                ctx.tr_id,
            )
            return

        process = getattr(state.instance, state.process_name)
        process.run(self._next_transition, ctx=ctx.child())
