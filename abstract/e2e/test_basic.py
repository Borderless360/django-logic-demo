import pytest
import time
from django.db import transaction
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

@pytest.mark.django_db(transaction=True)
def test_basic_transition(user, celery_app):
    """Test basic transition that triggers a celery task.
    Uses the existing worker from compose.yml (demo-worker service)."""
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = BasicProcess(instance=a)
    process.go_to_B(user=user)
    transaction.commit()
    # CeleryTransition queues side effects as tasks using transaction.on_commit()
    # The transaction needs to commit for the task to be queued
    # Wait for celery task to complete (task will be executed by demo-worker from compose.yml)
    # assert wait_for_transition(a, STATES.B, max_retries=12, retry_delay=0.5), "Transition did not complete"
    time.sleep(5)
    # TODO: instead of waiting states we can wait State.is_locked()
    a.refresh_from_db()
    assert a.status == STATES.B

# @pytest.mark.django_db()
# @pytest.mark.celery
# def test_basic_transition_with_error(superuser, celery_app, celery_worker):
#     a = A.objects.create(name='A')
#     assert a.status == STATES.A

#     process = BasicProcess(instance=a)
#     process.go_to_B(user=superuser) # should raise an error for superuser
#     # Wait for celery task to complete and error callback to execute
#     # Since state stays A, wait a bit to ensure failure callback has executed
#     time.sleep(0.5)
#     # Verify state stayed in A (transition failed)
#     assert wait_for_transition(a, STATES.A, max_retries=25, retry_delay=0.3), "Transition should have stayed in A state"
#     a.refresh_from_db()
#     assert a.status == STATES.A
#     assert a.error == 'Error for superuser'
