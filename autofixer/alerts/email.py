"""Email alert action (Action-1)."""

import logging

from django.core.mail import send_mail
from django.conf import settings

from autofixer.alerts.base import AlertAction
from autofixer.detector import Anomaly

logger = logging.getLogger("autofixer")


class EmailAlert(AlertAction):
    """Send email on anomaly."""

    def __init__(self, recipients: list[str] | None = None, subject_prefix: str = "[Autofixer]"):
        self.recipients = recipients or []
        self.subject_prefix = subject_prefix

    def execute(self, anomaly: Anomaly) -> None:
        if not self.recipients:
            logger.warning("EmailAlert: no recipients configured, skipping")
            return
        subject = f"{self.subject_prefix} Anomaly: {anomaly.process_class}.{anomaly.action_name}"
        body = (
            f"Anomaly detected:\n"
            f"  Process: {anomaly.process_class}\n"
            f"  Action: {anomaly.action_name}\n"
            f"  Duration: {anomaly.duration_seconds:.2f}s\n"
            f"  Mean: {anomaly.mean:.2f}s, Std: {anomaly.std:.2f}s\n"
            f"  Threshold: {anomaly.threshold:.2f}s\n"
            f"  Samples: {anomaly.sample_count}\n"
        )
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=self.recipients,
                fail_silently=False,
            )
            logger.info("Sent anomaly email to %s", self.recipients)
        except Exception as e:
            logger.exception("Failed to send anomaly email: %s", e)
