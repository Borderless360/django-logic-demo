from datetime import datetime, timezone

from autofixer.events import EventType, parse_log_row


def test_parse_start_event():
    row = {
        "message": "tr-1 Start BasicProcess go_to_B abstract-a-status-1 root-1 root-1",
        "_timestamp": datetime.now(tz=timezone.utc),
    }
    event = parse_log_row(row)
    assert event is not None
    assert event.event_type == EventType.START
    assert event.tr_id == "tr-1"
    assert event.process_class == "BasicProcess"
    assert event.action_name == "go_to_B"
    assert event.root_id == "root-1"


def test_parse_side_effect_event():
    row = {
        "message": "tr-1 SideEffect send_email",
        "_timestamp": datetime.now(tz=timezone.utc),
    }
    event = parse_log_row(row)
    assert event is not None
    assert event.event_type == EventType.SIDE_EFFECT
    assert event.name == "send_email"

