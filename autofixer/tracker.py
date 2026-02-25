"""Redis-backed tracker of currently active transitions.

Stores per-transition metadata in Redis hashes and maintains parent–child
chain relationships so that a transition is only removed from the "active"
set once *all* transitions sharing the same ``root_id`` have finished.

The tracker is the single source of truth for "what is running right now"
and must survive process restarts (Redis persistence).
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal

from core.redis import redis_client
from autofixer.config import get_config
from autofixer.events import TransitionEvent

logger = logging.getLogger('autofixer')


@dataclass
class ActiveTransition:
    tr_id: str
    root_id: str
    parent_id: str
    process_class: str
    action_name: str
    instance_key: str
    start_time: str  # ISO format
    status: Literal['active', 'failed', 'completed'] = 'active'
    end_time: str | None = None
    last_event: str = ''
    last_event_time: str = ''
    last_command_name: str = ''
    last_command_time: str = ''

    def duration_seconds(self) -> float | None:
        """Return elapsed seconds, or None if still running."""
        start = datetime.fromisoformat(self.start_time)
        if self.end_time:
            end = datetime.fromisoformat(self.end_time)
        else:
            end = datetime.now(timezone.utc)
        return (end - start).total_seconds()


def _prefix() -> str:
    return get_config('REDIS_KEY_PREFIX')


def _tr_key(tr_id: str) -> str:
    return f'{_prefix()}:tr:{tr_id}'


def _chain_key(root_id: str) -> str:
    return f'{_prefix()}:chain:{root_id}'


ACTIVE_SET_KEY_SUFFIX = ':active_roots'


def _active_roots_key() -> str:
    return f'{_prefix()}{ACTIVE_SET_KEY_SUFFIX}'


def _checkpoint_key() -> str:
    return f'{_prefix()}:checkpoint'


class Tracker:
    """Manages the active-transition state in Redis."""

    def __init__(self, redis=None):
        self.r = redis or redis_client

    # -- checkpoint ----------------------------------------------------------

    def get_checkpoint(self) -> datetime:
        raw = self.r.get(_checkpoint_key())
        if raw:
            return datetime.fromisoformat(raw.decode())
        return datetime(2000, 1, 1, tzinfo=timezone.utc)

    def set_checkpoint(self, ts: datetime) -> None:
        self.r.set(_checkpoint_key(), ts.isoformat())

    # -- handle events -------------------------------------------------------

    def handle_event(self, event: TransitionEvent) -> ActiveTransition | None:
        """Process a single event and update Redis state.
        Returns the ActiveTransition if it was just fully completed/removed.
        """
        handler = getattr(self, f'_on_{event.event_type.lower()}', None)
        if handler:
            return handler(event)
        self._update_last_event(event)
        return None

    def _on_start(self, event: TransitionEvent) -> None:
        at = ActiveTransition(
            tr_id=event.tr_id,
            root_id=event.root_id or event.tr_id,
            parent_id=event.parent_id or event.tr_id,
            process_class=event.process_class or '',
            action_name=event.action_name or '',
            instance_key=event.instance_key or '',
            start_time=event.timestamp.isoformat(),
            status='active',
            last_event='START',
            last_event_time=event.timestamp.isoformat(),
        )
        pipe = self.r.pipeline()
        pipe.hset(_tr_key(event.tr_id), mapping=self._to_redis(at))
        pipe.sadd(_chain_key(at.root_id), event.tr_id)
        pipe.sadd(_active_roots_key(), at.root_id)
        pipe.execute()

    def _on_fail(self, event: TransitionEvent) -> None:
        key = _tr_key(event.tr_id)
        if not self.r.exists(key):
            return
        self.r.hset(key, mapping={
            'status': 'failed',
            'last_event': 'FAIL',
            'last_event_time': event.timestamp.isoformat(),
        })

    def _on_unlock(self, event: TransitionEvent) -> ActiveTransition | None:
        """UNLOCK marks the final event for a transition.
        Returns the completed ActiveTransition if the entire chain is done.
        """
        key = _tr_key(event.tr_id)
        if not self.r.exists(key):
            return None

        data = self.r.hgetall(key)
        at = self._from_redis(data)

        final_status = 'failed' if at.status == 'failed' else 'completed'
        self.r.hset(key, mapping={
            'status': final_status,
            'end_time': event.timestamp.isoformat(),
            'last_event': 'UNLOCK',
            'last_event_time': event.timestamp.isoformat(),
        })
        at.status = final_status
        at.end_time = event.timestamp.isoformat()

        if self._chain_finished(at.root_id):
            chain_transitions = self._collect_chain(at.root_id)
            self._remove_chain(at.root_id)
            return at  # signal that chain is done
        return None

    def _on_set_state(self, event: TransitionEvent) -> None:
        self._update_last_event(event)

    def _on_sideeffect(self, event: TransitionEvent) -> None:
        key = _tr_key(event.tr_id)
        if not self.r.exists(key):
            return
        self.r.hset(key, mapping={
            'last_event': 'SideEffect',
            'last_event_time': event.timestamp.isoformat(),
            'last_command_name': event.command_name or '',
            'last_command_time': event.timestamp.isoformat(),
        })

    def _on_callback(self, event: TransitionEvent) -> None:
        key = _tr_key(event.tr_id)
        if not self.r.exists(key):
            return
        self.r.hset(key, mapping={
            'last_event': 'Callback',
            'last_event_time': event.timestamp.isoformat(),
            'last_command_name': event.command_name or '',
            'last_command_time': event.timestamp.isoformat(),
        })

    # -- query ---------------------------------------------------------------

    def get_active_transitions(self) -> list[ActiveTransition]:
        """Return all currently active transitions across all chains."""
        root_ids = self.r.smembers(_active_roots_key())
        result: list[ActiveTransition] = []
        for root_id in root_ids:
            root_id_str = root_id.decode() if isinstance(root_id, bytes) else root_id
            tr_ids = self.r.smembers(_chain_key(root_id_str))
            for tid in tr_ids:
                tid_str = tid.decode() if isinstance(tid, bytes) else tid
                data = self.r.hgetall(_tr_key(tid_str))
                if data:
                    result.append(self._from_redis(data))
        return result

    def get_chain(self, root_id: str) -> list[ActiveTransition]:
        """Return all transitions belonging to a chain."""
        tr_ids = self.r.smembers(_chain_key(root_id))
        result: list[ActiveTransition] = []
        for tid in tr_ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            data = self.r.hgetall(_tr_key(tid_str))
            if data:
                result.append(self._from_redis(data))
        return result

    def get_stuck_transitions(self, threshold_seconds: float) -> list[ActiveTransition]:
        """Return transitions that have been active longer than threshold."""
        stuck: list[ActiveTransition] = []
        for at in self.get_active_transitions():
            if at.status == 'active':
                duration = at.duration_seconds()
                if duration and duration > threshold_seconds:
                    stuck.append(at)
        return stuck

    # -- internal helpers ----------------------------------------------------

    def _chain_finished(self, root_id: str) -> bool:
        tr_ids = self.r.smembers(_chain_key(root_id))
        for tid in tr_ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            status = self.r.hget(_tr_key(tid_str), 'status')
            if status and status.decode() not in ('completed', 'failed'):
                return False
        return True

    def _collect_chain(self, root_id: str) -> list[ActiveTransition]:
        tr_ids = self.r.smembers(_chain_key(root_id))
        result = []
        for tid in tr_ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            data = self.r.hgetall(_tr_key(tid_str))
            if data:
                result.append(self._from_redis(data))
        return result

    def _remove_chain(self, root_id: str) -> None:
        tr_ids = self.r.smembers(_chain_key(root_id))
        pipe = self.r.pipeline()
        for tid in tr_ids:
            tid_str = tid.decode() if isinstance(tid, bytes) else tid
            pipe.delete(_tr_key(tid_str))
        pipe.delete(_chain_key(root_id))
        pipe.srem(_active_roots_key(), root_id)
        pipe.execute()

    def _update_last_event(self, event: TransitionEvent) -> None:
        key = _tr_key(event.tr_id)
        if self.r.exists(key):
            self.r.hset(key, mapping={
                'last_event': event.event_type,
                'last_event_time': event.timestamp.isoformat(),
            })

    @staticmethod
    def _to_redis(at: ActiveTransition) -> dict[str, str]:
        d = asdict(at)
        return {k: (v if v is not None else '') for k, v in d.items()}

    @staticmethod
    def _from_redis(data: dict) -> ActiveTransition:
        decoded = {}
        for k, v in data.items():
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            decoded[key] = val if val != '' else None
        return ActiveTransition(
            tr_id=decoded.get('tr_id', ''),
            root_id=decoded.get('root_id', ''),
            parent_id=decoded.get('parent_id', ''),
            process_class=decoded.get('process_class', ''),
            action_name=decoded.get('action_name', ''),
            instance_key=decoded.get('instance_key', ''),
            start_time=decoded.get('start_time', ''),
            status=decoded.get('status', 'active'),
            end_time=decoded.get('end_time'),
            last_event=decoded.get('last_event', ''),
            last_event_time=decoded.get('last_event_time', ''),
            last_command_name=decoded.get('last_command_name', ''),
            last_command_time=decoded.get('last_command_time', ''),
        )
