import pytest
import time
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from abstract.models import A, STATES
from abstract.logic.callbacks import save_error
from abstract.e2e.utils import wait_for_transition

class BasicProcess(BaseProcess):
    transitions = [
        Transition(
            action_name='go_to_B',
            sources=[STATES.A],
            target=STATES.B,
            side_effects=[error_for_superuser],
            failure_callbacks=[save_error],
        ),
    ]

@pytest.mark.django_db
def test_basic_transition(user):
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = BasicProcess(instance=a)
    process.go_to_B(user=user)
    # Wait for Celery task to complete
    # assert wait_for_transition(a, STATES.B), "Transition did not complete"
    a.refresh_from_db()
    assert a.status == STATES.B

@pytest.mark.django_db
def test_basic_transition_with_error(superuser):
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = BasicProcess(instance=a)
    process.go_to_B(user=superuser) # should raise an error for superuser
    # Wait for Celery task to complete (should fail and stay in A)
    # Give time for on_commit to fire and failure callback to execute
    # time.sleep(1.0)
    a.refresh_from_db()
    assert a.status == STATES.A
    assert a.error == 'Error for superuser'
