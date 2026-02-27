"""Abstract alert action (Action-1, Action-2)."""

from abc import ABC, abstractmethod

from autofixer.detector import Anomaly


class AlertAction(ABC):
    """Base for actions: email (Action-1), webhook (Action-2)."""

    @abstractmethod
    def execute(self, anomaly: Anomaly) -> None:
        """Execute the action for the given anomaly."""
        ...
