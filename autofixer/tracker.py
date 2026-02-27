from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from autofixer.events import EventType, TransitionCompletion, TransitionEvent
from core.redis import redis_client


@dataclass
class _ActiveTransition:
    tr_id: str
    root_id: str
    parent_id: str
    process_class: str
    action_name: str
    instance_key: str
    started_at: datetime
    current_side_effect_name: str = ""
    current_side_effect_started_at: datetime | None = None
    side_effect_durations: list[tuple[str, float]] = field(default_factory=list)


class ActiveTransitionTracker:
    def __init__(self, *, key_prefix: str, redis=None) -> None:
        self.key_prefix = key_prefix
        self.redis = redis or redis_client
        self._transitions: dict[str, _ActiveTransition] = {}
        self._load()

    def apply(self, event: TransitionEvent) -> TransitionCompletion | None:
        if event.event_type == EventType.START:
            root_id = event.root_id or event.tr_id
            self._transitions[event.tr_id] = _ActiveTransition(
                tr_id=event.tr_id,
                root_id=root_id,
                parent_id=event.parent_id,
                process_class=event.process_class,
                action_name=event.action_name,
                instance_key=event.instance_key,
                started_at=event.timestamp,
            )
            self._save()
            return None

        active = self._transitions.get(event.tr_id)
        if not active:
            return None

        if event.event_type == EventType.SIDE_EFFECT and event.name:
            self._finish_current_side_effect(active, event.timestamp)
            active.current_side_effect_name = event.name
            active.current_side_effect_started_at = event.timestamp
            self._save()
            return None

        if event.event_type in (EventType.UNLOCK, EventType.FAIL):
            self._finish_current_side_effect(active, event.timestamp)
            completion = TransitionCompletion(
                tr_id=active.tr_id,
                root_id=active.root_id,
                process_class=active.process_class,
                action_name=active.action_name,
                duration_seconds=max((event.timestamp - active.started_at).total_seconds(), 0.0),
                completed_at=event.timestamp,
                side_effect_durations=list(active.side_effect_durations),
            )
            del self._transitions[event.tr_id]
            self._save()
            return completion

        return None

    def get_active(self) -> list[dict]:
        rows: list[dict] = []
        for item in self._transitions.values():
            rows.append(
                {
                    "tr_id": item.tr_id,
                    "root_id": item.root_id,
                    "parent_id": item.parent_id,
                    "process_class": item.process_class,
                    "action_name": item.action_name,
                    "instance_key": item.instance_key,
                    "started_at": item.started_at.isoformat(),
                    "current_side_effect": item.current_side_effect_name,
                }
            )
        rows.sort(key=lambda value: value["started_at"])
        return rows

    def get_active_roots(self) -> list[dict]:
        counts: dict[str, int] = {}
        for item in self._transitions.values():
            counts[item.root_id] = counts.get(item.root_id, 0) + 1
        rows = [{"root_id": root_id, "active_children": count} for root_id, count in counts.items()]
        rows.sort(key=lambda value: value["root_id"])
        return rows

    def _finish_current_side_effect(self, active: _ActiveTransition, completed_at: datetime) -> None:
        if not active.current_side_effect_name or active.current_side_effect_started_at is None:
            return
        duration = max((completed_at - active.current_side_effect_started_at).total_seconds(), 0.0)
        active.side_effect_durations.append((active.current_side_effect_name, duration))
        active.current_side_effect_name = ""
        active.current_side_effect_started_at = None

    def _storage_key(self) -> str:
        return f"{self.key_prefix}:active"

    def _save(self) -> None:
        payload = []
        for item in self._transitions.values():
            payload.append(
                {
                    "tr_id": item.tr_id,
                    "root_id": item.root_id,
                    "parent_id": item.parent_id,
                    "process_class": item.process_class,
                    "action_name": item.action_name,
                    "instance_key": item.instance_key,
                    "started_at": item.started_at.isoformat(),
                    "current_side_effect_name": item.current_side_effect_name,
                    "current_side_effect_started_at": item.current_side_effect_started_at.isoformat()
                    if item.current_side_effect_started_at
                    else None,
                    "side_effect_durations": item.side_effect_durations,
                }
            )
        self.redis.set(self._storage_key(), json.dumps(payload))

    def _load(self) -> None:
        raw = self.redis.get(self._storage_key())
        if not raw:
            return
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        payload = json.loads(raw)
        for row in payload:
            current_started = row.get("current_side_effect_started_at")
            self._transitions[row["tr_id"]] = _ActiveTransition(
                tr_id=row["tr_id"],
                root_id=row["root_id"],
                parent_id=row.get("parent_id", ""),
                process_class=row.get("process_class", ""),
                action_name=row.get("action_name", ""),
                instance_key=row.get("instance_key", ""),
                started_at=datetime.fromisoformat(row["started_at"]),
                current_side_effect_name=row.get("current_side_effect_name", ""),
                current_side_effect_started_at=datetime.fromisoformat(current_started) if current_started else None,
                side_effect_durations=[tuple(item) for item in row.get("side_effect_durations", [])],
            )

