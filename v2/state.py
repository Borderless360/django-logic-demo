import uuid
from abc import ABC


class State[T](ABC):
    """ Base class for states. """

    FIELD_NAME = 'state'

    def __init__(self, instance: T, action_id: uuid.UUID):
        self.instance = instance
        # The state cannot be used outside of the action.
        # Therefore action_id is required.
        self.action_id = action_id

    def set(self, value):
        pass

    def get(self):
        self.instance[self.FIELD_NAME]

    def key(self):
        """ Key of state. It will be used as a key that is being locked. """
        raise NotImplementedError

    def lock(self) -> bool:
        """ Lock the state of object. 
        It should use self.tr_id as a value to lock the state.
        If state is already locked by other transition, it should return False.
        """
        raise NotImplementedError

    def unlock(self):
        """ Unlock the state of object. 
        It should use self.tr_id as a value to unlock the state.
        If state is not locked or locked by other transition, it should return False.
        """
        raise NotImplementedError

    @property
    def is_locked(self) -> uuid.UUID | False:
        """ Returns transition id that was locked the state of object. 
        If state is not locked, False will be returned. 
        """
        raise NotImplementedError


class ModelState[T](State[T]):
    """ State that is used for model instances. 
    Locker is based on django cache with redis.
    """

    def key(self):
        return f"{self.instance._meta.app_label}-" \
               f"{self.instance._meta.model_name}-" \
               f"{self.FIELD_NAME}-" \
               f"{self.instance.pk}"

    def lock(self) -> bool:
        # 99 999 999 seconds is 3 years
        # nx - sets the value only once, if it was set up before it guarantees to return False.
        return self.cache.set(self, self.tr_id, 99999999, nx=True) or False

    def unlock(self):
        if self.cache.get(self) != self.tr_id:
            return False
        if self.cache.delete(self):
            return True
        return False

    @property
    def is_locked(self) -> uuid.UUID | False:
        return self.cache.get(self)

