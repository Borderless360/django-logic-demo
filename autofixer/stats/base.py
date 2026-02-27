from __future__ import annotations

from typing import Protocol


class StatsBackend(Protocol):
    def add_sample(self, metric_key: str, duration_seconds: float) -> None:
        raise NotImplementedError

    def get_samples(self, metric_key: str) -> list[float]:
        raise NotImplementedError

