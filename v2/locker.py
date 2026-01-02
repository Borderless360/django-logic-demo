from hashlib import blake2b
from abc import ABC


class Locker(ABC):

    def __init__(self, instance: any, field_name: str):
        self.instance = instance
        self.field_name = field_name

    def __str__(self):
        """ It will used as a key for the cache. """
        return f"{self.instance._meta.app_label}-" \
               f"{self.instance._meta.model_name}-" \
               f"{self.field_name}-" \
               f"{self.instance.pk}"

    def key(self) -> str:
        return blake2b(self.__str__().encode(), digest_size=16).hexdigest()

    def lock(self) -> bool:
        raise NotImplementedError

    def unlock(self):
        raise NotImplementedError

    def is_locked(self):
        raise NotImplementedError


class CacheLocker(Locker):

    def lock(self) -> bool:
        """
        It locks the state only once for 3 years.
        nx - sets the value only once, if it was set up before it guarantees to return False.
        It returns True if it's been locked and False otherwise.
        """
        return self.cache.set(self, True, 99999999, nx=True) or False

    def unlock(self):
        return self.cache.delete(self)

    @property
    def is_locked(self) -> bool:
        return self.cache.get(self) or False

