from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StatsEntry:
    process_class: str
    action_name: str
    duration_seconds: float
    status: str  # 'completed' or 'failed'
    instance_key: str = ''
    root_id: str = ''


@dataclass
class StatsSummary:
    process_class: str
    action_name: str
    count: int
    mean: float
    std_dev: float
    min_val: float
    max_val: float


class BaseStatsBackend(ABC):
    """Abstract interface for storing and querying execution statistics."""

    @abstractmethod
    def record(self, entry: StatsEntry) -> None:
        """Record a single execution measurement."""
        ...

    @abstractmethod
    def get_summary(self, process_class: str, action_name: str) -> StatsSummary | None:
        """Return aggregated stats for a given (process_class, action_name) pair."""
        ...
