from __future__ import annotations

from autofixer.stats.base import StatsBackend
from core.redis import redis_client


class RedisStatsBackend(StatsBackend):
    def __init__(self, *, key_prefix: str, window_size: int, ttl_seconds: int, redis=None) -> None:
        self.key_prefix = key_prefix
        self.window_size = int(window_size)
        self.ttl_seconds = int(ttl_seconds)
        self.redis = redis or redis_client

    def add_sample(self, metric_key: str, duration_seconds: float) -> None:
        key = self._samples_key(metric_key)
        pipe = self.redis.pipeline()
        pipe.lpush(key, str(float(duration_seconds)))
        pipe.ltrim(key, 0, self.window_size - 1)
        pipe.expire(key, self.ttl_seconds)
        pipe.execute()

    def get_samples(self, metric_key: str) -> list[float]:
        values = self.redis.lrange(self._samples_key(metric_key), 0, self.window_size - 1)
        result: list[float] = []
        for value in values:
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            result.append(float(value))
        return result

    def _samples_key(self, metric_key: str) -> str:
        return f"{self.key_prefix}:stats:{metric_key}"

