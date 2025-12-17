from typing import Optional

from django.conf import settings
from django.utils import timezone


class QueueTransitionHelper:
    """
    Helps working with QueueTransition. Handles keys and all redis calls.

    Queue transition uses:
    1. List (_list_key): queue with serialized transitions to process
    2. Lock (_lock_key): prevent parallel processing
    3. Tmp (_tmp_key): list that stores currently processing transition. It is list with one element to take advantage
       of atomic command lmove, that moves value from one list to another.
    """
    USER_TYPE_CLIENT = 'client'  # it is the only queue type that used in project

    redis_client = None
    queue_key = None
    _list_key = None
    _lock_key = None
    _tmp_key = None

    def __init__(self, redis_client, queue_key: str = None) -> None:
        self.redis_client = redis_client
        if queue_key:
            self.set_queue_key(queue_key)

    @classmethod
    def build_base_queue_key(cls, user_id: str, model_name: str) -> str:
        return f'queue_transition:{cls.USER_TYPE_CLIENT}:{user_id}:{model_name}'

    @classmethod
    def build_manual_queue_key(cls, user_id: str, model_name: str) -> str:
        """ Manual queue is used to skip main queue that can be full of auto fulfilling orders """
        key = cls.build_base_queue_key(user_id, model_name)
        return f'{key}:manual'

    @classmethod
    def build_sharding_queue_key(cls, user_id: str, model_name: str, object_id: int, shards_count: int = None) -> str:
        """
        Enables to use more than one queue for fulfilling orders.
        Default single queue and zero sharding queue don't have queue number postfix, other sharding queues have
        postfix from 1 to shards_count.
        """
        if not shards_count:
            shards_count = settings.QUEUE_TRANSITION_DEFAULT_SHARDS_COUNT

        key = cls.build_base_queue_key(user_id, model_name)
        queue_number = object_id % shards_count
        if queue_number:
            key = f'{key}:{queue_number}'

        return key

    @staticmethod
    def build_lock_key(queue_key: str) -> str:
        return f'{queue_key}:lock'

    @staticmethod
    def build_list_key(queue_key: str) -> str:
        return f'{queue_key}:list'

    @staticmethod
    def build_tmp_key(queue_key: str) -> str:
        return f'{queue_key}:tmp'

    def _set_queue_keys(self) -> None:
        self._list_key = self.build_list_key(self.queue_key)
        self._lock_key = self.build_lock_key(self.queue_key)
        self._tmp_key = self.build_tmp_key(self.queue_key)

    def set_queue_key(self, queue_key: str) -> None:
        self.queue_key = queue_key
        self._set_queue_keys()

    def push_to_queue(self, value: str, to_beginning: bool = False) -> None:
        assert self.queue_key is not None, 'queue key is not set'
        if to_beginning:
            self.redis_client.lpush(self._list_key, value)
        else:
            self.redis_client.rpush(self._list_key, value)

    def take_value_from_queue(self, with_tmp=False) -> Optional[str]:
        assert self.queue_key is not None, 'queue key is not set'

        if with_tmp:
            value = self.redis_client.lmove(self._list_key, self._tmp_key)
        else:
            value = self.redis_client.lpop(self._list_key)

        return value

    def flush_queue(self) -> Optional[str]:
        assert self.queue_key is not None, 'queue key is not set'
        return self.redis_client.delete(self._list_key)

    def get_lock(self):
        assert self.queue_key is not None, 'queue key is not set'
        return self.redis_client.lock(self._lock_key)

    def unlock_queue(self) -> None:
        assert self.queue_key is not None, 'queue key is not set'
        self.redis_client.delete(self._lock_key)

    def get_queue_length(self) -> int:
        assert self.queue_key is not None, 'queue key is not set'
        return self.redis_client.llen(self._list_key)

    def get_first_value(self):
        assert self.queue_key is not None, 'queue key is not set'
        values = self.redis_client.lrange(self._list_key, 0, 0)
        if not values:
            return
        return values[0]

    def is_locked(self):
        assert self.queue_key is not None, 'queue key is not set'
        return bool(self.redis_client.get(self._lock_key))

    def take_value_from_tmp(self) -> Optional[str]:
        assert self.queue_key is not None, 'queue key is not set'
        return self.redis_client.lpop(self._tmp_key)

    def remove_from_tmp(self, value: str) -> None:
        assert self.queue_key is not None, 'queue key is not set'
        self.redis_client.lrem(self._tmp_key, 0, value)


class QueueTransitionPool:
    """
    Helps working with currently used queues. It needs for finding stuck queues.
    """
    POOL_KEY = 'queue_transition_pool'
    TIME_LIMIT = 5 * 60  # in seconds

    redis_client = None

    def __init__(self, redis_client) -> None:
        self.redis_client = redis_client

    @staticmethod
    def get_timestamp() -> int:
        return int(timezone.now().timestamp())

    @classmethod
    def get_timestamp_limit(cls) -> int:
        return cls.get_timestamp() - cls.TIME_LIMIT

    def flush_queues(self) -> None:
        self.redis_client.delete(self.POOL_KEY)

    def add_queue(self, queue_key: str) -> None:
        self.redis_client.sadd(self.POOL_KEY, queue_key)

    def get_queues(self) -> list[bytes]:
        return self.redis_client.smembers(self.POOL_KEY)

    def remove_queue(self, queue_key) -> None:
        self.redis_client.srem(self.POOL_KEY, queue_key)
