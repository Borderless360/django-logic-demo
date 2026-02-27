import pytest


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def lpush(self, key, value):
        self.ops.append(("lpush", key, value))
        return self

    def ltrim(self, key, start, end):
        self.ops.append(("ltrim", key, start, end))
        return self

    def expire(self, key, _seconds):
        self.ops.append(("expire", key))
        return self

    def execute(self):
        for op in self.ops:
            name = op[0]
            if name == "lpush":
                _, key, value = op
                self.redis.lpush(key, value)
            elif name == "ltrim":
                _, key, start, end = op
                self.redis.ltrim(key, start, end)
        self.ops = []
        return True


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.lists = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, nx=False, ex=None):  # noqa: ARG002
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)

    def lpush(self, key, value):
        bucket = self.lists.setdefault(key, [])
        bucket.insert(0, str(value))

    def ltrim(self, key, start, end):
        bucket = self.lists.get(key, [])
        self.lists[key] = bucket[start : end + 1]

    def lrange(self, key, start, end):
        bucket = self.lists.get(key, [])
        return bucket[start : end + 1]

    def expire(self, key, seconds):  # noqa: ARG002
        return True

    def pipeline(self):
        return FakePipeline(self)


@pytest.fixture
def fake_redis():
    return FakeRedis()

