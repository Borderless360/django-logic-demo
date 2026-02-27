"""Abstract stats backend (S-1, S-2)."""

from abc import ABC, abstractmethod


class StatsBackend(ABC):
    """Store execution duration stats for transitions/actions (S-1)."""

    @abstractmethod
    def record_duration(
        self,
        process_class: str,
        action_name: str,
        duration_seconds: float,
    ) -> None:
        """Record a single execution duration."""
        ...

    @abstractmethod
    def get_stats(
        self,
        process_class: str,
        action_name: str,
        limit: int = 1000,
    ) -> tuple[list[float], int]:
        """Get recent durations. Returns (list of durations, total count)."""
        ...
