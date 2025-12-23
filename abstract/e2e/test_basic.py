import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock
from abstract.logic.test_basic import BasicProcess


# @pytest.mark.django_db(transaction=True)
# def test_basic_transition(user):
#     """Test basic transition that triggers a celery task.
#     Uses the existing worker from compose.yml (demo-worker service)."""
#     a = A.objects.create(name='A')
#     assert a.status == STATES.A

#     process = BasicProcess(instance=a)
#     process.go_to_B(user=user)
#     # If state is not unlocked, it means everyting are finished and we can see the latest state.
#     assert wait_state_unlock(process.state), "State should be unlocked"

#     a.refresh_from_db()
#     assert a.status == STATES.B


# @pytest.mark.django_db(transaction=True)
# def test_basic_transition_with_error(superuser):
#     a = A.objects.create(name='A')
#     assert a.status == STATES.A

#     process = BasicProcess(instance=a)
#     process.go_to_B(user=superuser) # should raise an error for superuser
#     assert wait_state_unlock(process.state), "State should be unlocked"

#     a.refresh_from_db()
#     assert a.status == STATES.A
#     assert a.error == 'Error for superuser'
