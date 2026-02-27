from __future__ import annotations

from typing import Protocol

from autofixer.events import Anomaly


class AlertAction(Protocol):
    def send(self, *, anomaly: Anomaly, config: dict) -> None:
        raise NotImplementedError

