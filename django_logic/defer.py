"""
Schedule side-effect callables in a separate Celery task (see spec: defer).
"""
from __future__ import annotations

import importlib
from typing import Any, Callable
from uuid import UUID

from django.apps import apps
from django.conf import settings

from django_logic.utils import restore_user_object

_TRANSITION_KWARGS_KEYS = frozenset({
    'tr_id',
    'root_id',
    'parent_id',
    'process_class',
    'field_name',
    'process_name',
    'action_name',
    'target',
})


def _callable_to_path(func: Callable) -> str:
    if not callable(func):
        raise TypeError('defer() expects a callable')
    module = getattr(func, '__module__', None)
    qualname = getattr(func, '__qualname__', None)
    if not module or qualname is None:
        raise TypeError('callable must have __module__ and __qualname__ (e.g. top-level function)')
    return f'{module}:{qualname}'


def _import_callable(path: str) -> Callable:
    if ':' not in path:
        raise ValueError(f"invalid callable path {path!r}; expected 'module:qualname'")
    mod_name, qualname = path.split(':', 1)
    module = importlib.import_module(mod_name)
    obj: Any = module
    for part in qualname.split('.'):
        obj = getattr(obj, part)
    if not callable(obj):
        raise TypeError(f'object at {path!r} is not callable')
    return obj


def _serialize_transition_kwargs(kwargs: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in _TRANSITION_KWARGS_KEYS:
        if key not in kwargs:
            continue
        val = kwargs[key]
        if val is None:
            out[key] = None
        elif isinstance(val, UUID):
            out[key] = str(val)
        else:
            out[key] = val
    user = kwargs.get('user')
    if user is not None:
        out['user_id'] = user.pk
    elif kwargs.get('user_id') is not None:
        out['user_id'] = kwargs['user_id']
    return out


def _kwargs_from_context(context: dict) -> dict:
    kwargs: dict[str, Any] = {}
    for key in _TRANSITION_KWARGS_KEYS:
        if key not in context:
            continue
        val = context[key]
        if key in ('tr_id', 'root_id', 'parent_id') and val is not None and isinstance(val, str):
            kwargs[key] = UUID(val)
        else:
            kwargs[key] = val
    if 'user' in context:
        kwargs['user'] = context['user']
    return kwargs


def execute_deferred(
    func_path: str,
    app_label: str,
    model_name: str,
    instance_id: Any,
    context: dict,
) -> None:
    """Run inside the Celery worker."""
    from django_logic.process import _transition_context

    ctx = dict(context)
    restore_user_object(ctx)
    kwargs = _kwargs_from_context(ctx)

    app = apps.get_app_config(app_label)
    model = app.get_model(model_name)
    instance = model.objects.get(pk=instance_id)
    func = _import_callable(func_path)

    token = None
    if kwargs.get('tr_id') is not None:
        token = _transition_context.set({
            'root_id': kwargs.get('root_id'),
            'tr_id': kwargs.get('tr_id'),
        })
    try:
        func(instance, **kwargs)
    finally:
        if token is not None:
            _transition_context.reset(token)


def defer(func: Callable, queue_name: str | None = None) -> Callable[..., None]:
    """
    Return a callable that submits ``func`` to Celery when invoked.

    The returned callable must be called as ``scheduled(instance, **kwargs)`` —
    same convention as transition side effects (model instance first).

    ``func`` must be importable via ``module:qualname`` (typically a module-level
    function). ``queue_name`` defaults to ``DJANGO_LOGIC_DEFAULT_QUEUE``.
    """
    queue = queue_name if queue_name is not None else getattr(
        settings, 'DJANGO_LOGIC_DEFAULT_QUEUE', 'celery'
    )
    func_path = _callable_to_path(func)

    def scheduled(instance: Any, **kwargs: Any) -> None:
        from django_logic.tasks import django_logic_defer

        if instance is None:
            raise TypeError('deferred callable requires a non-None model instance as first argument')
        meta = getattr(instance, '_meta', None)
        if meta is None:
            raise TypeError('first argument must be a Django model instance')

        task_kwargs = {
            'func_path': func_path,
            'app_label': meta.app_label,
            'model_name': meta.model_name,
            'instance_id': instance.pk,
            'context': _serialize_transition_kwargs(kwargs),
        }
        django_logic_defer.apply_async(kwargs=task_kwargs, queue=queue)

    return scheduled
