import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock
from abstract.logic.test_chain import ChainProcess


# @pytest.mark.django_db(transaction=True)
# def test_chain_of_transitions(user):
#     a = A.objects.create(name='A')
#     assert a.status == STATES.A

#     process = ChainProcess(instance=a)
#     process.go_to_B(user=user)
#     assert wait_state_unlock(process.state), "State should be unlocked"

#     a.refresh_from_db()
#     assert a.status == STATES.D


# @pytest.mark.django_db(transaction=True)
# def test_chain_of_transitions_with_no_permissions(staff_user):
#     """ Test chain of transitions with no permissions in the middle of the chain.
#     Staff user have no permissions to run go_to_D transition, so it should be stay in C state.
#     """
#     a = A.objects.create(name='A', status=STATES.A)
#     assert a.status == STATES.A

#     process = ChainProcess(instance=a)
#     process.go_to_B(user=staff_user)
#     assert wait_state_unlock(process.state), "State should be unlocked"

#     a.refresh_from_db()
#     assert a.status == STATES.C


# @pytest.mark.django_db(transaction=True)
# def test_chain_of_transitions_with_error_for_superuser(superuser):
#     """ Test chain of transitions with error for superuser in the middle of the chain.
#     Superuser should raise an error in the go_to_C transition and stay in B state.
#     """
#     a = A.objects.create(name='A', status=STATES.A)
#     assert a.status == STATES.A

#     process = ChainProcess(instance=a)
#     process.go_to_B(user=superuser)
#     assert wait_state_unlock(process.state), "State should be unlocked"

#     a.refresh_from_db()
#     assert a.status == STATES.B
#     assert a.error == 'Error for superuser'
