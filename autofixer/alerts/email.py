import logging

from django.core.mail import send_mail

from autofixer.alerts.base import BaseAlert
from autofixer.detector import Anomaly

logger = logging.getLogger('autofixer')


class EmailAlert(BaseAlert):
    """Send anomaly alerts via Django's email backend."""

    def __init__(self, recipients: list[str], from_email: str | None = None):
        self.recipients = recipients
        self.from_email = from_email

    def send(self, anomaly: Anomaly, **kwargs) -> None:
        subject = (
            f'[autofixer] {anomaly.anomaly_type}: '
            f'{anomaly.process_class}.{anomaly.action_name}'
        )
        body = (
            f'Anomaly detected: {anomaly.anomaly_type}\n'
            f'Process: {anomaly.process_class}\n'
            f'Action: {anomaly.action_name}\n'
            f'Instance: {anomaly.instance_key}\n'
            f'Duration: {anomaly.duration_seconds:.2f}s\n'
            f'Threshold: {anomaly.threshold:.2f}s '
            f'(mean={anomaly.mean:.2f}, std_dev={anomaly.std_dev:.2f})\n'
            f'Root ID: {anomaly.root_id}\n'
        )
        try:
            send_mail(
                subject, body, self.from_email, self.recipients,
                fail_silently=False,
            )
        except Exception:
            logger.exception('Failed to send email alert')
