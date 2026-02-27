from __future__ import annotations

from datetime import datetime
from typing import Protocol


class LogSource(Protocol):
    def fetch_logs(self, *, since: datetime | None, limit: int = 5000) -> list[dict]:
        raise NotImplementedError

