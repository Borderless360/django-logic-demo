from __future__ import annotations

import logging

import requests

from autofixer.events import Anomaly

logger = logging.getLogger("autofixer")


class WebhookAlert:
    def send(self, *, anomaly: Anomaly, config: dict) -> None:
        url = config.get("url")
        if not url:
            return
        timeout = float(config.get("timeout", 5))
        payload = {
            "kind": anomaly.kind,
            "metric_key": anomaly.metric_key,
            "observed": anomaly.observed,
            "mean": anomaly.mean,
            "std_dev": anomaly.std_dev,
            "threshold": anomaly.threshold,
            "details": anomaly.details,
        }
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        logger.info("Webhook alert sent for %s", anomaly.metric_key)

