from __future__ import annotations

from statistics import mean, pstdev

from autofixer.events import Anomaly


class AnomalyDetector:
    def __init__(self, *, std_dev_multiplier: float, min_samples: int) -> None:
        self.std_dev_multiplier = float(std_dev_multiplier)
        self.min_samples = int(min_samples)

    def detect(self, *, kind: str, metric_key: str, observed: float, samples: list[float], fingerprint: str, details: dict) -> Anomaly | None:
        if len(samples) < self.min_samples:
            return None
        avg = mean(samples)
        std = pstdev(samples)
        threshold = avg + (self.std_dev_multiplier * std)
        if observed <= threshold:
            return None
        return Anomaly(
            kind=kind,
            metric_key=metric_key,
            observed=observed,
            mean=avg,
            std_dev=std,
            threshold=threshold,
            fingerprint=fingerprint,
            details=details,
        )

