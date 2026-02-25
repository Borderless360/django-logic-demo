"""Management command alternative to Celery Beat.

Usage:
    python manage.py run_autofixer

Runs the monitoring loop in the foreground with a configurable poll interval.
Uses the same Redis lock as the Celery task to guarantee singleton behaviour.
"""

import signal
import time
import logging

from django.core.management.base import BaseCommand
from redis.exceptions import LockNotOwnedError

from core.redis import redis_client
from autofixer.config import get_config
from autofixer.monitor import Monitor

logger = logging.getLogger('autofixer')

LOCK_KEY_SUFFIX = ':monitor_lock'


class Command(BaseCommand):
    help = 'Run the autofixer monitoring loop (alternative to Celery Beat)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=None,
            help='Poll interval in seconds (default: AUTOFIXER.POLL_INTERVAL)',
        )

    def handle(self, *args, **options):
        interval = options['interval'] or get_config('POLL_INTERVAL')
        lock_key = f'{get_config("REDIS_KEY_PREFIX")}{LOCK_KEY_SUFFIX}'
        lock_timeout = max(interval * 10, get_config('LOCK_TIMEOUT'))

        self._running = True
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

        lock = redis_client.lock(lock_key, timeout=lock_timeout)
        acquired = lock.acquire(blocking_timeout=5)
        if not acquired:
            self.stderr.write('Another autofixer instance is already running.')
            return

        self.stdout.write(f'autofixer started (interval={interval}s)')

        monitor = Monitor()
        try:
            while self._running:
                try:
                    monitor.tick()
                    lock.reacquire()
                except LockNotOwnedError:
                    logger.warning(
                        'Lock expired (tick took longer than %ds), re-acquiring',
                        lock_timeout,
                    )
                    lock = redis_client.lock(lock_key, timeout=lock_timeout)
                    if not lock.acquire(blocking_timeout=5):
                        logger.error('Failed to re-acquire lock, exiting')
                        break
                except Exception:
                    logger.exception('autofixer tick error')
                time.sleep(interval)
        finally:
            try:
                lock.release()
            except Exception:
                pass
            self.stdout.write('autofixer stopped')

    def _stop(self, signum, frame):
        self._running = False
