from abc import ABC, abstractmethod

from autofixer.detector import Anomaly


class BaseAlert(ABC):
    """Abstract base class for alert delivery mechanisms."""

    @abstractmethod
    def send(self, anomaly: Anomaly, **kwargs) -> None:
        ...
