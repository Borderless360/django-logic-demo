import pytest

from django_logic_monitoring.actions import _parse_log, _parse_instance_key


# ── _parse_log ───────────────────────────────────────────────────────────────


class TestParseLogEdgeCases:
    def test_empty_string(self):
        assert _parse_log("") is None

    def test_none(self):
        assert _parse_log(None) is None

    def test_single_word(self):
        assert _parse_log("abc") is None


class TestParseLogStart:
    def test_basic(self):
        msg = "abc-123 Start ProcessName do_something app-model-field-42 root-1 parent-1"
        result = _parse_log(msg)
        assert result == {
            "type": "Start",
            "tr_id": "abc-123",
            "process": "ProcessName",
            "action": "do_something",
            "instance_key": "app-model-field-42",
            "root_id": "root-1",
            "parent_id": "parent-1",
        }

    def test_too_few_tokens(self):
        msg = "abc-123 Start ProcessName"
        result = _parse_log(msg)
        assert result is not None
        assert result["type"] == "Unknown"


class TestParseLogGroupEvents:
    @pytest.mark.parametrize("group,count", [
        ("SideEffects", 3),
        ("Callbacks", 5),
        ("FailureSideEffects", 2),
    ])
    def test_group_events(self, group, count):
        msg = f"tr-001 {group} {count}"
        result = _parse_log(msg)
        assert result == {"type": group, "tr_id": "tr-001", "count": count}

    def test_non_numeric_count(self):
        result = _parse_log("tr-001 SideEffects abc")
        assert result is not None
        assert result["type"] == "Unknown"


class TestParseLogStepEvents:
    @pytest.mark.parametrize("step_type", ["SideEffect", "Callback", "FailureSideEffect"])
    def test_step_event(self, step_type):
        msg = f"tr-001 {step_type} my_handler"
        result = _parse_log(msg)
        assert result == {"type": step_type, "tr_id": "tr-001", "name": "my_handler"}

    def test_step_name_with_spaces(self):
        msg = "tr-001 SideEffect send_email_notification"
        result = _parse_log(msg)
        assert result["name"] == "send_email_notification"


class TestParseLogSetState:
    def test_basic(self):
        result = _parse_log("tr-001 Set State active")
        assert result == {"type": "SetState", "tr_id": "tr-001", "state": "active"}

    def test_state_with_spaces(self):
        result = _parse_log("tr-001 Set State in progress")
        assert result == {"type": "SetState", "tr_id": "tr-001", "state": "in progress"}


class TestParseLogSimpleEvents:
    def test_lock(self):
        result = _parse_log("tr-001 Lock")
        assert result == {"type": "Lock", "tr_id": "tr-001"}

    def test_unlock(self):
        result = _parse_log("tr-001 Unlock")
        assert result == {"type": "Unlock", "tr_id": "tr-001"}

    def test_background_mode(self):
        result = _parse_log("tr-001 Background Mode")
        assert result == {"type": "BackgroundMode", "tr_id": "tr-001"}

    def test_next_transition(self):
        result = _parse_log("tr-001 Next Transition")
        assert result == {"type": "NextTransition", "tr_id": "tr-001"}


class TestParseLogFail:
    def test_fail_basic(self):
        result = _parse_log("tr-001 Fail something went wrong")
        assert result["type"] == "Fail"
        assert result["tr_id"] == "tr-001"
        assert "something went wrong" in result["detail"]


class TestParseLogUnknown:
    def test_unknown_event(self):
        msg = "tr-001 SomeWeirdEvent data"
        result = _parse_log(msg)
        assert result["type"] == "Unknown"
        assert result["tr_id"] == "tr-001"
        assert result["raw"] == msg


# ── _parse_instance_key ──────────────────────────────────────────────────────


class TestParseInstanceKey:
    def test_standard_key(self):
        model, field, obj_id = _parse_instance_key("myapp-mymodel-status-42")
        assert model == "myapp.mymodel"
        assert field == "status"
        assert obj_id == "42"

    def test_uuid_pk(self):
        model, field, obj_id = _parse_instance_key(
            "app-model-field-550e8400-e29b-41d4-a716-446655440000"
        )
        assert model == "app.model"
        assert field == "field"
        assert obj_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_short_key(self):
        model, field, obj_id = _parse_instance_key("too-short")
        assert model == "too-short"
        assert field == ""
        assert obj_id == ""

    def test_single_segment(self):
        model, field, obj_id = _parse_instance_key("single")
        assert model == "single"
