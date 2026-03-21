from __future__ import annotations

from hashlib import blake2b

from django.core.cache import cache


class State:
    _LOCK_TTL = 60 * 60  # 1 hour — safety net against abandoned locks

    def __init__(
        self,
        instance: object,
        field_name: str,
        process_name: str | None = None,
        queryset_name: str = 'objects',
    ) -> None:
        self.instance = instance
        self.field_name = field_name
        self.process_name = process_name
        self.queryset_name = queryset_name

    # -- read / write ----------------------------------------------------------

    def get_state(self) -> str:
        return getattr(self.instance, self.field_name)

    def set_state(self, state: str) -> None:
        setattr(self.instance, self.field_name, state)
        self.instance.save(update_fields=[self.field_name])
        self.instance.refresh_from_db()

    def get_db_state(self) -> str:
        qs = getattr(self.instance._meta.model, self.queryset_name).all()
        return qs.values_list(self.field_name, flat=True).get(pk=self.instance.pk)

    # -- identity --------------------------------------------------------------

    @property
    def instance_key(self) -> str:
        meta = self.instance._meta
        return f'{meta.app_label}-{meta.model_name}-{self.field_name}-{self.instance.pk}'

    def _get_hash(self) -> str:
        return blake2b(self.instance_key.encode(), digest_size=16).hexdigest()

    # -- locking (atomic by default) -------------------------------------------

    def lock(self) -> bool:
        """Atomic set-if-not-exists. Returns True only if lock was acquired."""
        return cache.add(self._get_hash(), True, self._LOCK_TTL)

    def unlock(self) -> None:
        cache.delete(self._get_hash())

    def is_locked(self) -> bool:
        return cache.get(self._get_hash()) or False
