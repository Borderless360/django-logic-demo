import pytest
import time
from django.db import transaction
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from abstract.models import A, STATES
from abstract.logic.callbacks import save_error
from abstract.e2e.utils import wait_for_transition, verify_celery_worker_running
from core.utils import get_or_create_user

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

def test_basic_transition():
    user = get_or_create_user()
    
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = BasicProcess(instance=a)
    process.go_to_B(user=user)
    # Wait for Celery task to complete
    assert wait_for_transition(a, STATES.B), "Transition did not complete"

    a.refresh_from_db()
    assert a.status == STATES.B

@pytest.mark.django_db(transaction=True)
@pytest.mark.celery
def test_basic_transition_with_error(superuser, celery_worker, celery_app):
    # Verify celery worker is actually running
    assert verify_celery_worker_running(celery_app), "Celery worker is not running or not responding"
    
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = BasicProcess(instance=a)
    process.go_to_B(user=superuser) # should raise an error for superuser
    # Commit transaction to trigger on_commit callbacks
    transaction.commit()
    # Wait for Celery task to complete (should fail and stay in A)
    # Give time for on_commit to fire and failure callback to execute
    assert wait_for_transition(a, STATES.A, max_retries=20, retry_delay=0.2), "Transition should stay in A"
    a.refresh_from_db()
    assert a.status == STATES.A
    assert a.error == 'Error for superuser'
