from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class AutofixerSettings:
    log_source: str
    stats_backend: str
    poll_interval: int
    lock_timeout: int
    anomaly_std_dev_multiplier: float
    anomaly_min_samples: int
    stats_window_size: int
    redis_key_prefix: str
    stuck_transition_seconds: int
    action_config: list[dict]


DEFAULTS = {
    "LOG_SOURCE": "clickhouse",
    "STATS_BACKEND": "redis",
    "POLL_INTERVAL": 5,
    "LOCK_TIMEOUT": 30,
    "ANOMALY_STD_DEV_MULTIPLIER": 2.0,
    "ANOMALY_MIN_SAMPLES": 5,
    "STATS_WINDOW_SIZE": 1000,
    "REDIS_KEY_PREFIX": "autofixer",
    "STUCK_TRANSITION_SECONDS": 300,
    "ACTION_CONFIG": [],
}


def get_autofixer_settings() -> AutofixerSettings:
    raw = {**DEFAULTS, **getattr(settings, "AUTOFIXER", {})}
    return AutofixerSettings(
        log_source=raw["LOG_SOURCE"],
        stats_backend=raw["STATS_BACKEND"],
        poll_interval=int(raw["POLL_INTERVAL"]),
        lock_timeout=int(raw["LOCK_TIMEOUT"]),
        anomaly_std_dev_multiplier=float(raw["ANOMALY_STD_DEV_MULTIPLIER"]),
        anomaly_min_samples=int(raw["ANOMALY_MIN_SAMPLES"]),
        stats_window_size=int(raw["STATS_WINDOW_SIZE"]),
        redis_key_prefix=str(raw["REDIS_KEY_PREFIX"]),
        stuck_transition_seconds=int(raw["STUCK_TRANSITION_SECONDS"]),
        action_config=list(raw.get("ACTION_CONFIG", [])),
    )

