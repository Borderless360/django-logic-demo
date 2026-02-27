from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    START = "Start"
    UNLOCK = "Unlock"
    FAIL = "Fail"
    SIDE_EFFECT = "SideEffect"
    CALLBACK = "Callback"
    FAILURE_SIDE_EFFECT = "FailureSideEffect"
    SET_STATE = "Set State"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class TransitionEvent:
    tr_id: str
    event_type: EventType
    timestamp: datetime
    process_class: str = ""
    action_name: str = ""
    instance_key: str = ""
    root_id: str = ""
    parent_id: str = ""
    name: str = ""
    raw_message: str = ""


@dataclass(frozen=True)
class TransitionCompletion:
    tr_id: str
    root_id: str
    process_class: str
    action_name: str
    duration_seconds: float
    completed_at: datetime
    side_effect_durations: list[tuple[str, float]]


@dataclass(frozen=True)
class Anomaly:
    kind: str
    metric_key: str
    observed: float
    mean: float
    std_dev: float
    threshold: float
    fingerprint: str
    details: dict


def parse_log_row(row: dict) -> TransitionEvent | None:
    message = (row.get("message") or "").strip()
    if not message:
        return None

    tokens = message.split()
    if len(tokens) < 2:
        return None

    timestamp = row.get("_timestamp") or row.get("created")
    if timestamp is None:
        return None

    tr_id = tokens[0]
    second = tokens[1]
    event_type = _parse_event_type(tokens)
    event_name = ""
    process_class = ""
    action_name = ""
    instance_key = ""
    root_id = ""
    parent_id = ""

    if event_type == EventType.START and len(tokens) >= 7:
        process_class = tokens[2]
        action_name = tokens[3]
        instance_key = tokens[4]
        root_id = tokens[5]
        parent_id = tokens[6]
    elif event_type in (EventType.SIDE_EFFECT, EventType.CALLBACK, EventType.FAILURE_SIDE_EFFECT):
        if len(tokens) >= 3:
            event_name = tokens[2]
    elif event_type == EventType.SET_STATE and len(tokens) >= 4:
        event_name = " ".join(tokens[3:])
    elif event_type == EventType.FAIL:
        event_name = second.rstrip(":")

    return TransitionEvent(
        tr_id=tr_id,
        event_type=event_type,
        timestamp=timestamp,
        process_class=process_class,
        action_name=action_name,
        instance_key=instance_key,
        root_id=root_id,
        parent_id=parent_id,
        name=event_name,
        raw_message=message,
    )


def _parse_event_type(tokens: list[str]) -> EventType:
    if len(tokens) < 2:
        return EventType.UNKNOWN
    second = tokens[1]
    if second == "Start":
        return EventType.START
    if second == "Unlock":
        return EventType.UNLOCK
    if second.startswith("Fail"):
        return EventType.FAIL
    if second == "SideEffect":
        return EventType.SIDE_EFFECT
    if second == "Callback":
        return EventType.CALLBACK
    if second == "FailureSideEffect":
        return EventType.FAILURE_SIDE_EFFECT
    if len(tokens) > 2 and second == "Set" and tokens[2] == "State":
        return EventType.SET_STATE
    return EventType.UNKNOWN

