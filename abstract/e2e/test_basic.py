import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock
from abstract.logic.test_basic import BasicProcess


@pytest.mark.django_db(transaction=True)
def test_basic_transition(user):
    """Test basic transition that triggers a celery task.
    Uses the existing worker from compose.yml (demo-worker service)."""
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = BasicProcess(instance=a)
    process.go_to_B(user=user)
    # CeleryTransition queues side effects as tasks using transaction.on_commit()
    # The transaction needs to commit for the task to be queued

    # If state is not unlocked, it means everyting are finished and we can see the latest state.
    assert wait_state_unlock(process.state), "State should be unlocked"
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
