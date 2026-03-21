from __future__ import annotations

import importlib
import uuid
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model

from v4.context import TransitionContext
from v4.state import State


def to_task_kwargs(ctx: TransitionContext, state: State) -> dict[str, Any]:
    """Produce a JSON-safe dict for async task dispatch."""
    result: dict[str, Any] = {
        'app_label': state.instance._meta.app_label,
        'model_name': state.instance._meta.model_name,
        'instance_id': state.instance.pk,
        'field_name': state.field_name,
        'process_class': ctx.process_class,
        'tr_id': str(ctx.tr_id),
        'root_id': str(ctx.root_id) if ctx.root_id else None,
        'parent_id': str(ctx.parent_id) if ctx.parent_id else None,
    }
    if ctx.user is not None:
        result['user_id'] = ctx.user.id
    return result


def restore_user(kwargs: dict) -> object | None:
    """Restore ``user`` from ``user_id`` in a task kwargs dict."""
    user_id = kwargs.get('user_id')
    if not user_id:
        return None
    return get_user_model().objects.get(id=user_id)


def restore_process(
    app_label: str,
    model_name: str,
    instance_id: int | str,
    process_class: str,
    field_name: str = 'status',
):
    """Load instance + Process from serialised task kwargs."""
    model = apps.get_app_config(app_label).get_model(model_name)
    instance = model.objects.get(pk=instance_id)

    module_path, class_name = process_class.rsplit('.', 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    process = cls(field_name=field_name, instance=instance)
    return process


def restore_action(
    app_label: str,
    model_name: str,
    instance_id: int | str,
    field_name: str,
    process_class: str,
    action_name: str,
    user: object | None = None,
    tr_id: str | None = None,
    root_id: str | None = None,
    parent_id: str | None = None,
):
    """Restore a specific transition from serialised task kwargs.

    When ``tr_id``/``root_id``/``parent_id`` are provided (as strings from
    ``to_task_kwargs``), they are threaded into the restored context so that
    log correlation between dispatch and execute phases is preserved.
    """
    process = restore_process(
        app_label=app_label,
        model_name=model_name,
        instance_id=instance_id,
        process_class=process_class,
        field_name=field_name,
    )

    ctx_kwargs: dict[str, Any] = {'user': user}
    if tr_id:
        ctx_kwargs['tr_id'] = uuid.UUID(tr_id)
    if root_id:
        ctx_kwargs['root_id'] = uuid.UUID(root_id)
    if parent_id:
        ctx_kwargs['parent_id'] = uuid.UUID(parent_id)

    ctx = TransitionContext(**ctx_kwargs)
    transition = process._resolve_transition(action_name, ctx)
    return process, transition, ctx
