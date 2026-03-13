import logging

from celery import shared_task
from core.redis import redis_client

from django_logic_monitoring.actions import detect_anomaly, fetch_logs
from django_logic_monitoring.config import DLM_MONITORING_DELAY

logger = logging.getLogger("django_logic_monitoring")

LOCK_KEY = "dlm:monitoring:lock"
LOCK_TTL = DLM_MONITORING_DELAY * 30


@shared_task(name="django_logic_monitoring.monitoring")
def monitoring():
    acquired = redis_client.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL)
    if not acquired:
        logger.debug("Monitoring task already running, skipping")
        return
    try:
        fetch_logs()
        detect_anomaly()
    finally:
        redis_client.delete(LOCK_KEY)
