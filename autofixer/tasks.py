from __future__ import annotations

import logging

from celery import shared_task

from autofixer.monitor import get_monitor

logger = logging.getLogger("autofixer")


@shared_task(name="autofixer.tick", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 5})
def tick() -> dict:
    result = get_monitor().tick()
    logger.info("Autofixer tick result: %s", result)
    return result

