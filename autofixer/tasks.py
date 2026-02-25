"""Celery tasks for the autofixer monitoring loop.

The ``autofixer_tick`` task is meant to be called periodically (e.g. every 5 s
via Celery Beat).  A Redis lock guarantees that only **one** tick runs at a
time across all workers, satisfying the "single listener" requirement.
"""

import logging

from celery import shared_task
from core.redis import redis_client
from autofixer.config import get_config

logger = logging.getLogger('autofixer')

LOCK_KEY_SUFFIX = ':monitor_lock'


def _lock_key() -> str:
    return f'{get_config("REDIS_KEY_PREFIX")}{LOCK_KEY_SUFFIX}'


@shared_task(name='autofixer.tick', ignore_result=True)
def autofixer_tick():
    """Single monitoring cycle, protected by a distributed lock."""
    lock_timeout = get_config('LOCK_TIMEOUT')
    lock = redis_client.lock(_lock_key(), timeout=lock_timeout, blocking=False)

    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.debug('autofixer_tick skipped — another instance holds the lock')
        return

    try:
        from autofixer.monitor import Monitor
        monitor = Monitor()
        monitor.tick()
    except Exception:
        logger.exception('autofixer_tick failed')
    finally:
        try:
            lock.release()
        except Exception:
            pass
