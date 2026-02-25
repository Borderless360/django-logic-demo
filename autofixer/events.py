import re
from dataclasses import dataclass, field
from datetime import datetime

UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


@dataclass
class TransitionEvent:
    tr_id: str
    event_type: str
    timestamp: datetime
    process_class: str | None = None
    action_name: str | None = None
    instance_key: str | None = None
    root_id: str | None = None
    parent_id: str | None = None
    state: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    command_name: str | None = None
    command_count: int | None = None
    raw_message: str = ''


PATTERNS = [
    # START: {tr_id} Start {process_class} {action_name} {instance_key} {root_id} {parent_id}
    (
        re.compile(
            rf'^(?P<tr_id>{UUID_PATTERN})\s+Start\s+'
            rf'(?P<process_class>\S+)\s+(?P<action_name>\S+)\s+'
            rf'(?P<instance_key>\S+)\s+(?P<root_id>{UUID_PATTERN})\s+(?P<parent_id>{UUID_PATTERN})$'
        ),
        'START',
    ),
    # FAIL: {tr_id} Fail: {ExceptionType}: {message}
    (
        re.compile(
            rf'^(?P<tr_id>{UUID_PATTERN})\s+Fail:\s+(?P<error_type>\w+):\s+(?P<error_message>.+)$'
        ),
        'FAIL',
    ),
    # SET_STATE: {tr_id} Set State {state}
    (
        re.compile(rf'^(?P<tr_id>{UUID_PATTERN})\s+Set State\s+(?P<state>\S+)$'),
        'SET_STATE',
    ),
    # LOCK / UNLOCK / BACKGROUND_MODE (simple single-keyword events)
    (re.compile(rf'^(?P<tr_id>{UUID_PATTERN})\s+Lock$'), 'LOCK'),
    (re.compile(rf'^(?P<tr_id>{UUID_PATTERN})\s+Unlock$'), 'UNLOCK'),
    (re.compile(rf'^(?P<tr_id>{UUID_PATTERN})\s+Background Mode$'), 'BACKGROUND_MODE'),
    # Command groups with count: SideEffects / Callbacks / FailureSideEffects
    (
        re.compile(
            rf'^(?P<tr_id>{UUID_PATTERN})\s+(?P<group>SideEffects|Callbacks|FailureSideEffects)\s+(?P<command_count>\d+)$'
        ),
        'COMMAND_GROUP',
    ),
    # Individual commands: SideEffect / Callback / FailureSideEffect / Next Transition
    (
        re.compile(
            rf'^(?P<tr_id>{UUID_PATTERN})\s+'
            rf'(?P<cmd_type>SideEffect|Callback|FailureSideEffect|Next Transition)\s+(?P<command_name>.+)$'
        ),
        'COMMAND',
    ),
]


def parse_log_message(message: str, timestamp: datetime) -> TransitionEvent | None:
    """Parse a django-logic.transition log message into a TransitionEvent."""
    message = message.strip()
    for pattern, event_type in PATTERNS:
        m = pattern.match(message)
        if not m:
            continue
        groups = m.groupdict()
        tr_id = groups.get('tr_id', '')

        if event_type == 'START':
            return TransitionEvent(
                tr_id=tr_id,
                event_type='START',
                timestamp=timestamp,
                process_class=groups.get('process_class'),
                action_name=groups.get('action_name'),
                instance_key=groups.get('instance_key'),
                root_id=groups.get('root_id'),
                parent_id=groups.get('parent_id'),
                raw_message=message,
            )

        if event_type == 'FAIL':
            return TransitionEvent(
                tr_id=tr_id,
                event_type='FAIL',
                timestamp=timestamp,
                error_type=groups.get('error_type'),
                error_message=groups.get('error_message'),
                raw_message=message,
            )

        if event_type == 'SET_STATE':
            return TransitionEvent(
                tr_id=tr_id,
                event_type='SET_STATE',
                timestamp=timestamp,
                state=groups.get('state'),
                raw_message=message,
            )

        if event_type == 'COMMAND_GROUP':
            return TransitionEvent(
                tr_id=tr_id,
                event_type=groups.get('group', 'COMMAND_GROUP'),
                timestamp=timestamp,
                command_count=int(groups.get('command_count', 0)),
                raw_message=message,
            )

        if event_type == 'COMMAND':
            return TransitionEvent(
                tr_id=tr_id,
                event_type=groups.get('cmd_type', 'COMMAND'),
                timestamp=timestamp,
                command_name=groups.get('command_name'),
                raw_message=message,
            )

        return TransitionEvent(
            tr_id=tr_id,
            event_type=event_type,
            timestamp=timestamp,
            raw_message=message,
        )

    return None
