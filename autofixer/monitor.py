"""
Monitoring process (Mon-1, Mon-2, Mon-3).
Singleton process listening in a separately run task.
Near-realtime (up to 5 sec delay). Auto-restart on crash.
"""

import logging
from datetime import datetime
from typing import Iterator

from django.conf import settings

from autofixer.config import run_actions
from autofixer.detector import AnomalyDetector
from autofixer.events import LogEvent, parse_event
from autofixer.sources.base import LogSource
from autofixer.sources.clickhouse import ClickHouseSource
from autofixer.stats.redis_backend import RedisStatsBackend
from autofixer.tracker import TransitionTracker

logger = logging.getLogger("autofixer")


def get_source() -> LogSource:
    """Get log source from config (SRC-2: default ClickHouse)."""
    cfg = getattr(settings, "AUTOFIXER", {})
    kind = cfg.get("LOG_SOURCE", "clickhouse")
    if kind == "clickhouse":
        return ClickHouseSource()
    raise ValueError(f"Unknown LOG_SOURCE: {kind}")


def get_stats_backend():
    cfg = getattr(settings, "AUTOFIXER", {})
    kind = cfg.get("STATS_BACKEND", "redis")
    if kind == "redis":
        return RedisStatsBackend()
    raise ValueError(f"Unknown STATS_BACKEND: {kind}")


class Monitor:
    """
    Main monitoring loop. Mon-1: singleton-style (one process).
    Mon-2: near-realtime, polls every POLL_INTERVAL seconds.
    Mon-3: restart on crash handled by caller (Celery beat / management command).
    """

    def __init__(self):
        self._source = get_source()
        self._tracker = TransitionTracker()
        self._stats = get_stats_backend()
        self._detector = AnomalyDetector(self._stats)
        self._last_timestamp: datetime | None = None
        cfg = getattr(settings, "AUTOFIXER", {})
        self._prefix = cfg.get("REDIS_KEY_PREFIX", "autofixer")

    def _get_last_offset(self) -> datetime | None:
        from core.redis import redis_client

        key = f"{self._prefix}:monitor:last_offset"
        val = redis_client.get(key)
        if val:
            try:
                return datetime.fromisoformat(val.decode())
            except Exception:
                pass
        return None

    def _set_last_offset(self, ts: datetime) -> None:
        from core.redis import redis_client

        key = f"{self._prefix}:monitor:last_offset"
        redis_client.set(key, ts.isoformat())

    def run_once(self) -> None:
        """Process one batch of logs (one poll cycle)."""
        since = self._get_last_offset()
        max_ts = since
        # tr_id -> (start_ts, process_class, action_name) from Start event
        transition_meta: dict[str, tuple[datetime, str, str]] = {}
        already_fired: set[str] = set()

        for ts, message in self._source.fetch_logs(since=since, limit=10000):
            if max_ts is None or ts > max_ts:
                max_ts = ts

            event = parse_event(message, ts)
            if event is None:
                continue

            # Tracker: active transitions
            self._tracker.process_event(event, ts)
            if event.is_start:
                transition_meta[event.tr_id] = (
                    ts,
                    event.process_class or "",
                    event.action_name or "",
                )

            # Stats + anomaly: on completion (Unlock/Fail)
            if event.is_complete:
                meta = transition_meta.pop(event.tr_id, None)
                if meta:
                    start_ts, process_class, action_name = meta
                    if process_class and action_name:
                        duration = (ts - start_ts).total_seconds()
                        self._stats.record_duration(
                            process_class,
                            action_name,
                            duration,
                        )
                        anomaly = self._detector.check(
                            process_class,
                            action_name,
                            duration,
                        )
                        if anomaly:
                            logger.warning(
                                "Anomaly: %s.%s took %.2fs (threshold %.2fs)",
                                anomaly.process_class,
                                anomaly.action_name,
                                duration,
                                anomaly.threshold,
                            )
                            run_actions(anomaly, already_fired)

        if max_ts:
            self._set_last_offset(max_ts)
