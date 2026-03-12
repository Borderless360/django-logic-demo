import pytest
from core.redis import redis_client

DLM_KEYS_PATTERN = "dlm:*"


@pytest.fixture(autouse=True)
def clean_redis():
    """Wipe all dlm:* keys before and after each test."""
    _flush_dlm_keys()
    yield
    _flush_dlm_keys()


def _flush_dlm_keys():
    keys = redis_client.keys(DLM_KEYS_PATTERN)
    if keys:
        redis_client.delete(*keys)
