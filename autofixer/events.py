"""Parse django-logic transition log events from message strings."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class LogEvent:
    """Parsed log event from django-logic transition logger."""

    tr_id: str
    event_type: str  # Start, Set State, Lock, Unlock, Fail, SideEffect, etc.
    raw_message: str
    timestamp: Optional[datetime] = None
    # Start-specific
    process_class: Optional[str] = None
    action_name: Optional[str] = None
    instance_key: Optional[str] = None
    root_id: Optional[str] = None
    parent_id: Optional[str] = None
    # Set State-specific
    state: Optional[str] = None
    # Fail-specific
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_start(self) -> bool:
        return self.event_type == "Start"

    @property
    def is_complete(self) -> bool:
        """Transition finished: Unlock (success) or Fail (error)."""
        return self.event_type in ("Unlock", "Fail")

    @property
    def is_failure(self) -> bool:
        return self.event_type == "Fail"


# Patterns for django-logic log messages (message LIKE '{tr_id} %')
# Start: {tr_id} Start {process_class} {action_name} {instance_key} {root_id} {parent_id}
# Unlock: {tr_id} Unlock
# Fail: {tr_id} Fail: {ExceptionType}: {message}
# Set State: {tr_id} Set State {state}
# SideEffect: {tr_id} SideEffect {function_name}
# etc.

START_RE = re.compile(
    r"^([a-f0-9-]{36})\s+Start\s+(\S+)\s+(\S+)\s+(\S+)\s+([a-f0-9-]{36}|None)\s+([a-f0-9-]{36}|None)\s*$",
    re.IGNORECASE,
)
UNLOCK_RE = re.compile(r"^([a-f0-9-]{36})\s+Unlock\s*$", re.IGNORECASE)
FAIL_RE = re.compile(
    r"^([a-f0-9-]{36})\s+Fail:\s+(.+?):\s+(.*)$",
    re.DOTALL,
)
SET_STATE_RE = re.compile(
    r"^([a-f0-9-]{36})\s+Set State\s+(.+?)\s*$",
)


def parse_event(message: str, timestamp: Optional[datetime] = None) -> Optional[LogEvent]:
    """Parse a log message into a LogEvent, or None if not a transition log."""
    if not message or not message.strip():
        return None

    parts = message.split(None, 2)
    if len(parts) < 2:
        return None

    tr_id, suffix = parts[0], (parts[2] if len(parts) > 2 else "")

    # Validate tr_id looks like UUID
    try:
        UUID(tr_id)
    except (ValueError, TypeError):
        return None

    # Start
    m = START_RE.match(message)
    if m:
        return LogEvent(
            tr_id=m.group(1),
            event_type="Start",
            raw_message=message,
            timestamp=timestamp,
            process_class=m.group(2),
            action_name=m.group(3),
            instance_key=m.group(4),
            root_id=m.group(5) if m.group(5) != "None" else None,
            parent_id=m.group(6) if m.group(6) != "None" else None,
        )

    # Unlock
    m = UNLOCK_RE.match(message)
    if m:
        return LogEvent(
            tr_id=m.group(1),
            event_type="Unlock",
            raw_message=message,
            timestamp=timestamp,
        )

    # Fail
    m = FAIL_RE.match(message)
    if m:
        return LogEvent(
            tr_id=m.group(1),
            event_type="Fail",
            raw_message=message,
            timestamp=timestamp,
            error_type=m.group(2).strip(),
            error_message=m.group(3).strip() if len(m.group(3)) else "",
        )

    # Set State
    m = SET_STATE_RE.match(message)
    if m:
        return LogEvent(
            tr_id=m.group(1),
            event_type="Set State",
            raw_message=message,
            timestamp=timestamp,
            state=m.group(2).strip(),
        )

    # Generic: tr_id + event_type (Lock, SideEffect, Callback, etc.)
    event_type = parts[1] if len(parts) >= 2 else ""
    if event_type in ("Lock", "SideEffect", "Callback", "FailureSideEffect", "Background Mode", "Next Transition"):
        return LogEvent(
            tr_id=tr_id,
            event_type=event_type,
            raw_message=message,
            timestamp=timestamp,
        )

    return None
