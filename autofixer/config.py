from django.conf import settings

DEFAULTS = {
    'LOG_SOURCE': 'clickhouse',
    'STATS_BACKEND': 'redis',
    'POLL_INTERVAL': 5,
    'LOCK_TIMEOUT': 30,
    'ANOMALY_STD_DEV_MULTIPLIER': 3.0,
    'ANOMALY_MIN_SAMPLES': 10,
    'STATS_WINDOW_SIZE': 1000,
    'REDIS_KEY_PREFIX': 'autofixer',
    'CLICKHOUSE_STATS_TABLE': 'transition_stats',
    'STUCK_TRANSITION_SECONDS': 300,
}


def get_config(key):
    user_config = getattr(settings, 'AUTOFIXER', {})
    return user_config.get(key, DEFAULTS[key])
