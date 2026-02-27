from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from autofixer.events import Anomaly

logger = logging.getLogger("autofixer")


class EmailAlert:
    def send(self, *, anomaly: Anomaly, config: dict) -> None:
        recipients = config.get("recipients", [])
        if not recipients:
            return
        subject = f"[Autofixer] Anomaly detected: {anomaly.metric_key}"
        message = (
            f"Kind: {anomaly.kind}\n"
            f"Metric: {anomaly.metric_key}\n"
            f"Observed: {anomaly.observed:.3f}s\n"
            f"Mean: {anomaly.mean:.3f}s\n"
            f"StdDev: {anomaly.std_dev:.3f}\n"
            f"Threshold: {anomaly.threshold:.3f}s\n"
            f"Details: {anomaly.details}\n"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost"),
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info("Email alert sent for %s", anomaly.metric_key)

