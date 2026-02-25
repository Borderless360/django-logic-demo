from abc import ABC, abstractmethod
from datetime import datetime

from autofixer.events import TransitionEvent


class BaseLogSource(ABC):
    """Abstract base class for log sources.

    Implement this to support sources other than ClickHouse
    (e.g. Kafka, file-based logs, Elasticsearch).
    """

    @abstractmethod
    def fetch_events(
        self, since: datetime, limit: int = 1000
    ) -> list[TransitionEvent]:
        """Return transition events newer than *since*, ordered by time ascending."""
        ...

    @abstractmethod
    def get_latest_timestamp(self) -> datetime | None:
        """Return the timestamp of the most recent available log entry, or None."""
        ...
