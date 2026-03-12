import logging
from datetime import datetime

from django_logic_monitoring.config import DLM_DEFAULT_TIME_LIMIT, DLM_LOG_PAGE_SIZE
from django_logic_monitoring.logs import fetch_logs_since
from django_logic_monitoring.storage import (
    AnomalyStore,
    LastLogTimestamp,
    StatStore,
    TransitionStore,
)

logger = logging.getLogger("django_logic_monitoring")

STEP_EVENTS = {"SideEffect", "Callback", "FailureSideEffect"}
GROUP_EVENTS = {"SideEffects", "Callbacks", "FailureSideEffects"}
GROUP_TO_STEP = {
    "SideEffects": "SideEffect",
    "Callbacks": "Callback",
    "FailureSideEffects": "FailureSideEffect",
}


def _parse_log(message: str) -> dict | None:
    """Parse a transition log message into structured data."""
    if not message:
        return None

    parts = message.split(" ", 2)
    if len(parts) < 2:
        return None

    tr_id = parts[0]
    rest = message[len(tr_id) + 1:]

    if rest.startswith("Start "):
        tokens = rest.split(" ")
        if len(tokens) >= 6:
            return {
                "type": "Start",
                "tr_id": tr_id,
                "process": tokens[1],
                "action": tokens[2],
                "instance_key": tokens[3],
                "root_id": tokens[4],
                "parent_id": tokens[5],
            }

    for group_name in GROUP_EVENTS:
        if rest.startswith(group_name + " "):
            try:
                count = int(rest[len(group_name) + 1:])
            except ValueError:
                continue
            return {"type": group_name, "tr_id": tr_id, "count": count}

    for step_name in STEP_EVENTS:
        prefix = step_name + " "
        if rest.startswith(prefix):
            return {"type": step_name, "tr_id": tr_id, "name": rest[len(prefix):].strip()}

    if rest.startswith("Set State "):
        return {"type": "SetState", "tr_id": tr_id, "state": rest[len("Set State "):].strip()}

    stripped = rest.strip()
    if stripped == "Lock":
        return {"type": "Lock", "tr_id": tr_id}
    if stripped == "Unlock":
        return {"type": "Unlock", "tr_id": tr_id}
    if stripped == "Background Mode":
        return {"type": "BackgroundMode", "tr_id": tr_id}
    if stripped.startswith("Next Transition"):
        return {"type": "NextTransition", "tr_id": tr_id}

    if rest.startswith("Fail"):
        return {"type": "Fail", "tr_id": tr_id, "detail": rest}

    return {"type": "Unknown", "tr_id": tr_id, "raw": message}


def _parse_instance_key(instance_key: str):
    """Parse 'app_label-model_name-field_name-pk' into (model_name, field_name, object_id)."""
    parts = instance_key.split("-")
    if len(parts) < 4:
        return instance_key, "", ""
    app_label = parts[0]
    model_name = parts[1]
    field_name = parts[2]
    object_id = "-".join(parts[3:])
    return f"{app_label}.{model_name}", field_name, object_id


def _remove_completed_transitions():
    """Remove transitions that are fully completed (including children)."""
    all_transitions = TransitionStore.get_all()
    if not all_transitions:
        return

    by_id = {tr["id"]: tr for tr in all_transitions}
    children: dict[str, list[str]] = {}
    for tr in all_transitions:
        parent_id = tr.get("parent_id", "")
        if parent_id and parent_id != tr["id"]:
            children.setdefault(parent_id, []).append(tr["id"])

    def is_fully_completed(tr_id, visited=None):
        if visited is None:
            visited = set()
        if tr_id in visited:
            return True
        visited.add(tr_id)

        tr = by_id.get(tr_id)
        if not tr:
            return True
        if tr.get("is_completed") != "1":
            return False

        for child_id in children.get(tr_id, []):
            if not is_fully_completed(child_id, visited):
                return False
        return True

    to_remove = [tr["id"] for tr in all_transitions if is_fully_completed(tr["id"])]
    for tr_id in to_remove:
        TransitionStore.delete(tr_id)

    if to_remove:
        logger.info("Removed %d completed transitions", len(to_remove))


# ── Main Process Actions ─────────────────────────────────────────────────────


def fetch_logs():
    """Read logs page by page → update transitions → remove completed → update stats."""
    last_ts = LastLogTimestamp.get()

    total_processed = 0
    # {tr_id: {step_type, step_name, start_time}} — tracks the currently
    # executing step so we can compute its duration when the next event arrives.
    active_steps: dict[str, dict] = {}
    stat_updates: list[tuple] = []

    while True:
        page = fetch_logs_since(last_ts, limit=DLM_LOG_PAGE_SIZE)
        if not page:
            break

        is_last_page = len(page) < DLM_LOG_PAGE_SIZE

        # On a full page the LIMIT may split rows that share the boundary
        # timestamp.  Trim that trailing group so the next iteration re-fetches
        # all of them.  Skip the trim only when every row in the page already
        # shares the same timestamp (nothing to trim — process them all).
        if not is_last_page and page[0]["timestamp"] != page[-1]["timestamp"]:
            boundary_ts = page[-1]["timestamp"]
            page = [e for e in page if e["timestamp"] < boundary_ts]

        logger.info("Processing page of %d log entries", len(page))

        for entry in page:
            message = entry["message"]
            timestamp = entry["timestamp"]
            event = _parse_log(message)
            if not event:
                continue

            tr_id = event["tr_id"]

            if tr_id in active_steps:
                prev = active_steps.pop(tr_id)
                tr_data = TransitionStore.get(tr_id)
                if tr_data and prev["step_name"] and "process" in tr_data:
                    duration = (timestamp - prev["start_time"]).total_seconds()
                    if duration > 0:
                        stat_updates.append((
                            tr_data["process"],
                            tr_data.get("action", ""),
                            prev["step_type"],
                            prev["step_name"],
                            duration,
                        ))

            if event["type"] == "Start":
                model_name, field_name, object_id = _parse_instance_key(event["instance_key"])
                TransitionStore.create(
                    tr_id=tr_id,
                    process=event["process"],
                    action=event["action"],
                    model_name=model_name,
                    object_id=object_id,
                    field_name=field_name,
                    root_id=event["root_id"],
                    parent_id=event["parent_id"],
                    timestamp=timestamp,
                )

            elif event["type"] in GROUP_EVENTS:
                if TransitionStore.exists(tr_id):
                    TransitionStore.update(
                        tr_id,
                        steps=str(event["count"]),
                        step_type=GROUP_TO_STEP[event["type"]],
                        step_n="0",
                        timestamp=timestamp,
                    )

            elif event["type"] in STEP_EVENTS:
                if TransitionStore.exists(tr_id):
                    tr_data = TransitionStore.get(tr_id)
                    new_step_n = int(tr_data.get("step_n", "0")) + 1
                    TransitionStore.update(
                        tr_id,
                        step_n=str(new_step_n),
                        step_type=event["type"],
                        step_name=event["name"],
                        timestamp=timestamp,
                    )
                    active_steps[tr_id] = {
                        "step_type": event["type"],
                        "step_name": event["name"],
                        "start_time": timestamp,
                    }

            elif event["type"] == "Unlock":
                if TransitionStore.exists(tr_id):
                    TransitionStore.update(tr_id, is_completed=True, timestamp=timestamp)

            elif event["type"] == "Fail":
                if TransitionStore.exists(tr_id):
                    TransitionStore.update(tr_id, is_completed=True, timestamp=timestamp)

            elif event["type"] in ("SetState", "Lock", "BackgroundMode", "NextTransition"):
                if TransitionStore.exists(tr_id):
                    TransitionStore.update(tr_id, timestamp=timestamp)

        total_processed += len(page)
        last_ts = page[-1]["timestamp"]
        LastLogTimestamp.set(last_ts)

        if is_last_page:
            break

    if total_processed == 0:
        logger.info("No new logs found")
        return

    _remove_completed_transitions()

    for process, action, step_type, step_name, duration in stat_updates:
        stat_id = StatStore.get_or_create(process, action, step_type, step_name)
        StatStore.add_execution(stat_id, duration)

    logger.info("Processed %d log entries, stat updates: %d", total_processed, len(stat_updates))


def detect_anomaly():
    """Detect execution-time anomalies in active transitions."""
    transitions = TransitionStore.get_all()
    if not transitions:
        logger.info("No active transitions")
        return []

    now = datetime.now()
    new_anomalies: list[dict] = []

    for tr in transitions:
        if tr.get("is_completed") == "1":
            continue

        step_type = tr.get("step_type", "")
        step_name = tr.get("step_name", "")
        process = tr.get("process", "")
        action = tr.get("action", "")
        ts_raw = tr.get("timestamp", "")

        if not step_type or not step_name or not ts_raw:
            continue

        tr_timestamp = datetime.fromisoformat(ts_raw)
        current_exec = (now - tr_timestamp).total_seconds()

        stat = StatStore.find(process, action, step_type, step_name)
        time_limit = float(stat["time_limit"]) if stat else DLM_DEFAULT_TIME_LIMIT

        if current_exec > time_limit:
            existing = AnomalyStore.get_all()
            if any(a["tr_id"] == tr["id"] for a in existing):
                continue

            anomaly_id = AnomalyStore.create(
                tr_id=tr["id"],
                current_exec=current_exec,
                timestamp=now,
            )
            new_anomalies.append({
                "anomaly_id": anomaly_id,
                "tr_id": tr["id"],
                "process": process,
                "action": action,
                "step_type": step_type,
                "step_name": step_name,
                "current_exec": current_exec,
                "time_limit": time_limit,
            })

    for a in new_anomalies:
        logger.warning(
            "ANOMALY DETECTED [id=%s] transition=%s process=%s action=%s "
            "step=%s.%s exec_time=%.1fs limit=%.1fs",
            a["anomaly_id"], a["tr_id"], a["process"], a["action"],
            a["step_type"], a["step_name"], a["current_exec"], a["time_limit"],
        )

    if not new_anomalies:
        logger.info("No new anomalies detected (%d active transitions)", len(transitions))

    return new_anomalies


def clear():
    """Remove completed transitions and orphaned anomalies."""
    _remove_completed_transitions()

    anomalies = AnomalyStore.get_all()
    removed = 0
    for anomaly in anomalies:
        if not TransitionStore.exists(anomaly["tr_id"]):
            AnomalyStore.delete(anomaly["id"])
            removed += 1

    logger.info("Clear completed (removed %d orphaned anomalies)", removed)
