"""Abstract log source interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterator

from autofixer.events import LogEvent


class LogSource(ABC):
    """Abstract source of django-logic transition logs (SRC-1)."""

    @abstractmethod
    def fetch_logs(
        self,
        since: datetime | None = None,
        limit: int = 10000,
    ) -> Iterator[tuple[datetime, str]]:
        """
        Fetch logs since the given timestamp.
        Yields (timestamp, message) tuples.
        """
        ...
