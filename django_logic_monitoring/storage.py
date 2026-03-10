import json
import math
from datetime import datetime

from core.redis import redis_client

from django_logic_monitoring.config import (
    DLM_DEFAULT_TIME_LIMIT,
    DLM_MAX_EXECUTIONS,
    DLM_MIN_EXECUTIONS,
)

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


class AnomalyStore:
    _PREFIX = f"{PREFIX}:anomaly"
    INDEX_KEY = f"{PREFIX}:anomalies"
    COUNTER_KEY = f"{PREFIX}:anomaly:next_id"

    @classmethod
    def _key(cls, anomaly_id):
        return f"{cls._PREFIX}:{anomaly_id}"

    @classmethod
    def create(cls, *, tr_id, current_exec, timestamp=None) -> str:
        anomaly_id = str(redis_client.incr(cls.COUNTER_KEY))
        data = {
            "id": anomaly_id,
            "tr_id": str(tr_id),
            "current_exec": str(current_exec),
            "timestamp": (timestamp or datetime.now()).isoformat(),
        }
        redis_client.hset(cls._key(anomaly_id), mapping=data)
        redis_client.sadd(cls.INDEX_KEY, anomaly_id)
        return anomaly_id

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
        redis_client.delete(cls._key(anomaly_id))
        redis_client.srem(cls.INDEX_KEY, str(anomaly_id))
