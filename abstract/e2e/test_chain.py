# import pytest
# from abstract.models import A, STATES
# from abstract.e2e.utils import wait_state_unlock
# from abstract.logic.test_chain import ChainProcess


# @pytest.mark.django_db(transaction=True)
# def test_chain_of_transitions(user):

#     a = A.objects.create(name='A')
#     process = ChainProcess(instance=a)
#     process.go_to_B(user=user)

#     assert wait_state_unlock(process.state), "State should be unlocked"
#     a.refresh_from_db()
#     assert a.status == STATES.D


# @pytest.mark.django_db(transaction=True)
# def test_chain_of_transitions_with_no_permissions(staff_user):

#     a = A.objects.create(name='A', status=STATES.A)
#     process = ChainProcess(instance=a)
#     process.go_to_B(user=staff_user)

#     assert wait_state_unlock(process.state), "State should be unlocked"
#     a.refresh_from_db()
#     assert a.status == STATES.C  # staff user has no permissions to run go_to_D transition
#     assert a.error is None       # no permission is not an error, just stop the chain execution


# @pytest.mark.django_db(transaction=True)
# def test_chain_of_transitions_with_error_for_superuser(superuser):

#     a = A.objects.create(name='A', status=STATES.A)
#     process = ChainProcess(instance=a)
#     process.go_to_B(user=superuser)  # should raise an error for superuser in the go_to_C transition

#     assert wait_state_unlock(process.state), "State should be unlocked"
#     a.refresh_from_db()
#     # go_to_C transition should raise an error for superuser
#     assert a.status == STATES.B  
#     assert a.error == 'Error for superuser'
