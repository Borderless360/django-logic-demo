"""
Anomaly detector (Anom-1): long execution based on past stats.
Deviation > 2σ from mean, minimum 5 records.
"""

import math
from dataclasses import dataclass

from django.conf import settings

from autofixer.stats.base import StatsBackend


@dataclass
class Anomaly:
    """Detected anomaly."""

    process_class: str
    action_name: str
    duration_seconds: float
    mean: float
    std: float
    sample_count: int
    threshold: float  # mean + multiplier * std


class AnomalyDetector:
    """
    Detect anomalies: execution time > 2σ from mean (Anom-1).
    Requires at least 5 samples.
    """

    def __init__(self, stats: StatsBackend):
        self._stats = stats
        cfg = getattr(settings, "AUTOFIXER", {})
        self._multiplier = float(cfg.get("ANOMALY_STD_DEV_MULTIPLIER", 2.0))
        self._min_samples = int(cfg.get("ANOMALY_MIN_SAMPLES", 5))

    def check(
        self,
        process_class: str,
        action_name: str,
        duration_seconds: float,
    ) -> Anomaly | None:
        """
        Check if duration is anomalous.
        Returns Anomaly if anomaly detected, else None.
        """
        durations, total = self._stats.get_stats(process_class, action_name)
        if total < self._min_samples:
            return None

        n = len(durations)
        if n == 0:
            return None

        mean = sum(durations) / n
        variance = sum((x - mean) ** 2 for x in durations) / n
        std = math.sqrt(variance) if variance > 0 else 0.0
        threshold = mean + self._multiplier * std

        if duration_seconds > threshold:
            return Anomaly(
                process_class=process_class,
                action_name=action_name,
                duration_seconds=duration_seconds,
                mean=mean,
                std=std,
                sample_count=total,
                threshold=threshold,
            )
        return None
