import json
import logging
from dataclasses import asdict

import requests

from autofixer.alerts.base import BaseAlert
from autofixer.detector import Anomaly

logger = logging.getLogger('autofixer')


class WebhookAlert(BaseAlert):
    """Send anomaly alerts to an HTTP webhook endpoint."""

    def __init__(self, url: str, headers: dict | None = None, timeout: int = 10):
        self.url = url
        self.headers = headers or {'Content-Type': 'application/json'}
        self.timeout = timeout

    def send(self, anomaly: Anomaly, **kwargs) -> None:
        payload = asdict(anomaly)
        try:
            resp = requests.post(
                self.url,
                data=json.dumps(payload),
                headers=self.headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except Exception:
            logger.exception('Failed to send webhook alert to %s', self.url)
