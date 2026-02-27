"""Webhook alert action (Action-2)."""

import json
import logging

import requests

from autofixer.alerts.base import AlertAction
from autofixer.detector import Anomaly

logger = logging.getLogger("autofixer")


class WebhookAlert(AlertAction):
    """Call HTTP webhook on anomaly."""

    def __init__(self, url: str, method: str = "POST", headers: dict | None = None):
        self.url = url
        self.method = method.upper()
        self.headers = headers or {"Content-Type": "application/json"}

    def execute(self, anomaly: Anomaly) -> None:
        payload = {
            "anomaly": True,
            "process_class": anomaly.process_class,
            "action_name": anomaly.action_name,
            "duration_seconds": anomaly.duration_seconds,
            "mean": anomaly.mean,
            "std": anomaly.std,
            "threshold": anomaly.threshold,
            "sample_count": anomaly.sample_count,
        }
        try:
            resp = requests.request(
                method=self.method,
                url=self.url,
                data=json.dumps(payload),
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Webhook called: %s %s", self.method, self.url)
        except Exception as e:
            logger.exception("Webhook call failed: %s", e)
