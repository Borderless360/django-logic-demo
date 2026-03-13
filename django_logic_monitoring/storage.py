import json
import math
from datetime import datetime, timedelta
from enum import IntEnum

from core.redis import redis_client

from django_logic_monitoring.config import (
    DLM_DEFAULT_TIME_LIMIT,
    DLM_FAILURE_WINDOW,
    DLM_LOOP_WINDOW,
    DLM_MAX_EXECUTIONS,
    DLM_MIN_EXECUTIONS,
)


class AnomalyType(IntEnum):
    LONG_EXECUTION = 1
    STUCK_TRANSITION = 2
    FREQUENT_FAILURES = 3
    EXECUTION_TIME_DEGRADATION = 4
    LOOP_DETECTION = 5

PREFIX = "dlm"


def _decode(data: dict) -> dict:
    return {k.decode(): v.decode() for k, v in data.items()}


class LastLogTimestamp:
    KEY = f"{PREFIX}:last_log_ts"

    @classmethod
    def get(cls) -> datetime | None:
        val = redis_client.get(cls.KEY)
        if val:
            return datetime.fromisoformat(val.decode())
        return None

    @classmethod
    def set(cls, timestamp: datetime):
        redis_client.set(cls.KEY, timestamp.isoformat())


class TransitionStore:
    _PREFIX = f"{PREFIX}:tr"
    INDEX_KEY = f"{PREFIX}:transitions"

    @classmethod
    def _key(cls, tr_id):
        return f"{cls._PREFIX}:{tr_id}"

    @classmethod
    def create(cls, *, tr_id, process, action, model_name, object_id,
               field_name, root_id=None, parent_id=None, timestamp=None):
        data = {
            "id": str(tr_id),
            "process": process,
            "action": action,
            "model_name": model_name,
            "object_id": object_id,
            "field_name": field_name,
            "root_id": str(root_id) if root_id else "",
            "parent_id": str(parent_id) if parent_id else "",
            "steps": "0",
            "step_n": "0",
            "step_type": "",
            "step_name": "",
            "timestamp": timestamp.isoformat() if timestamp else "",
            "is_completed": "0",
        }
        redis_client.hset(cls._key(tr_id), mapping=data)
        redis_client.sadd(cls.INDEX_KEY, str(tr_id))

    @classmethod
    def update(cls, tr_id, **fields):
        if "timestamp" in fields and isinstance(fields["timestamp"], datetime):
            fields["timestamp"] = fields["timestamp"].isoformat()
        if "is_completed" in fields:
            fields["is_completed"] = "1" if fields["is_completed"] else "0"
        redis_client.hset(cls._key(tr_id), mapping=fields)

    @classmethod
    def get(cls, tr_id) -> dict | None:
        data = redis_client.hgetall(cls._key(tr_id))
        if not data:
            return None
        return _decode(data)

    @classmethod
    def get_all(cls) -> list[dict]:
        tr_ids = redis_client.smembers(cls.INDEX_KEY)
        result = []
        for tr_id in tr_ids:
            tr = cls.get(tr_id.decode())
            if tr:
                result.append(tr)
        return result

    @classmethod
    def delete(cls, tr_id):
        redis_client.delete(cls._key(tr_id))
        redis_client.srem(cls.INDEX_KEY, str(tr_id))

    @classmethod
    def exists(cls, tr_id) -> bool:
        return redis_client.exists(cls._key(tr_id)) > 0


class StatStore:
    _PREFIX = f"{PREFIX}:stat"
    INDEX_KEY = f"{PREFIX}:stats"
    COUNTER_KEY = f"{PREFIX}:stat:next_id"

    @classmethod
    def _key(cls, stat_id):
        return f"{cls._PREFIX}:{stat_id}"

    @classmethod
    def _lookup_key(cls, process, action, step_type, step_name):
        return f"{cls._PREFIX}:idx:{process}:{action}:{step_type}:{step_name}"

    @classmethod
    def get_or_create(cls, process, action, step_type, step_name) -> str:
        lookup = cls._lookup_key(process, action, step_type, step_name)
        stat_id = redis_client.get(lookup)
        if stat_id:
            return stat_id.decode()

        stat_id = str(redis_client.incr(cls.COUNTER_KEY))
        redis_client.set(lookup, stat_id)
        data = {
            "id": stat_id,
            "process": process,
            "action": action,
            "step_type": step_type,
            "step_name": step_name,
            "last_exec": json.dumps([]),
            "time_limit": str(DLM_DEFAULT_TIME_LIMIT),
            "updated_at": datetime.now().isoformat(),
        }
        redis_client.hset(cls._key(stat_id), mapping=data)
        redis_client.sadd(cls.INDEX_KEY, stat_id)
        return stat_id

    @classmethod
    def add_execution(cls, stat_id, duration_seconds: float):
        key = cls._key(stat_id)
        data = redis_client.hgetall(key)
        if not data:
            return

        last_exec = json.loads(data[b"last_exec"].decode())
        last_exec.append(duration_seconds)
        if len(last_exec) > DLM_MAX_EXECUTIONS:
            last_exec = last_exec[-DLM_MAX_EXECUTIONS:]

        time_limit = DLM_DEFAULT_TIME_LIMIT
        if len(last_exec) >= DLM_MIN_EXECUTIONS:
            mean = sum(last_exec) / len(last_exec)
            variance = sum((x - mean) ** 2 for x in last_exec) / len(last_exec)
            std = math.sqrt(variance)
            time_limit = mean + 2 * std

        redis_client.hset(key, mapping={
            "last_exec": json.dumps(last_exec),
            "time_limit": str(time_limit),
            "updated_at": datetime.now().isoformat(),
        })

    @classmethod
    def get(cls, stat_id) -> dict | None:
        data = redis_client.hgetall(cls._key(stat_id))
        if not data:
            return None
        return _decode(data)

    @classmethod
    def get_all(cls) -> list[dict]:
        stat_ids = redis_client.smembers(cls.INDEX_KEY)
        result = []
        for sid in stat_ids:
            stat = cls.get(sid.decode())
            if stat:
                result.append(stat)
        return result

    @classmethod
    def find(cls, process, action, step_type, step_name) -> dict | None:
        lookup = cls._lookup_key(process, action, step_type, step_name)
        stat_id = redis_client.get(lookup)
        if not stat_id:
            return None
        return cls.get(stat_id.decode())

    @classmethod
    def clear_all(cls) -> int:
        """Delete all stats, their lookup indices, and the counter."""
        stat_ids = redis_client.smembers(cls.INDEX_KEY)
        count = len(stat_ids)
        keys_to_delete = [cls.INDEX_KEY, cls.COUNTER_KEY]

        for sid in stat_ids:
            sid_str = sid.decode()
            keys_to_delete.append(cls._key(sid_str))

        idx_keys = redis_client.keys(f"{cls._PREFIX}:idx:*")
        keys_to_delete.extend(idx_keys)

        if keys_to_delete:
            redis_client.delete(*keys_to_delete)

        return count

class FailureCounterStore:
    _PREFIX = f"{PREFIX}:failcnt"

    @classmethod
    def _key(cls, process, action):
        return f"{cls._PREFIX}:{process}:{action}"

    @classmethod
    def record(cls, process: str, action: str, timestamp: datetime):
        """Append a failure timestamp and prune entries outside the window."""
        key = cls._key(process, action)
        raw = redis_client.get(key)
        timestamps: list[str] = json.loads(raw.decode()) if raw else []
        cutoff = (timestamp - timedelta(seconds=DLM_FAILURE_WINDOW)).isoformat()
        timestamps = [ts for ts in timestamps if ts > cutoff]
        timestamps.append(timestamp.isoformat())
        redis_client.set(key, json.dumps(timestamps))

    @classmethod
    def get_count(cls, process: str, action: str, now: datetime | None = None) -> int:
        """Return the number of failures within the sliding window."""
        key = cls._key(process, action)
        raw = redis_client.get(key)
        if not raw:
            return 0
        timestamps: list[str] = json.loads(raw.decode())
        ref = now or datetime.now()
        cutoff = (ref - timedelta(seconds=DLM_FAILURE_WINDOW)).isoformat()
        return sum(1 for ts in timestamps if ts > cutoff)


class LoopCounterStore:
    _PREFIX = f"{PREFIX}:loopcnt"

    @classmethod
    def _key(cls, model_name, object_id, process, action):
        return f"{cls._PREFIX}:{model_name}:{object_id}:{process}:{action}"

    @classmethod
    def record(cls, model_name: str, object_id: str, process: str, action: str,
               timestamp: datetime):
        """Append a start timestamp and prune entries outside the window."""
        key = cls._key(model_name, object_id, process, action)
        raw = redis_client.get(key)
        timestamps: list[str] = json.loads(raw.decode()) if raw else []
        cutoff = (timestamp - timedelta(seconds=DLM_LOOP_WINDOW)).isoformat()
        timestamps = [ts for ts in timestamps if ts > cutoff]
        timestamps.append(timestamp.isoformat())
        redis_client.set(key, json.dumps(timestamps))

    @classmethod
    def get_count(cls, model_name: str, object_id: str, process: str, action: str,
                  now: datetime | None = None) -> int:
        """Return the number of starts within the sliding window."""
        key = cls._key(model_name, object_id, process, action)
        raw = redis_client.get(key)
        if not raw:
            return 0
        timestamps: list[str] = json.loads(raw.decode())
        ref = now or datetime.now()
        cutoff = (ref - timedelta(seconds=DLM_LOOP_WINDOW)).isoformat()
        return sum(1 for ts in timestamps if ts > cutoff)


class AnomalyStore:
    _PREFIX = f"{PREFIX}:anomaly"
    INDEX_KEY = f"{PREFIX}:anomalies"
    COUNTER_KEY = f"{PREFIX}:anomaly:next_id"

    @classmethod
    def _key(cls, anomaly_id):
        return f"{cls._PREFIX}:{anomaly_id}"

    @classmethod
    def _unique_key(cls, tr_id, anomaly_type: AnomalyType):
        return f"{cls._PREFIX}:uniq:{tr_id}:{anomaly_type.value}"

    @classmethod
    def create(cls, *, tr_id, process, action, step_type, step_name,
               anomaly_type: AnomalyType, timestamp=None) -> str | None:
        """Create an anomaly. Returns anomaly id, or None if (tr_id, type) already exists."""
        ukey = cls._unique_key(tr_id, anomaly_type)
        if redis_client.exists(ukey):
            return None

        anomaly_id = str(redis_client.incr(cls.COUNTER_KEY))
        data = {
            "id": anomaly_id,
            "tr_id": str(tr_id),
            "process": process,
            "action": action,
            "step_type": step_type,
            "step_name": step_name,
            "type": str(anomaly_type.value),
            "timestamp": (timestamp or datetime.now()).isoformat(),
        }
        redis_client.hset(cls._key(anomaly_id), mapping=data)
        redis_client.sadd(cls.INDEX_KEY, anomaly_id)
        redis_client.set(ukey, anomaly_id)
        return anomaly_id

    @classmethod
    def exists_for(cls, tr_id, anomaly_type: AnomalyType) -> bool:
        return redis_client.exists(cls._unique_key(tr_id, anomaly_type)) > 0

    @classmethod
    def get_all(cls) -> list[dict]:
        anomaly_ids = redis_client.smembers(cls.INDEX_KEY)
        result = []
        for aid in anomaly_ids:
            data = redis_client.hgetall(cls._key(aid.decode()))
            if data:
                result.append(_decode(data))
        return result

    @classmethod
    def delete(cls, anomaly_id):
        data = redis_client.hgetall(cls._key(anomaly_id))
        if data:
            decoded = _decode(data)
            tr_id = decoded.get("tr_id", "")
            atype = decoded.get("type", "")
            if tr_id and atype:
                redis_client.delete(cls._unique_key(
                    tr_id, AnomalyType(int(atype))
                ))
        redis_client.delete(cls._key(anomaly_id))
        redis_client.srem(cls.INDEX_KEY, str(anomaly_id))
