"""Celery task for autofixer tick (Mon-1, Mon-3)."""

import logging

from celery import shared_task

from autofixer.monitor import Monitor

logger = logging.getLogger("autofixer")


@shared_task(name="autofixer.tick")
def tick():
    """
    Celery beat task: run one monitor poll.
    Mon-3: Celery will auto-restart on crash.
    """
    try:
        monitor = Monitor()
        monitor.run_once()
    except Exception as e:
        logger.exception("Autofixer tick failed: %s", e)
        raise
