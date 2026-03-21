from __future__ import annotations

import enum
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

_current_context: ContextVar[TransitionContext | None] = ContextVar(
    '_current_context', default=None,
)


class ExecutionMode(enum.Enum):
    SYNC = 'sync'
    BACKGROUND_DISPATCH = 'background_dispatch'
    BACKGROUND_EXECUTE = 'background_execute'


@dataclass
class TransitionContext:
    """Typed container that replaces the old **kwargs bag.

    Every piece of metadata that used to be passed implicitly through
    ``**kwargs`` now has an explicit, documented field.
    """

    tr_id: uuid.UUID = field(default_factory=uuid.uuid4)
    root_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None

    user: Any = None
    process_class: str = ''

    execution_mode: ExecutionMode = ExecutionMode.SYNC

    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.root_id is None:
            self.root_id = self.tr_id
        if self.parent_id is None:
            self.parent_id = self.tr_id

    @property
    def is_root(self) -> bool:
        return self.root_id == self.tr_id

    def child(self) -> TransitionContext:
        """Create a child context that inherits root_id and extra."""
        return TransitionContext(
            root_id=self.root_id,
            parent_id=self.tr_id,
            user=self.user,
            process_class=self.process_class,
            execution_mode=self.execution_mode,
            extra=dict(self.extra),
        )

    # -- context-var helpers ---------------------------------------------------

    def activate(self) -> Any:
        """Push this context onto the context-var stack; return a reset token."""
        return _current_context.set(self)

    @staticmethod
    def get_current() -> TransitionContext | None:
        return _current_context.get()

    @staticmethod
    def reset(token: Any) -> None:
        _current_context.reset(token)
