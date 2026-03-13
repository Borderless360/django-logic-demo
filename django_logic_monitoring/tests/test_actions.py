import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from django_logic_monitoring.actions import (
    _remove_completed_transitions,
    clear,
    detect_anomaly,
    fetch_logs,
)
from django_logic_monitoring.config import (
    DLM_DEFAULT_TIME_LIMIT,
    DLM_DEGRADATION_RATIO,
    DLM_FAILURE_THRESHOLD,
    DLM_LOG_PAGE_SIZE,
    DLM_LOOP_THRESHOLD,
    DLM_MIN_EXECUTIONS,
    DLM_STUCK_TIMEOUT,
)
from django_logic_monitoring.storage import (
    AnomalyStore,
    AnomalyType,
    FailureCounterStore,
    LastLogTimestamp,
    LoopCounterStore,
    StatStore,
    TransitionStore,
)


def _make_log(message: str, timestamp: datetime) -> dict:
    return {"message": message, "timestamp": timestamp}


def _make_transition_logs(
    tr_id: str = "tr-001",
    process: str = "Proc",
    action: str = "act",
    instance_key: str = "app-model-field-1",
    base_time: datetime | None = None,
):
    """Build a typical transition log sequence: Start → SideEffects → SideEffect → Unlock."""
    t = base_time or datetime(2025, 6, 15, 10, 0, 0)
    return [
        _make_log(f"{tr_id} Start {process} {action} {instance_key} {tr_id} {tr_id}", t),
        _make_log(f"{tr_id} Lock", t + timedelta(milliseconds=10)),
        _make_log(f"{tr_id} SideEffects 2", t + timedelta(milliseconds=20)),
        _make_log(f"{tr_id} SideEffect handler_one", t + timedelta(seconds=1)),
        _make_log(f"{tr_id} SideEffect handler_two", t + timedelta(seconds=2)),
        _make_log(f"{tr_id} Set State done", t + timedelta(seconds=2, milliseconds=100)),
        _make_log(f"{tr_id} Unlock", t + timedelta(seconds=3)),
    ]


# ── fetch_logs ───────────────────────────────────────────────────────────────


class TestFetchLogs:
    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_no_logs(self, mock_fetch):
        mock_fetch.return_value = []
        fetch_logs()
        assert TransitionStore.get_all() == []

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_start_creates_transition(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-42 tr-001 tr-001", t),
        ]
        fetch_logs()
        tr = TransitionStore.get("tr-001")
        assert tr is not None
        assert tr["process"] == "Proc"
        assert tr["action"] == "act"
        assert tr["model_name"] == "app.model"
        assert tr["object_id"] == "42"
        assert tr["field_name"] == "field"

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_full_lifecycle_removes_completed(self, mock_fetch):
        mock_fetch.return_value = _make_transition_logs()
        fetch_logs()
        assert TransitionStore.get_all() == []

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_updates_last_timestamp(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-1 tr-001 tr-001", t),
            _make_log("tr-001 Lock", t + timedelta(seconds=1)),
        ]
        fetch_logs()
        assert LastLogTimestamp.get() == t + timedelta(seconds=1)

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_updates_stats_for_steps(self, mock_fetch):
        mock_fetch.return_value = _make_transition_logs()
        fetch_logs()

        stat = StatStore.find("Proc", "act", "SideEffect", "handler_one")
        assert stat is not None
        assert float(stat["time_limit"]) == DLM_DEFAULT_TIME_LIMIT

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_group_event_updates_transition(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-1 tr-001 tr-001", t),
            _make_log("tr-001 SideEffects 3", t + timedelta(seconds=1)),
        ]
        fetch_logs()
        tr = TransitionStore.get("tr-001")
        assert tr is not None
        assert tr["steps"] == "3"
        assert tr["step_type"] == "SideEffect"
        assert tr["step_n"] == "0"

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_step_event_increments_step_n(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-1 tr-001 tr-001", t),
            _make_log("tr-001 SideEffects 2", t + timedelta(seconds=1)),
            _make_log("tr-001 SideEffect first_handler", t + timedelta(seconds=2)),
            _make_log("tr-001 SideEffect second_handler", t + timedelta(seconds=3)),
        ]
        fetch_logs()
        tr = TransitionStore.get("tr-001")
        assert tr is not None
        assert tr["step_n"] == "2"
        assert tr["step_name"] == "second_handler"

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_fail_marks_completed(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-1 tr-001 tr-001", t),
            _make_log("tr-001 Fail something broke", t + timedelta(seconds=1)),
        ]
        fetch_logs()
        # Completed transition should be removed
        assert TransitionStore.get_all() == []

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_reads_since_last_timestamp(self, mock_fetch):
        mock_fetch.return_value = []
        saved_ts = datetime(2025, 6, 15, 9, 0, 0)
        LastLogTimestamp.set(saved_ts)
        fetch_logs()
        mock_fetch.assert_called_once_with(saved_ts, limit=DLM_LOG_PAGE_SIZE)

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_ignores_events_for_unknown_transitions(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("ghost SideEffects 3", t),
            _make_log("ghost SideEffect handler", t + timedelta(seconds=1)),
            _make_log("ghost Unlock", t + timedelta(seconds=2)),
        ]
        fetch_logs()
        assert TransitionStore.get_all() == []

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_multiple_transitions(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start P1 a1 app-m-f-1 tr-001 tr-001", t),
            _make_log("tr-002 Start P2 a2 app-m-f-2 tr-002 tr-002", t + timedelta(seconds=1)),
        ]
        fetch_logs()
        assert len(TransitionStore.get_all()) == 2

    @patch("django_logic_monitoring.actions.DLM_LOG_PAGE_SIZE", 3)
    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_fetches_multiple_pages(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        all_logs = [
            _make_log("tr-001 Start P a app-m-f-1 tr-001 tr-001", t),
            _make_log("tr-001 Lock", t + timedelta(seconds=1)),
            _make_log("tr-001 Unlock", t + timedelta(seconds=2)),
        ]

        def fake_fetch(since, *, limit=None):
            result = [e for e in all_logs if since is None or e["timestamp"] > since]
            return result[:limit] if limit else result

        mock_fetch.side_effect = fake_fetch
        fetch_logs()
        assert TransitionStore.get_all() == []
        assert LastLogTimestamp.get() == t + timedelta(seconds=2)
        assert mock_fetch.call_count == 2

    @patch("django_logic_monitoring.actions.DLM_LOG_PAGE_SIZE", 2)
    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_pagination_does_not_skip_duplicate_timestamps(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        all_logs = [
            _make_log("tr-001 Start P a app-m-f-1 tr-001 tr-001", t),
            _make_log("tr-001 Lock", t + timedelta(seconds=1)),
            _make_log("tr-001 SideEffects 1", t + timedelta(seconds=1)),
            _make_log("tr-001 SideEffect handler", t + timedelta(seconds=2)),
            _make_log("tr-001 Unlock", t + timedelta(seconds=3)),
        ]

        def fake_fetch(since, *, limit=None):
            result = [e for e in all_logs if since is None or e["timestamp"] > since]
            return result[:limit] if limit else result

        mock_fetch.side_effect = fake_fetch
        fetch_logs()
        assert TransitionStore.get_all() == []
        assert LastLogTimestamp.get() == t + timedelta(seconds=3)


# ── _remove_completed_transitions ────────────────────────────────────────────


class TestRemoveCompletedTransitions:
    def test_removes_simple_completed(self):
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        TransitionStore.update("tr-001", is_completed=True)
        _remove_completed_transitions()
        assert TransitionStore.get_all() == []

    def test_keeps_incomplete(self):
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        _remove_completed_transitions()
        assert len(TransitionStore.get_all()) == 1

    def test_parent_kept_when_child_incomplete(self):
        TransitionStore.create(
            tr_id="parent", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        TransitionStore.update("parent", is_completed=True)

        TransitionStore.create(
            tr_id="child", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            parent_id="parent", timestamp=datetime(2025, 1, 1),
        )
        _remove_completed_transitions()
        ids = {tr["id"] for tr in TransitionStore.get_all()}
        assert "parent" in ids
        assert "child" in ids

    def test_parent_removed_when_child_completed(self):
        TransitionStore.create(
            tr_id="parent", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        TransitionStore.update("parent", is_completed=True)

        TransitionStore.create(
            tr_id="child", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            parent_id="parent", timestamp=datetime(2025, 1, 1),
        )
        TransitionStore.update("child", is_completed=True)

        _remove_completed_transitions()
        assert TransitionStore.get_all() == []


# ── detect_anomaly ───────────────────────────────────────────────────────────


class TestDetectAnomaly:
    def test_no_transitions(self):
        result = detect_anomaly()
        assert result == []

    def test_skips_completed_transitions(self):
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        TransitionStore.update(
            "tr-001",
            is_completed=True,
            step_type="SideEffect",
            step_name="h",
            timestamp=datetime(2025, 1, 1),
        )
        assert detect_anomaly() == []

    def test_skips_transitions_without_step_for_long_execution(self):
        recent = datetime.now() - timedelta(seconds=10)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=recent,
        )
        anomalies = detect_anomaly()
        long_exec = [a for a in anomalies if a["type"] == "LONG_EXECUTION"]
        assert long_exec == []

    def test_detects_long_running_step(self):
        old_time = datetime.now() - timedelta(seconds=DLM_DEFAULT_TIME_LIMIT + 100)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=old_time,
        )
        TransitionStore.update(
            "tr-001",
            step_type="SideEffect",
            step_name="slow_handler",
            timestamp=old_time,
        )
        anomalies = detect_anomaly()
        long_exec = [a for a in anomalies if a["type"] == "LONG_EXECUTION"]
        assert len(long_exec) == 1
        assert long_exec[0]["tr_id"] == "tr-001"

    def test_no_anomaly_within_limit(self):
        recent = datetime.now() - timedelta(seconds=10)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=recent,
        )
        TransitionStore.update(
            "tr-001",
            step_type="SideEffect",
            step_name="fast_handler",
            timestamp=recent,
        )
        assert detect_anomaly() == []

    def test_skips_already_detected_anomaly(self):
        old_time = datetime.now() - timedelta(seconds=DLM_DEFAULT_TIME_LIMIT + 100)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=old_time,
        )
        TransitionStore.update(
            "tr-001",
            step_type="SideEffect",
            step_name="slow_handler",
            timestamp=old_time,
        )

        first = detect_anomaly()
        assert len(first) == 1
        second = detect_anomaly()
        assert len(second) == 0

    def test_uses_stat_time_limit(self):
        stat_id = StatStore.get_or_create("P", "a", "SideEffect", "h")
        from core.redis import redis_client
        redis_client.hset(
            f"dlm:stat:{stat_id}",
            mapping={"time_limit": "5.0"},
        )

        old_time = datetime.now() - timedelta(seconds=10)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=old_time,
        )
        TransitionStore.update(
            "tr-001",
            step_type="SideEffect",
            step_name="h",
            timestamp=old_time,
        )
        anomalies = detect_anomaly()
        assert len(anomalies) == 1
        assert anomalies[0]["time_limit"] == 5.0

    def test_creates_anomaly_record(self):
        old_time = datetime.now() - timedelta(seconds=DLM_DEFAULT_TIME_LIMIT + 100)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=old_time,
        )
        TransitionStore.update(
            "tr-001",
            step_type="SideEffect",
            step_name="h",
            timestamp=old_time,
        )
        detect_anomaly()
        stored = AnomalyStore.get_all()
        assert len(stored) == 1
        assert stored[0]["tr_id"] == "tr-001"


# ── clear ────────────────────────────────────────────────────────────────────


class TestClear:
    def test_removes_completed(self):
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        TransitionStore.update("tr-001", is_completed=True)
        clear()
        assert TransitionStore.get_all() == []

    def test_removes_orphaned_anomalies(self):
        AnomalyStore.create(
            tr_id="nonexistent", process="P", action="a",
            step_type="SideEffect", step_name="h",
            anomaly_type=AnomalyType.LONG_EXECUTION,
        )
        clear()
        assert AnomalyStore.get_all() == []

    def test_keeps_anomalies_with_active_transitions(self):
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        AnomalyStore.create(
            tr_id="tr-001", process="P", action="a",
            step_type="SideEffect", step_name="h",
            anomaly_type=AnomalyType.LONG_EXECUTION,
        )
        clear()
        assert len(AnomalyStore.get_all()) == 1

    def test_keeps_incomplete_transitions(self):
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=datetime(2025, 1, 1),
        )
        clear()
        assert len(TransitionStore.get_all()) == 1


# ── detect_anomaly: stuck transition ─────────────────────────────────────────


class TestDetectStuckTransition:
    def test_detects_stuck(self):
        old_time = datetime.now() - timedelta(seconds=DLM_STUCK_TIMEOUT + 100)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=old_time,
        )
        TransitionStore.update("tr-001", step_type="SideEffect", step_name="h", timestamp=old_time)
        anomalies = detect_anomaly()
        types = {a["type"] for a in anomalies}
        assert "STUCK_TRANSITION" in types

    def test_no_stuck_within_timeout(self):
        recent = datetime.now() - timedelta(seconds=10)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=recent,
        )
        anomalies = detect_anomaly()
        stuck = [a for a in anomalies if a["type"] == "STUCK_TRANSITION"]
        assert stuck == []


# ── detect_anomaly: frequent failures ────────────────────────────────────────


class TestDetectFrequentFailures:
    def test_detects_frequent_failures(self):
        now = datetime.now()
        for i in range(DLM_FAILURE_THRESHOLD):
            FailureCounterStore.record("P", "a", now - timedelta(seconds=i))

        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=now - timedelta(seconds=5),
        )
        anomalies = detect_anomaly()
        types = {a["type"] for a in anomalies}
        assert "FREQUENT_FAILURES" in types

    def test_no_anomaly_below_threshold(self):
        now = datetime.now()
        FailureCounterStore.record("P", "a", now)

        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=now - timedelta(seconds=5),
        )
        anomalies = detect_anomaly()
        failures = [a for a in anomalies if a["type"] == "FREQUENT_FAILURES"]
        assert failures == []


# ── detect_anomaly: execution time degradation ───────────────────────────────


class TestDetectDegradation:
    def test_detects_degradation(self):
        stat_id = StatStore.get_or_create("P", "a", "SideEffect", "h")
        older = [1.0] * (DLM_MIN_EXECUTIONS // 2)
        recent = [DLM_DEGRADATION_RATIO * 1.0 + 0.1] * (DLM_MIN_EXECUTIONS - DLM_MIN_EXECUTIONS // 2)
        all_exec = older + recent

        from core.redis import redis_client
        redis_client.hset(
            f"dlm:stat:{stat_id}",
            mapping={
                "last_exec": json.dumps(all_exec),
                "time_limit": "9999",
            },
        )

        ts = datetime.now() - timedelta(seconds=5)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=ts,
        )
        TransitionStore.update("tr-001", step_type="SideEffect", step_name="h", timestamp=ts)
        anomalies = detect_anomaly()
        types = {a["type"] for a in anomalies}
        assert "EXECUTION_TIME_DEGRADATION" in types

    def test_no_degradation_with_stable_times(self):
        stat_id = StatStore.get_or_create("P", "a", "SideEffect", "h")
        all_exec = [1.0] * DLM_MIN_EXECUTIONS

        from core.redis import redis_client
        redis_client.hset(
            f"dlm:stat:{stat_id}",
            mapping={
                "last_exec": json.dumps(all_exec),
                "time_limit": "9999",
            },
        )

        ts = datetime.now() - timedelta(seconds=5)
        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=ts,
        )
        TransitionStore.update("tr-001", step_type="SideEffect", step_name="h", timestamp=ts)
        anomalies = detect_anomaly()
        degraded = [a for a in anomalies if a["type"] == "EXECUTION_TIME_DEGRADATION"]
        assert degraded == []


# ── detect_anomaly: loop detection ───────────────────────────────────────────


class TestDetectLoop:
    def test_detects_loop(self):
        now = datetime.now()
        for i in range(DLM_LOOP_THRESHOLD):
            LoopCounterStore.record("m", "1", "P", "a", now - timedelta(seconds=i))

        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=now - timedelta(seconds=5),
        )
        anomalies = detect_anomaly()
        types = {a["type"] for a in anomalies}
        assert "LOOP_DETECTION" in types

    def test_no_loop_below_threshold(self):
        now = datetime.now()
        LoopCounterStore.record("m", "1", "P", "a", now)

        TransitionStore.create(
            tr_id="tr-001", process="P", action="a",
            model_name="m", object_id="1", field_name="f",
            timestamp=now - timedelta(seconds=5),
        )
        anomalies = detect_anomaly()
        loops = [a for a in anomalies if a["type"] == "LOOP_DETECTION"]
        assert loops == []


# ── fetch_logs: counter recording ────────────────────────────────────────────


class TestFetchLogsCounterRecording:
    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_records_failure_counter(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-1 tr-001 tr-001", t),
            _make_log("tr-001 Fail something broke", t + timedelta(seconds=1)),
        ]
        fetch_logs()
        assert FailureCounterStore.get_count("Proc", "act", t + timedelta(seconds=1)) == 1

    @patch("django_logic_monitoring.actions.fetch_logs_since")
    def test_records_loop_counter(self, mock_fetch):
        t = datetime(2025, 6, 15, 10, 0, 0)
        mock_fetch.return_value = [
            _make_log("tr-001 Start Proc act app-model-field-1 tr-001 tr-001", t),
        ]
        fetch_logs()
        assert LoopCounterStore.get_count("app.model", "1", "Proc", "act", t) == 1
