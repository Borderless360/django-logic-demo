"""
ActionConfig (AC-1, AC-2, AC-3): actions configured in django settings.
One anomaly can trigger multiple actions; each action runs only once per anomaly.
"""

import logging
from django.conf import settings

from autofixer.alerts.base import AlertAction
from autofixer.alerts.email import EmailAlert
from autofixer.alerts.webhook import WebhookAlert
from autofixer.detector import Anomaly

logger = logging.getLogger("autofixer")


def get_action_config() -> list[tuple[str, list[AlertAction]]]:
    """
    Load ActionConfig from settings (AC-1).
    Returns list of (anomaly_key, [actions]) where anomaly_key = process_class:action_name.
    AC-2: multiple actions per anomaly.
    """
    cfg = getattr(settings, "AUTOFIXER", {})
    action_config = cfg.get("ACTION_CONFIG", [])
    result: list[tuple[str, list[AlertAction]]] = []

    for item in action_config:
        pattern = item.get("pattern", "*:*")  # process_class:action_name or * for wildcard
        actions_cfg = item.get("actions", [])
        actions: list[AlertAction] = []
        for a in actions_cfg:
            if a.get("type") == "email":
                actions.append(
                    EmailAlert(
                        recipients=a.get("recipients", []),
                        subject_prefix=a.get("subject_prefix", "[Autofixer]"),
                    )
                )
            elif a.get("type") == "webhook":
                actions.append(
                    WebhookAlert(
                        url=a.get("url", ""),
                        method=a.get("method", "POST"),
                        headers=a.get("headers"),
                    )
                )
        if actions:
            result.append((pattern, actions))
    return result


def anomaly_key(process_class: str, action_name: str) -> str:
    return f"{process_class}:{action_name}"


def matches_pattern(pattern: str, process_class: str, action_name: str) -> bool:
    """Check if process_class:action_name matches pattern (supports * wildcard)."""
    key = anomaly_key(process_class, action_name)
    if "*" in pattern:
        parts = pattern.split(":")
        pc_pat = parts[0] if len(parts) > 0 else "*"
        ac_pat = parts[1] if len(parts) > 1 else "*"
        if pc_pat != "*" and pc_pat != process_class:
            return False
        if ac_pat != "*" and ac_pat != action_name:
            return False
        return True
    return key == pattern


def run_actions(anomaly: Anomaly, already_fired: set[str]) -> None:
    """
    Run configured actions for anomaly (AC-3: each action once per anomaly).
    already_fired: set of anomaly keys we've already acted on (idempotent per detection run).
    """
    key = anomaly_key(anomaly.process_class, anomaly.action_name)
    if key in already_fired:
        return

    config = get_action_config()
    for pattern, actions in config:
        if matches_pattern(pattern, anomaly.process_class, anomaly.action_name):
            for action in actions:
                try:
                    action.execute(anomaly)
                except Exception as e:
                    logger.exception("Action failed: %s", e)
            already_fired.add(key)
            break
