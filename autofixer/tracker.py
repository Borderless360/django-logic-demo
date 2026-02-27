"""
ActiveTransition tracker (AT-1, AT-2, AT-3).
Tracks running transitions; state in memory with Redis persistence for recovery.
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime

from django.conf import settings

from autofixer.events import LogEvent

logger = logging.getLogger("autofixer")


@dataclass
class ActiveTransition:
    """A transition that is currently running (chain not yet complete)."""

    tr_id: str
    root_id: str
    parent_id: str | None
    process_class: str
    action_name: str
    instance_key: str
    started_at: str  # ISO format

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ActiveTransition":
        return cls(**d)


class TransitionTracker:
    """
    Tracks active transitions. AT-1: chain active until all (root + children) complete.
    AT-2: completed transitions are removed.
    AT-3: state in memory, persisted to Redis for crash recovery.
    """

    REDIS_KEY_ACTIVE = "active"
    REDIS_KEY_LAST_OFFSET = "last_offset"
    TTL_DAYS = 1  # Keep persisted state for 1 day

    def __init__(self):
        from core.redis import redis_client

        self._redis = redis_client
        cfg = getattr(settings, "AUTOFIXER", {})
        self._prefix = cfg.get("REDIS_KEY_PREFIX", "autofixer")
        self._active: dict[str, ActiveTransition] = {}  # tr_id -> ActiveTransition
        self._roots: dict[str, set[str]] = {}  # root_id -> set of tr_ids in chain
        self._load_from_redis()

    def _key(self, *parts: str) -> str:
        return ":".join([self._prefix, "tracker"] + list(parts))

    def _load_from_redis(self) -> None:
        """Restore state from Redis after crash (AT-3)."""
        try:
            data = self._redis.get(self._key(self.REDIS_KEY_ACTIVE))
            if data:
                payload = json.loads(data)
                for tr_id, d in payload.get("active", {}).items():
                    self._active[tr_id] = ActiveTransition.from_dict(d)
                for root_id, tr_ids in payload.get("roots", {}).items():
                    self._roots[root_id] = set(tr_ids)
                logger.info("Restored %d active transitions from Redis", len(self._active))
        except Exception as e:
            logger.warning("Failed to restore from Redis: %s", e)

    def _save_to_redis(self) -> None:
        """Persist state to Redis (AT-3)."""
        try:
            payload = {
                "active": {tid: t.to_dict() for tid, t in self._active.items()},
                "roots": {rid: list(tr_ids) for rid, tr_ids in self._roots.items()},
            }
            key = self._key(self.REDIS_KEY_ACTIVE)
            self._redis.set(key, json.dumps(payload), ex=self.TTL_DAYS * 24 * 3600)
        except Exception as e:
            logger.warning("Failed to persist to Redis: %s", e)

    def process_event(self, event: LogEvent, started_at: datetime | None = None) -> None:
        """Process a log event: add on Start, remove on Unlock/Fail when chain complete."""
        if event.is_start:
            root_id = event.root_id or event.tr_id
            parent_id = event.parent_id
            t = ActiveTransition(
                tr_id=event.tr_id,
                root_id=root_id,
                parent_id=parent_id,
                process_class=event.process_class or "",
                action_name=event.action_name or "",
                instance_key=event.instance_key or "",
                started_at=(started_at or datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%S"),
            )
            self._active[event.tr_id] = t
            if root_id not in self._roots:
                self._roots[root_id] = set()
            self._roots[root_id].add(event.tr_id)
        elif event.is_complete:
            self._mark_complete(event.tr_id)
        self._save_to_redis()

    def _mark_complete(self, tr_id: str) -> None:
        """Mark transition complete and remove if whole chain is done (AT-2)."""
        if tr_id not in self._active:
            return
        t = self._active[tr_id]
        root_id = t.root_id
        self._roots[root_id].discard(tr_id)
        del self._active[tr_id]

        # If root has no more active transitions, we're done
        if not self._roots[root_id]:
            del self._roots[root_id]

    def get_active(self) -> list[ActiveTransition]:
        """Return all active transitions (for UA-1: user can view at any time)."""
        return list(self._active.values())
