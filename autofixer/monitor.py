"""Main monitoring orchestrator.

Ties together the log source, tracker, stats backend, anomaly detector,
and alert dispatchers into a single ``Monitor.tick()`` loop.
"""

import logging
from datetime import datetime, timezone

from autofixer.alerts.base import BaseAlert
from autofixer.alerts.email import EmailAlert
from autofixer.alerts.webhook import WebhookAlert
from autofixer.config import get_config
from autofixer.detector import Anomaly, AnomalyDetector
from autofixer.models import AlertConfig
from autofixer.sources.base import BaseLogSource
from autofixer.sources.clickhouse import ClickHouseLogSource
from autofixer.stats.base import BaseStatsBackend, StatsEntry
from autofixer.stats.clickhouse_backend import ClickHouseStatsBackend
from autofixer.stats.redis_backend import RedisStatsBackend
from autofixer.tracker import Tracker

logger = logging.getLogger('autofixer')


def _build_log_source() -> BaseLogSource:
    source_name = get_config('LOG_SOURCE')
    if source_name == 'clickhouse':
        return ClickHouseLogSource()
    from django.utils.module_loading import import_string
    return import_string(source_name)()


def _build_stats_backend() -> BaseStatsBackend:
    backend_name = get_config('STATS_BACKEND')
    if backend_name == 'redis':
        return RedisStatsBackend()
    if backend_name == 'clickhouse':
        return ClickHouseStatsBackend()
    from django.utils.module_loading import import_string
    return import_string(backend_name)()


class Monitor:
    """Performs a single monitoring cycle on each ``tick()`` call."""

    def __init__(
        self,
        source: BaseLogSource | None = None,
        tracker: Tracker | None = None,
        stats: BaseStatsBackend | None = None,
    ):
        self.source = source or _build_log_source()
        self.tracker = tracker or Tracker()
        self.stats = stats or _build_stats_backend()
        self.detector = AnomalyDetector(self.stats)

    # -- main entry point ----------------------------------------------------

    def tick(self) -> None:
        """Run one monitoring cycle: fetch → process → detect → alert."""
        checkpoint = self.tracker.get_checkpoint()
        events = self.source.fetch_events(since=checkpoint)

        latest_ts = checkpoint
        for event in events:
            completed_at = self.tracker.handle_event(event)

            if completed_at is not None:
                self._on_transition_done(completed_at)

            if event.timestamp and event.timestamp > latest_ts:
                latest_ts = event.timestamp

        if latest_ts > checkpoint:
            self.tracker.set_checkpoint(latest_ts)

        self._check_stuck_transitions()

    # -- internal helpers ----------------------------------------------------

    def _on_transition_done(self, at) -> None:
        """Record stats and check for slow-completion anomalies."""
        duration = at.duration_seconds()
        if duration is None:
            return

        entry = StatsEntry(
            process_class=at.process_class,
            action_name=at.action_name,
            duration_seconds=duration,
            status=at.status,
            instance_key=at.instance_key,
            root_id=at.root_id,
        )

        anomaly = self.detector.check_completed(entry)

        # Record *after* anomaly check so the current value doesn't skew
        # the statistics that were used for comparison.
        self.stats.record(entry)

        if anomaly:
            self._dispatch_alert(anomaly)

    def _check_stuck_transitions(self) -> None:
        threshold = get_config('STUCK_TRANSITION_SECONDS')
        stuck = self.tracker.get_stuck_transitions(threshold)
        for at in stuck:
            anomaly = self.detector.check_stuck(at)
            if anomaly:
                self._dispatch_alert(anomaly)

    def _dispatch_alert(self, anomaly: Anomaly) -> None:
        configs = AlertConfig.objects.filter(is_active=True)
        for cfg in configs:
            if not cfg.matches(anomaly.process_class, anomaly.action_name):
                continue
            alert = self._alert_from_config(cfg)
            if alert:
                try:
                    alert.send(anomaly)
                except Exception:
                    logger.exception('Alert dispatch failed for config %s', cfg.name)

    @staticmethod
    def _alert_from_config(cfg: AlertConfig) -> BaseAlert | None:
        if cfg.alert_type == 'email':
            recipients = [
                e.strip() for e in cfg.email_recipients.split(',') if e.strip()
            ]
            if not recipients:
                return None
            return EmailAlert(recipients=recipients, from_email=cfg.email_from or None)

        if cfg.alert_type == 'webhook':
            if not cfg.webhook_url:
                return None
            return WebhookAlert(
                url=cfg.webhook_url,
                headers=cfg.webhook_headers or None,
            )

        return None
