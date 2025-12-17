import pytest
import time
from abstract.models import A, B, C, STATES
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user, is_superuser
from abstract.logic.callbacks import save_error
from abstract.e2e.utils import wait_for_transition


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
        Transition('go_to_B', [STATES.A], STATES.B, 
            side_effects=[run_b_action], 
            failure_callbacks=[save_error]
        ),
    ]

class BProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, 
            side_effects=[run_c_action], 
            failure_callbacks=[save_error]
        ),
    ]

class CProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, 
            permissions=[is_user], 
        ),
        Transition('go_to_B', [STATES.A], STATES.B, 
            permissions=[is_superuser], 
            side_effects=[error_for_superuser], 
            failure_callbacks=[save_error]
        ),
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
    # Wait for nested transitions to complete (A -> B triggers B -> B triggers C -> B)
    # assert wait_for_transition(a, STATES.B, max_retries=25, retry_delay=0.3), "Nested transition did not complete for A"
    # assert wait_for_transition(b, STATES.B, max_retries=25, retry_delay=0.3), "Nested transition did not complete for B"
    # assert wait_for_transition(c, STATES.B, max_retries=25, retry_delay=0.3), "Nested transition did not complete for C"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.B
    assert b.status == STATES.B
    assert c.status == STATES.B

@pytest.mark.django_db
def test_nested_calls_with_no_permissions(staff_user):
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A

    process = AProcess(instance=a)
    process.go_to_B(user=staff_user)
    # Wait for transitions to complete (A -> B, but C stays in A due to permissions)
    # assert wait_for_transition(a, STATES.B, max_retries=25, retry_delay=0.3), "Transition did not complete for A"
    # time.sleep(1.0)  # Give time for on_commit to fire and error handling
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.B
    assert b.status == STATES.A  # TODO: should be done or not?
    assert c.status == STATES.A  # Correct, because is_user condition is not met and the last transition is not run
    assert a.error is None
    assert b.error.startswith("Process class") and staff_user.username in b.error
    assert c.error is None

@pytest.mark.django_db
def test_nested_calls_with_error(superuser):
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A

    process = AProcess(instance=a)
    process.go_to_B(user=superuser)
    # Wait for transitions and error handling
    # assert wait_for_transition(a, STATES.B, max_retries=25, retry_delay=0.3), "Transition did not complete for A"
    # time.sleep(1.0)  # Give time for on_commit to fire and error handling
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    # TODO: fix this test, assert is not correct
    assert a.status == STATES.B
    assert b.status == STATES.B  # TODO: is it correct? I think it should be STATES.A because the child was crashed
    assert c.status == STATES.A
    assert a.error is None
    assert b.error is None
    assert c.error == 'Error for superuser'
