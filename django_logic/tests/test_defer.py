import uuid
from unittest.mock import patch

import pytest

from django_logic.defer import (
    _callable_to_path,
    _serialize_transition_kwargs,
    defer,
    execute_deferred,
)


def _module_level_capture(obj, **kwargs):
    _module_level_capture.calls.append((obj.pk, dict(kwargs)))


_module_level_capture.calls = []


@pytest.mark.django_db
def test_defer_returns_callable_and_queues_task():
    from abstract.models import A

    instance = A.objects.create(name='d1')
    with patch('django_logic.tasks.django_logic_defer.apply_async') as apply_async:
        scheduled = defer(_module_level_capture)
        scheduled(instance)

    apply_async.assert_called_once()
    kwargs = apply_async.call_args.kwargs['kwargs']
    assert kwargs['app_label'] == 'abstract'
    assert kwargs['model_name'] == 'a'
    assert kwargs['instance_id'] == instance.pk
    assert kwargs['func_path'] == _callable_to_path(_module_level_capture)


@pytest.mark.django_db
def test_defer_uses_explicit_queue():
    from abstract.models import A

    instance = A.objects.create(name='d2')
    with patch('django_logic.tasks.django_logic_defer.apply_async') as apply_async:
        defer(_module_level_capture, queue_name='high')(instance)

    assert apply_async.call_args.kwargs['queue'] == 'high'


@pytest.mark.django_db
def test_defer_rejects_non_model_instance():
    with patch('django_logic.tasks.django_logic_defer.apply_async'):
        scheduled = defer(_module_level_capture)
    with pytest.raises(TypeError):
        scheduled(object())


@pytest.mark.django_db
def test_execute_deferred_invokes_callable_with_context():
    from abstract.models import A

    _module_level_capture.calls.clear()
    instance = A.objects.create(name='d3')
    tr_id = uuid.uuid4()
    context = _serialize_transition_kwargs({'tr_id': tr_id, 'process_name': 'process'})

    execute_deferred(
        _callable_to_path(_module_level_capture),
        'abstract',
        'a',
        instance.pk,
        context,
    )

    assert len(_module_level_capture.calls) == 1
    pk, kwargs = _module_level_capture.calls[0]
    assert pk == instance.pk
    assert kwargs['tr_id'] == tr_id
    assert kwargs['process_name'] == 'process'


@pytest.mark.django_db
def test_execute_deferred_restores_user_from_user_id(user):
    from abstract.models import A

    _module_level_capture.calls.clear()
    instance = A.objects.create(name='d4')
    context = _serialize_transition_kwargs({'user': user})

    execute_deferred(
        _callable_to_path(_module_level_capture),
        'abstract',
        'a',
        instance.pk,
        context,
    )

    assert _module_level_capture.calls[0][1]['user'] == user
