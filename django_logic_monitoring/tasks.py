from celery import shared_task

from django_logic_monitoring.actions import detect_anomaly, fetch_logs


@shared_task(name="django_logic_monitoring.monitoring")
def monitoring():
    fetch_logs()
    detect_anomaly()
