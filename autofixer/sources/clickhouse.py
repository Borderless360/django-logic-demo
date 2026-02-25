import logging
from datetime import datetime, timezone

from autofixer.events import TransitionEvent, parse_log_message
from autofixer.sources.base import BaseLogSource

logger = logging.getLogger('autofixer')


class ClickHouseLogSource(BaseLogSource):
    """Reads django-logic.transition logs from the ClickHouse ``logs`` table."""

    LOGGER_NAME = 'django-logic.transition'

    def __init__(self):
        from clickhouse.client import client
        self._client = client

    def fetch_events(
        self, since: datetime, limit: int = 1000
    ) -> list[TransitionEvent]:
        query = (
            "SELECT message, created, _timestamp "
            "FROM logs "
            "WHERE name = {logger_name:String} "
            "  AND _timestamp > {since:DateTime64(3)} "
            "ORDER BY _timestamp ASC "
            "LIMIT {limit:UInt32}"
        )
        params = {
            'logger_name': self.LOGGER_NAME,
            'since': since,
            'limit': limit,
        }
        try:
            result = self._client.query(query, parameters=params)
        except Exception:
            logger.exception('Failed to fetch logs from ClickHouse')
            return []

        events: list[TransitionEvent] = []
        for row in result.result_rows:
            message, created, _timestamp = row
            ts = created if created else _timestamp
            if ts and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            event = parse_log_message(message, ts)
            if event is not None:
                events.append(event)
        return events

    def get_latest_timestamp(self) -> datetime | None:
        query = (
            "SELECT max(_timestamp) "
            "FROM logs "
            "WHERE name = {logger_name:String}"
        )
        try:
            result = self._client.query(
                query, parameters={'logger_name': self.LOGGER_NAME}
            )
            row = result.result_rows
            if row and row[0][0]:
                ts = row[0][0]
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
        except Exception:
            logger.exception('Failed to get latest timestamp from ClickHouse')
        return None
