import uuid
from typing import TypedDict
from django_logic.exceptions import TransitionNotAllowed
from django_logic.logger import logger, TransitionEventType
from django.contrib.auth import get_user_model
from locker import CacheLocker
User = get_user_model()

class TransitionContext(TypedDict):
    process     : str | None
    transition  : str
    tr_id       : uuid.UUID
    root_id     : uuid.UUID
    parent_id   : uuid.UUID
    user        : User | None
    user_id     : int | None
    app         : str
    model       : str
    instance_pk : int
    instance    : any
    # args and kwargs are used to pass arguments to the transition
    args        : tuple | None
    kwargs      : dict | None


class Transition():
    def __init__(
        self, 
        name              : str, 
        sources           : list[str], 
        target            : str | None,  # if None, the transition will not change the state i.e it's an action
        in_progress_state : str | None,
        failed_state      : str | None,
        permissions       : list[callable] | None,
        conditions        : list[callable] | None, 
        side_effects      : list[callable] | None, 
        callbacks         : list[callable] | None,
        failure_callbacks : list[callable] | None, 
        next_transition   : 'Transition' | None
    ):
        self.sources           = sources
        self.target            = target
        self.in_progress_state = in_progress_state
        self.failed_state      = failed_state
        self.name              = name
        self.permissions       = permissions
        self.conditions        = conditions
        self.side_effects      = side_effects
        self.callbacks         = callbacks
        self.failure_callbacks = failure_callbacks
        self.next_transition   = next_transition

    def is_valid(self, instance: any, user=None) -> bool:
        for permission in self.permissions:
            if not permission(instance, user):
                return False
        for condition in self.conditions:
            if not condition(instance):
                return False
        locker = CacheLocker(instance, field_name=self.field_name)
        return not locker.is_locked()

    def change_state(
        self, 
        instance  : any, 
        process   : str | None = None,  # path to the process class that called this transition
        root_id   : uuid.UUID | None = None,  # id of the root transition
        parent_id : uuid.UUID | None = None,  # id of the parent transition
        user      : User | None = None,  # user who is performing the transition
        *args     : tuple | None,
        **kwargs  : dict | None,
        ):

        locker = CacheLocker(instance, field_name=self.field_name)
        tr_id  = uuid.uuid4()
        context: TransitionContext = {
            'process'    : process,
            'transition' : self.name,
            'tr_id'      : tr_id,
            'root_id'    : root_id or tr_id,
            'parent_id'  : parent_id or tr_id,
            'user'       : user,
            'user_id'    : user.pk if user else None,
            'app'        : instance._meta.app_label,
            'model'      : instance._meta.model_name,
            'instance_pk': instance.pk,
            'instance'   : instance,
            'args'       : args,
            'kwargs'     : kwargs,
        }
        extra = {'event_type': TransitionEventType.START.value }
        extra.update(context)
        logger.info(f'{tr_id} {TransitionEventType.START.value} {process} {self.name} {instance.pk}', extra=extra)

        try:
            if not locker.lock():
                raise TransitionNotAllowed("State is locked")
            logger.info(
                f'{tr_id} {TransitionEventType.LOCK.value}',
                extra={'tr_id': tr_id, 'event_type': TransitionEventType.LOCK.value }
            )
        except TransitionNotAllowed as e:
            raise e
        if self.in_progress_state:
            self._set_state(tr_id, self.in_progress_state)
        try:
            for side_effect in self.side_effects:
                side_effect(context)
        except Exception as error:
            context['exception'] = error
            for callback in self.failure_callbacks:
                callback(context)
            if self.failed_state:
                self._set_state(tr_id, self.failed_state)
            locker.unlock()
            logger.info(
                f'{tr_id} {TransitionEventType.UNLOCK.value}',
                extra={'tr_id': tr_id, 'event_type': TransitionEventType.UNLOCK.value }
            )
            raise error
        else:
            if self.target:
                self._set_state(tr_id, self.target)
                locker.unlock()
                logger.info(
                    f'{tr_id} {TransitionEventType.UNLOCK.value}',
                    extra={'tr_id': tr_id, 'event_type': TransitionEventType.UNLOCK.value }
                )
            # Can be run in another thread
            for callback in self.callbacks:
                callback(context)
            # Always run in the same thread
            if self.next_transition:
                self.next_transition.change_state(instance, process, root_id, parent_id, user, *args, **kwargs)
        finally:
            # Refresh instance from db, too many changes may be made to the instance in the meantime
            self.instance.refresh_from_db()

    def _set_state(self, tr_id, state: str):
        self.instance[self.field_name] = state
        self.instance.save(fields=[self.field_name])
        logger.info(
            f'{tr_id} {TransitionEventType.SET_STATE.value} {self.instance[self.field_name]}',
            extra={'tr_id': tr_id, 'event_type': TransitionEventType.SET_STATE.value, 'state': self.instance[self.field_name] }
        )
