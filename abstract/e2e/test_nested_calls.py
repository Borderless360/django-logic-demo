import pytest
from abstract.models import A, B, C, STATES
from django_logic import Process
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user
from abstract.logic.callbacks import save_error


def run_b_action(obj, *args, **kwargs):
    process = BProcess(instance=obj.b)
    print(f"Running b action with args: {args} and kwargs: {kwargs}")
    print(f"Process available actions: {process.get_available_actions()}")
    process.go_to_B(*args, **kwargs)

def run_c_action(obj, *args, **kwargs):
    process = CProcess(instance=obj.c)
    process.go_to_B(*args, **kwargs)

class AProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, side_effects=[run_b_action]),
    ]

class BProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, side_effects=[run_c_action]),
    ]

class CProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B),
    ]

@pytest.mark.django_db
def test_nested_calls(user):
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A

    process = AProcess(instance=a)
    process.go_to_B(user=user)
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.B
    assert b.status == STATES.B
    assert c.status == STATES.B
