# import pytest
# from abstract.models import A, B, C, STATES
# from abstract.logic.test_nested_calls import AProcess, BProcess, CProcess
# from abstract.e2e.utils import wait_state_unlock
# from django_logic.state import State


# @pytest.mark.django_db(transaction=True)
# def test_nested_calls(user):
#     c = C.objects.create(name='C')
#     b = B.objects.create(name='B', c=c)
#     a = A.objects.create(name='A', b=b)
#     process = AProcess(instance=a)
#     process.go_to_B(user=user)
    
#     # State A should be unloacked after B and C 
#     assert wait_state_unlock(process.state), "State A should be unlocked"
#     a.refresh_from_db()
#     b.refresh_from_db()
#     c.refresh_from_db()
#     assert a.status == STATES.B
#     assert b.status == STATES.B
#     assert c.status == STATES.B


# @pytest.mark.django_db(transaction=True)
# def test_nested_calls_with_no_permissions(staff_user):
#     c = C.objects.create(name='C')
#     b = B.objects.create(name='B', c=c)
#     a = A.objects.create(name='A', b=b)
#     process = AProcess(instance=a)
#     process.go_to_B(user=staff_user)

#     # State A should be unloacked after B and C 
#     assert wait_state_unlock(process.state), "State A should be unlocked"
#     a.refresh_from_db()
#     b.refresh_from_db()
#     c.refresh_from_db()
#     # staff_user has no permissions to run go_to_B transition in CProcess, 
#     # so the last transition is not run, but BProcess is run and raises an error
#     assert a.status == STATES.A
#     assert b.status == STATES.A
#     assert c.status == STATES.A
#     assert a.error.startswith("Process class") and staff_user.username in a.error
#     assert b.error.startswith("Process class") and staff_user.username in b.error
#     assert c.error is None  # nothing happened in CProcess

# @pytest.mark.django_db(transaction=True)
# def test_nested_calls_with_error(superuser):
#     c = C.objects.create(name='C')
#     b = B.objects.create(name='B', c=c)
#     a = A.objects.create(name='A', b=b)
#     process = AProcess(instance=a)
#     process.go_to_B(user=superuser)

#     assert wait_state_unlock(process.state), "State A should be unlocked"
#     a.refresh_from_db()
#     b.refresh_from_db()
#     c.refresh_from_db()
#     # any error in the nested process should be propagated to the parent process
#     assert a.status == STATES.A
#     assert b.status == STATES.A
#     assert c.status == STATES.A
#     assert a.error == 'Error for superuser'
#     assert b.error == 'Error for superuser'
#     assert c.error == 'Error for superuser'
