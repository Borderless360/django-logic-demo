import json
import math
from datetime import datetime

import pytest

from django_logic_monitoring.config import DLM_DEFAULT_TIME_LIMIT, DLM_MIN_EXECUTIONS
from django_logic_monitoring.storage import (
    AnomalyStore,
    LastLogTimestamp,
    StatStore,
    TransitionStore,
)


# ── LastLogTimestamp ─────────────────────────────────────────────────────────


class TestLastLogTimestamp:
    def test_get_returns_none_when_empty(self):
        assert LastLogTimestamp.get() is None

    def test_set_and_get(self):
        ts = datetime(2025, 6, 15, 12, 30, 0)
        LastLogTimestamp.set(ts)
        result = LastLogTimestamp.get()
        assert result == ts

    def test_overwrite(self):
        ts1 = datetime(2025, 1, 1)
        ts2 = datetime(2025, 6, 15)
        LastLogTimestamp.set(ts1)
        LastLogTimestamp.set(ts2)
        assert LastLogTimestamp.get() == ts2


# ── TransitionStore ──────────────────────────────────────────────────────────


class TestTransitionStore:
    def _create_default(self, tr_id="tr-001", **overrides):
        defaults = dict(
            tr_id=tr_id,
            process="TestProcess",
            action="do_test",
            model_name="app.mymodel",
            object_id="42",
            field_name="status",
            root_id="root-1",
            parent_id="parent-1",
            timestamp=datetime(2025, 6, 15, 10, 0, 0),
        )
        defaults.update(overrides)
        TransitionStore.create(**defaults)

    def test_create_and_get(self):
        self._create_default()
        tr = TransitionStore.get("tr-001")
        assert tr is not None
        assert tr["id"] == "tr-001"
        assert tr["process"] == "TestProcess"
        assert tr["action"] == "do_test"
        assert tr["model_name"] == "app.mymodel"
        assert tr["object_id"] == "42"
        assert tr["field_name"] == "status"
        assert tr["root_id"] == "root-1"
        assert tr["parent_id"] == "parent-1"
        assert tr["steps"] == "0"
        assert tr["step_n"] == "0"
        assert tr["is_completed"] == "0"

    def test_get_nonexistent(self):
        assert TransitionStore.get("nonexistent") is None

    def test_update_fields(self):
        self._create_default()
        TransitionStore.update("tr-001", steps="3", step_type="SideEffect", step_name="handler")
        tr = TransitionStore.get("tr-001")
        assert tr["steps"] == "3"
        assert tr["step_type"] == "SideEffect"
        assert tr["step_name"] == "handler"

    def test_update_timestamp(self):
        self._create_default()
        new_ts = datetime(2025, 6, 15, 11, 0, 0)
        TransitionStore.update("tr-001", timestamp=new_ts)
        tr = TransitionStore.get("tr-001")
        assert tr["timestamp"] == new_ts.isoformat()

    def test_update_is_completed(self):
        self._create_default()
        TransitionStore.update("tr-001", is_completed=True)
        tr = TransitionStore.get("tr-001")
        assert tr["is_completed"] == "1"

    def test_update_is_completed_false(self):
        self._create_default()
        TransitionStore.update("tr-001", is_completed=True)
        TransitionStore.update("tr-001", is_completed=False)
        tr = TransitionStore.get("tr-001")
        assert tr["is_completed"] == "0"

    def test_exists(self):
        assert TransitionStore.exists("tr-001") is False
        self._create_default()
        assert TransitionStore.exists("tr-001") is True

    def test_delete(self):
        self._create_default()
        TransitionStore.delete("tr-001")
        assert TransitionStore.get("tr-001") is None
        assert TransitionStore.exists("tr-001") is False

    def test_get_all(self):
        self._create_default("tr-001")
        self._create_default("tr-002", process="OtherProcess")
        all_trs = TransitionStore.get_all()
        ids = {tr["id"] for tr in all_trs}
        assert ids == {"tr-001", "tr-002"}

    def test_get_all_empty(self):
        assert TransitionStore.get_all() == []


# ── StatStore ────────────────────────────────────────────────────────────────


class TestStatStore:
    def test_get_or_create(self):
        stat_id = StatStore.get_or_create("Process", "action", "SideEffect", "handler")
        stat = StatStore.get(stat_id)
        assert stat is not None
        assert stat["process"] == "Process"
        assert stat["action"] == "action"
        assert stat["step_type"] == "SideEffect"
        assert stat["step_name"] == "handler"
        assert json.loads(stat["last_exec"]) == []
        assert float(stat["time_limit"]) == DLM_DEFAULT_TIME_LIMIT

    def test_get_or_create_idempotent(self):
        id1 = StatStore.get_or_create("P", "A", "SideEffect", "h")
        id2 = StatStore.get_or_create("P", "A", "SideEffect", "h")
        assert id1 == id2

    def test_get_or_create_different_keys(self):
        id1 = StatStore.get_or_create("P1", "A", "SideEffect", "h")
        id2 = StatStore.get_or_create("P2", "A", "SideEffect", "h")
        assert id1 != id2

    def test_add_execution(self):
        stat_id = StatStore.get_or_create("P", "A", "SideEffect", "h")
        StatStore.add_execution(stat_id, 1.5)
        stat = StatStore.get(stat_id)
        assert json.loads(stat["last_exec"]) == [1.5]

    def test_add_multiple_executions(self):
        stat_id = StatStore.get_or_create("P", "A", "SideEffect", "h")
        for i in range(1, 6):
            StatStore.add_execution(stat_id, float(i))
        stat = StatStore.get(stat_id)
        execs = json.loads(stat["last_exec"])
        assert execs == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_time_limit_uses_default_below_min_executions(self):
        stat_id = StatStore.get_or_create("P", "A", "SideEffect", "h")
        for i in range(DLM_MIN_EXECUTIONS - 1):
            StatStore.add_execution(stat_id, 1.0)
        stat = StatStore.get(stat_id)
        assert float(stat["time_limit"]) == DLM_DEFAULT_TIME_LIMIT

    def test_time_limit_updates_at_min_executions(self):
        stat_id = StatStore.get_or_create("P", "A", "SideEffect", "h")
        for _ in range(DLM_MIN_EXECUTIONS):
            StatStore.add_execution(stat_id, 10.0)

        stat = StatStore.get(stat_id)
        # All identical → std=0, time_limit = mean + 0 = 10.0
        assert float(stat["time_limit"]) == pytest.approx(10.0)

    def test_time_limit_mean_plus_2_sigma(self):
        stat_id = StatStore.get_or_create("P", "A", "SideEffect", "h")
        values = [10.0, 12.0, 8.0, 11.0, 9.0]
        for v in values:
            StatStore.add_execution(stat_id, v)

        stat = StatStore.get(stat_id)
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance)
        expected = mean + 2 * std
        assert float(stat["time_limit"]) == pytest.approx(expected)

    def test_find(self):
        StatStore.get_or_create("P", "A", "SideEffect", "h")
        found = StatStore.find("P", "A", "SideEffect", "h")
        assert found is not None
        assert found["process"] == "P"

    def test_find_missing(self):
        assert StatStore.find("X", "X", "X", "X") is None

    def test_get_all(self):
        StatStore.get_or_create("P1", "A", "SideEffect", "h1")
        StatStore.get_or_create("P2", "A", "SideEffect", "h2")
        all_stats = StatStore.get_all()
        assert len(all_stats) == 2


# ── AnomalyStore ─────────────────────────────────────────────────────────────


class TestAnomalyStore:
    def test_create_and_get_all(self):
        ts = datetime(2025, 6, 15, 10, 0, 0)
        aid = AnomalyStore.create(tr_id="tr-001", current_exec=350.5, timestamp=ts)
        anomalies = AnomalyStore.get_all()
        assert len(anomalies) == 1
        assert anomalies[0]["id"] == aid
        assert anomalies[0]["tr_id"] == "tr-001"
        assert float(anomalies[0]["current_exec"]) == 350.5

    def test_create_multiple(self):
        AnomalyStore.create(tr_id="tr-001", current_exec=100.0)
        AnomalyStore.create(tr_id="tr-002", current_exec=200.0)
        assert len(AnomalyStore.get_all()) == 2

    def test_delete(self):
        aid = AnomalyStore.create(tr_id="tr-001", current_exec=100.0)
        AnomalyStore.delete(aid)
        assert len(AnomalyStore.get_all()) == 0

    def test_get_all_empty(self):
        assert AnomalyStore.get_all() == []
