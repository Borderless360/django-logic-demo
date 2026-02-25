"""Anomaly detection based on execution-time statistics."""

import logging
from dataclasses import dataclass

from autofixer.config import get_config
from autofixer.stats.base import BaseStatsBackend, StatsEntry, StatsSummary
from autofixer.tracker import ActiveTransition

logger = logging.getLogger('autofixer')


@dataclass
class Anomaly:
    process_class: str
    action_name: str
    instance_key: str
    root_id: str
    duration_seconds: float
    mean: float
    std_dev: float
    threshold: float
    anomaly_type: str  # 'slow_completion' or 'stuck'


class AnomalyDetector:
    """Detects anomalous execution times using mean + N*stddev threshold."""

    def __init__(self, stats_backend: BaseStatsBackend):
        self.stats = stats_backend

    def check_completed(self, entry: StatsEntry) -> Anomaly | None:
        """Check a newly completed transition for anomalous duration."""
        multiplier = get_config('ANOMALY_STD_DEV_MULTIPLIER')
        min_samples = get_config('ANOMALY_MIN_SAMPLES')

        summary = self.stats.get_summary(entry.process_class, entry.action_name)
        if summary is None or summary.count < min_samples:
            return None

        threshold = summary.mean + multiplier * summary.std_dev
        if entry.duration_seconds > threshold:
            return Anomaly(
                process_class=entry.process_class,
                action_name=entry.action_name,
                instance_key=entry.instance_key,
                root_id=entry.root_id,
                duration_seconds=entry.duration_seconds,
                mean=summary.mean,
                std_dev=summary.std_dev,
                threshold=threshold,
                anomaly_type='slow_completion',
            )
        return None

    def check_stuck(self, transition: ActiveTransition) -> Anomaly | None:
        """Check whether a still-running transition has exceeded the stuck threshold."""
        stuck_seconds = get_config('STUCK_TRANSITION_SECONDS')
        multiplier = get_config('ANOMALY_STD_DEV_MULTIPLIER')

        duration = transition.duration_seconds()
        if duration is None:
            return None

        summary = self.stats.get_summary(
            transition.process_class, transition.action_name
        )

        if summary and summary.count >= get_config('ANOMALY_MIN_SAMPLES'):
            threshold = summary.mean + multiplier * summary.std_dev
        else:
            threshold = stuck_seconds

        if duration > threshold:
            return Anomaly(
                process_class=transition.process_class,
                action_name=transition.action_name,
                instance_key=transition.instance_key,
                root_id=transition.root_id,
                duration_seconds=duration,
                mean=summary.mean if summary else 0,
                std_dev=summary.std_dev if summary else 0,
                threshold=threshold,
                anomaly_type='stuck',
            )
        return None
