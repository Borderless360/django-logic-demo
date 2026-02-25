import math
import logging
from datetime import datetime, timezone

from autofixer.config import get_config
from autofixer.stats.base import BaseStatsBackend, StatsEntry, StatsSummary

logger = logging.getLogger('autofixer')


class ClickHouseStatsBackend(BaseStatsBackend):
    """Stores execution time stats in a dedicated ClickHouse table."""

    def __init__(self):
        from clickhouse.client import client
        self._client = client

    @property
    def _table(self) -> str:
        return get_config('CLICKHOUSE_STATS_TABLE')

    def record(self, entry: StatsEntry) -> None:
        try:
            self._client.insert(
                self._table,
                [[
                    entry.process_class,
                    entry.action_name,
                    entry.duration_seconds,
                    entry.status,
                    entry.instance_key,
                    entry.root_id,
                    datetime.now(timezone.utc),
                ]],
                column_names=[
                    'process_class', 'action_name', 'duration_seconds',
                    'status', 'instance_key', 'root_id', '_timestamp',
                ],
            )
        except Exception:
            logger.exception('Failed to record stats in ClickHouse')

    def get_summary(self, process_class: str, action_name: str) -> StatsSummary | None:
        window = get_config('STATS_WINDOW_SIZE')
        query = (
            "SELECT "
            "  count() AS cnt, "
            "  avg(duration_seconds) AS mean, "
            "  stddevPop(duration_seconds) AS sd, "
            "  min(duration_seconds) AS min_val, "
            "  max(duration_seconds) AS max_val "
            f"FROM (SELECT duration_seconds FROM {self._table} "
            "  WHERE process_class = {pc:String} "
            "    AND action_name = {an:String} "
            "  ORDER BY _timestamp DESC "
            "  LIMIT {lim:UInt32})"
        )
        try:
            result = self._client.query(query, parameters={
                'pc': process_class,
                'an': action_name,
                'lim': window,
            })
            if not result.result_rows:
                return None
            row = result.result_rows[0]
            cnt, mean, sd, mn, mx = row
            if cnt == 0:
                return None
            return StatsSummary(
                process_class=process_class,
                action_name=action_name,
                count=int(cnt),
                mean=float(mean),
                std_dev=float(sd),
                min_val=float(mn),
                max_val=float(mx),
            )
        except Exception:
            logger.exception('Failed to get stats summary from ClickHouse')
            return None
