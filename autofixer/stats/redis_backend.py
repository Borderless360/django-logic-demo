"""Redis stats backend with 30-day TTL (S-2, S-3)."""

from django.conf import settings

from autofixer.stats.base import StatsBackend


class RedisStatsBackend(StatsBackend):
    """Store stats in Redis with 30-day TTL."""

    TTL_DAYS = 30

    def __init__(self):
        from core.redis import redis_client

        self._redis = redis_client
        cfg = getattr(settings, "AUTOFIXER", {})
        self._prefix = cfg.get("REDIS_KEY_PREFIX", "autofixer")
        self._window = int(cfg.get("STATS_WINDOW_SIZE", 1000))

    def _key(self, process_class: str, action_name: str) -> str:
        return f"{self._prefix}:stats:{process_class}:{action_name}"

    def record_duration(
        self,
        process_class: str,
        action_name: str,
        duration_seconds: float,
    ) -> None:
        """Append duration to a sorted list, trim to window, set TTL."""
        key = self._key(process_class, action_name)
        pipe = self._redis.pipeline()
        pipe.lpush(key, duration_seconds)
        pipe.ltrim(key, 0, self._window - 1)
        pipe.expire(key, self.TTL_DAYS * 24 * 3600)
        pipe.execute()

    def get_stats(
        self,
        process_class: str,
        action_name: str,
        limit: int = 1000,
    ) -> tuple[list[float], int]:
        """Get recent durations (newest first in list)."""
        key = self._key(process_class, action_name)
        raw = self._redis.lrange(key, 0, limit - 1)
        durations = [float(x) for x in raw]
        total = self._redis.llen(key)
        return (durations, total)
