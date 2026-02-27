from __future__ import annotations

import fnmatch
import logging
from datetime import datetime, timedelta, timezone

from autofixer.alerts.email import EmailAlert
from autofixer.alerts.webhook import WebhookAlert
from autofixer.config import AutofixerSettings, get_autofixer_settings
from autofixer.detector import AnomalyDetector
from autofixer.events import Anomaly, parse_log_row
from autofixer.sources.clickhouse import ClickHouseSource
from autofixer.stats.redis_backend import RedisStatsBackend
from autofixer.tracker import ActiveTransitionTracker
from core.redis import redis_client

logger = logging.getLogger("autofixer")

_monitor_singleton = None


class ActionDispatcher:
    def __init__(self, *, settings_obj: AutofixerSettings, redis=None) -> None:
        self.settings = settings_obj
        self.redis = redis or redis_client
        self.email = EmailAlert()
        self.webhook = WebhookAlert()

    def dispatch(self, anomaly: Anomaly) -> None:
        matched = self._match_actions(anomaly.details.get("process_action_key", ""))
        for config in matched:
            self._dispatch_one(anomaly, config)

    def _dispatch_one(self, anomaly: Anomaly, config: dict) -> None:
        dedupe_key = f"{self.settings.redis_key_prefix}:alert:{anomaly.fingerprint}"
        was_set = self.redis.set(
            dedupe_key,
            "1",
            nx=True,
            ex=int(timedelta(days=30).total_seconds()),
        )
        if not was_set:
            return

        action_type = config.get("type")
        if action_type == "email":
            self.email.send(anomaly=anomaly, config=config)
            return
        if action_type == "webhook":
            self.webhook.send(anomaly=anomaly, config=config)
            return
        logger.warning("Unknown autofixer action type: %s", action_type)

    def _match_actions(self, process_action_key: str) -> list[dict]:
        matched: list[dict] = []
        for rule in self.settings.action_config:
            pattern = str(rule.get("pattern", "*:*"))
            if fnmatch.fnmatch(process_action_key, pattern):
                matched.extend(rule.get("actions", []))
        return matched


class MonitoringService:
    def __init__(
        self,
        *,
        settings_obj: AutofixerSettings | None = None,
        source=None,
        tracker=None,
        stats=None,
        detector=None,
        dispatcher=None,
        redis=None,
    ) -> None:
        self.settings = settings_obj or get_autofixer_settings()
        self.redis = redis or redis_client
        self.source = source or ClickHouseSource()
        self.tracker = tracker or ActiveTransitionTracker(
            key_prefix=self.settings.redis_key_prefix,
            redis=self.redis,
        )
        self.stats = stats or RedisStatsBackend(
            key_prefix=self.settings.redis_key_prefix,
            window_size=self.settings.stats_window_size,
            ttl_seconds=int(timedelta(days=30).total_seconds()),
            redis=self.redis,
        )
        self.detector = detector or AnomalyDetector(
            std_dev_multiplier=self.settings.anomaly_std_dev_multiplier,
            min_samples=self.settings.anomaly_min_samples,
        )
        self.dispatcher = dispatcher or ActionDispatcher(settings_obj=self.settings, redis=self.redis)

    def tick(self) -> dict:
        if not self._acquire_lock():
            return {"status": "skipped", "reason": "monitor_is_locked"}
        try:
            since = self._get_cursor()
            rows = self.source.fetch_logs(since=since)
            max_timestamp = since
            processed = 0
            anomalies = 0

            for row in rows:
                event = parse_log_row(row)
                if event is None:
                    continue
                completion = self.tracker.apply(event)
                processed += 1
                if max_timestamp is None or event.timestamp > max_timestamp:
                    max_timestamp = event.timestamp
                if completion is not None:
                    anomalies += self._handle_completion(completion)

            if max_timestamp is not None:
                self._set_cursor(max_timestamp)

            return {
                "status": "ok",
                "processed_events": processed,
                "anomalies": anomalies,
                "active": len(self.tracker.get_active()),
            }
        finally:
            self._release_lock()

    def get_status(self) -> dict:
        return {
            "active_transitions": self.tracker.get_active(),
            "active_roots": self.tracker.get_active_roots(),
            "cursor": self._get_cursor().isoformat() if self._get_cursor() else None,
        }

    def _handle_completion(self, completion) -> int:
        process_action_key = f"{completion.process_class}:{completion.action_name}"
        transition_metric = f"transition:{process_action_key}"

        transition_samples = self.stats.get_samples(transition_metric)
        transition_anomaly = self.detector.detect(
            kind="transition",
            metric_key=transition_metric,
            observed=completion.duration_seconds,
            samples=transition_samples,
            fingerprint=f"transition:{completion.tr_id}",
            details={
                "tr_id": completion.tr_id,
                "root_id": completion.root_id,
                "process_action_key": process_action_key,
            },
        )
        self.stats.add_sample(transition_metric, completion.duration_seconds)

        anomalies = 0
        if transition_anomaly is not None:
            self.dispatcher.dispatch(transition_anomaly)
            anomalies += 1

        for side_effect_name, side_effect_duration in completion.side_effect_durations:
            metric_key = f"side_effect:{process_action_key}:{side_effect_name}"
            samples = self.stats.get_samples(metric_key)
            anomaly = self.detector.detect(
                kind="side_effect",
                metric_key=metric_key,
                observed=side_effect_duration,
                samples=samples,
                fingerprint=f"side_effect:{completion.tr_id}:{side_effect_name}",
                details={
                    "tr_id": completion.tr_id,
                    "root_id": completion.root_id,
                    "process_action_key": process_action_key,
                    "side_effect_name": side_effect_name,
                },
            )
            self.stats.add_sample(metric_key, side_effect_duration)
            if anomaly is not None:
                self.dispatcher.dispatch(anomaly)
                anomalies += 1
        return anomalies

    def _cursor_key(self) -> str:
        return f"{self.settings.redis_key_prefix}:cursor"

    def _lock_key(self) -> str:
        return f"{self.settings.redis_key_prefix}:monitor:lock"

    def _get_cursor(self) -> datetime | None:
        raw = self.redis.get(self._cursor_key())
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return datetime.fromisoformat(raw)

    def _set_cursor(self, value: datetime) -> None:
        self.redis.set(self._cursor_key(), value.astimezone(timezone.utc).isoformat())

    def _acquire_lock(self) -> bool:
        return bool(
            self.redis.set(
                self._lock_key(),
                "1",
                nx=True,
                ex=self.settings.lock_timeout,
            )
        )

    def _release_lock(self) -> None:
        self.redis.delete(self._lock_key())


def get_monitor() -> MonitoringService:
    global _monitor_singleton
    if _monitor_singleton is None:
        _monitor_singleton = MonitoringService()
    return _monitor_singleton

