import pytest
from abstract.models import A, B, C, STATES
from abstract.logic.test_nested_calls import AProcess
from abstract.e2e.utils import wait_state_unlock


# @pytest.mark.django_db(transaction=True)
# def test_nested_calls(user):
#     c = C.objects.create(name='C')
#     b = B.objects.create(name='B', c=c)
#     a = A.objects.create(name='A', b=b)
#     assert a.status == STATES.A
#     assert b.status == STATES.A
#     assert c.status == STATES.A

#     process = AProcess(instance=a)
#     process.go_to_B(user=user)
#     assert wait_state_unlock(process.state), "State should be unlocked"

#     a.refresh_from_db()
#     b.refresh_from_db()
#     c.refresh_from_db()
#     assert a.status == STATES.B
#     assert b.status == STATES.B
#     assert c.status == STATES.B

# @pytest.mark.django_db
# def test_nested_calls_with_no_permissions(staff_user):
#     c = C.objects.create(name='C')
#     b = B.objects.create(name='B', c=c)
#     a = A.objects.create(name='A', b=b)
#     assert a.status == STATES.A
#     assert b.status == STATES.A
#     assert c.status == STATES.A

#     process = AProcess(instance=a)
#     process.go_to_B(user=staff_user)
#     # Wait for transitions to complete (A -> B, but C stays in A due to permissions)
#     # assert wait_for_transition(a, STATES.B, max_retries=25, retry_delay=0.3), "Transition did not complete for A"
#     # time.sleep(1.0)  # Give time for on_commit to fire and error handling
#     a.refresh_from_db()
#     b.refresh_from_db()
#     c.refresh_from_db()
#     assert a.status == STATES.B
#     assert b.status == STATES.A  # TODO: should be done or not?
#     assert c.status == STATES.A  # Correct, because is_user condition is not met and the last transition is not run
#     assert a.error is None
#     assert b.error.startswith("Process class") and staff_user.username in b.error
#     assert c.error is None

# @pytest.mark.django_db
# def test_nested_calls_with_error(superuser):
#     c = C.objects.create(name='C')
#     b = B.objects.create(name='B', c=c)
#     a = A.objects.create(name='A', b=b)
#     assert a.status == STATES.A
#     assert b.status == STATES.A
#     assert c.status == STATES.A

#     process = AProcess(instance=a)
#     process.go_to_B(user=superuser)
#     # Wait for transitions and error handling
#     # assert wait_for_transition(a, STATES.B, max_retries=25, retry_delay=0.3), "Transition did not complete for A"
#     # time.sleep(1.0)  # Give time for on_commit to fire and error handling
#     a.refresh_from_db()
#     b.refresh_from_db()
#     c.refresh_from_db()
#     # TODO: fix this test, assert is not correct
#     assert a.status == STATES.B
#     assert b.status == STATES.B  # TODO: is it correct? I think it should be STATES.A because the child was crashed
#     assert c.status == STATES.A
#     assert a.error is None
#     assert b.error is None
#     assert c.error == 'Error for superuser'
