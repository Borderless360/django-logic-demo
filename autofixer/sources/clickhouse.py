"""ClickHouse log source (SRC-2: default source)."""

from datetime import datetime
from typing import Iterator

from django.conf import settings

from autofixer.sources.base import LogSource


class ClickHouseSource(LogSource):
    """Fetch django-logic logs from ClickHouse."""

    def __init__(self):
        from clickhouse.client import client

        self._client = client
        self._table = getattr(
            settings,
            "AUTOFIXER_CLICKHOUSE_TABLE",
            "logs",
        )

    def fetch_logs(
        self,
        since: datetime | None = None,
        limit: int = 10000,
    ) -> Iterator[tuple[datetime, str]]:
        """Fetch logs from ClickHouse, ordered by _timestamp."""
        # Build query (since is from our code, formatted safely)
        where = "name = 'django-logic.transition'"
        if since:
            ts = since.strftime("%Y-%m-%d %H:%M:%S")
            where += f" AND _timestamp >= '{ts}'"
        query = f"""
            SELECT _timestamp, message
            FROM {self._table}
            WHERE {where}
            ORDER BY _timestamp ASC, created ASC
            LIMIT {min(limit, 10000)}
        """
        result = self._client.query(query)
        if not result.result_rows:
            return

        for row in result.result_rows:
            ts, msg = row[0], row[1]
            if msg:
                yield (ts, msg)
