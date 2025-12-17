from django.conf import settings
from redis import Redis


def get_redis_client():
    connection_kwargs = {}
    return Redis.from_url(settings.REDIS_URL, **connection_kwargs)


redis_client = get_redis_client()
