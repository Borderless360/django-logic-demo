from datetime import datetime, timedelta, timezone

from autofixer.config import AutofixerSettings
from autofixer.detector import AnomalyDetector
from autofixer.monitor import ActionDispatcher, MonitoringService
from autofixer.stats.redis_backend import RedisStatsBackend
from autofixer.tracker import ActiveTransitionTracker


class StubSource:
    def __init__(self, rows):
        self.rows = rows

    def fetch_logs(self, *, since, limit=5000):  # noqa: ARG002
        if since is None:
            return self.rows
        return [row for row in self.rows if row["_timestamp"] > since]


def test_monitor_detects_anomaly_and_dispatches_once(fake_redis, monkeypatch):
    base = datetime.now(tz=timezone.utc)
    rows = [
        {"message": "tr-1 Start BasicProcess go_to_B abstract-a-status-1 tr-1 tr-1", "_timestamp": base},
        {"message": "tr-1 Unlock", "_timestamp": base + timedelta(seconds=10)},
    ]

    settings_obj = AutofixerSettings(
        log_source="clickhouse",
        stats_backend="redis",
        poll_interval=5,
        lock_timeout=30,
        anomaly_std_dev_multiplier=2.0,
        anomaly_min_samples=5,
        stats_window_size=1000,
        redis_key_prefix="autofixer-test",
        stuck_transition_seconds=300,
        action_config=[{"pattern": "BasicProcess:*", "actions": [{"type": "webhook", "url": "https://x"}]}],
    )

    stats = RedisStatsBackend(
        key_prefix="autofixer-test",
        window_size=1000,
        ttl_seconds=3600,
        redis=fake_redis,
    )
    metric_key = "transition:BasicProcess:go_to_B"
    for value in [1, 1.1, 0.9, 1.2, 1.0]:
        stats.add_sample(metric_key, value)

    calls = []

    def fake_webhook_send(*, anomaly, config):
        calls.append((anomaly.metric_key, config["type"]))

    dispatcher = ActionDispatcher(settings_obj=settings_obj, redis=fake_redis)
    monkeypatch.setattr(dispatcher.webhook, "send", fake_webhook_send)

    monitor = MonitoringService(
        settings_obj=settings_obj,
        source=StubSource(rows),
        tracker=ActiveTransitionTracker(key_prefix="autofixer-test", redis=fake_redis),
        stats=stats,
        detector=AnomalyDetector(std_dev_multiplier=2.0, min_samples=5),
        dispatcher=dispatcher,
        redis=fake_redis,
    )

    result_1 = monitor.tick()
    result_2 = monitor.tick()

    assert result_1["anomalies"] == 1
    assert result_2["processed_events"] == 0
    assert calls == [("transition:BasicProcess:go_to_B", "webhook")]

