import json
import math
import logging

from core.redis import redis_client
from autofixer.config import get_config
from autofixer.stats.base import BaseStatsBackend, StatsEntry, StatsSummary

logger = logging.getLogger('autofixer')


class RedisStatsBackend(BaseStatsBackend):
    """Stores execution time stats in Redis as capped lists."""

    def __init__(self, redis=None):
        self.r = redis or redis_client

    def _key(self, process_class: str, action_name: str) -> str:
        prefix = get_config('REDIS_KEY_PREFIX')
        return f'{prefix}:stats:{process_class}:{action_name}'

    def record(self, entry: StatsEntry) -> None:
        key = self._key(entry.process_class, entry.action_name)
        window = get_config('STATS_WINDOW_SIZE')
        pipe = self.r.pipeline()
        pipe.rpush(key, json.dumps({
            'd': entry.duration_seconds,
            's': entry.status,
            'i': entry.instance_key,
        }))
        pipe.ltrim(key, -window, -1)
        pipe.execute()

    def get_summary(self, process_class: str, action_name: str) -> StatsSummary | None:
        key = self._key(process_class, action_name)
        raw_list = self.r.lrange(key, 0, -1)
        if not raw_list:
            return None

        durations: list[float] = []
        for raw in raw_list:
            try:
                item = json.loads(raw)
                durations.append(float(item['d']))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        if not durations:
            return None

        n = len(durations)
        mean = sum(durations) / n
        variance = sum((d - mean) ** 2 for d in durations) / n if n > 1 else 0.0
        std_dev = math.sqrt(variance)

        return StatsSummary(
            process_class=process_class,
            action_name=action_name,
            count=n,
            mean=mean,
            std_dev=std_dev,
            min_val=min(durations),
            max_val=max(durations),
        )
