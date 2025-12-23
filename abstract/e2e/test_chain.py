import pytest
import time
from abstract.models import A, STATES
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user
from abstract.logic.callbacks import save_error
# from abstract.e2e.utils import wait_for_transition


# @pytest.mark.django_db
# def test_chain_of_transitions(user):
#     a = A.objects.create(name='A')
#     assert a.status == STATES.A

#     process = ChainProcess(instance=a)
#     process.go_to_B(user=user)
#     # Wait for chain of transitions to complete (B -> C -> D)
#     # assert wait_for_transition(a, STATES.D, max_retries=25, retry_delay=0.3), "Chain transition did not complete"
#     a.refresh_from_db()
#     assert a.status == STATES.D


# @pytest.mark.django_db
# def test_chain_of_transitions_with_no_permissions(staff_user):
#     """ Test chain of transitions with no permissions in the middle of the chain.
#     Staff user have no permissions to run go_to_D transition, so it should be stay in C state.
#     """
#     a = A.objects.create(name='A', status=STATES.A)
#     assert a.status == STATES.A

#     process = ChainProcess(instance=a)
#     process.go_to_B(user=staff_user)
#     # Wait for chain to complete up to C (B -> C, but C -> D fails due to permissions)
#     # assert wait_for_transition(a, STATES.C, max_retries=25, retry_delay=0.3), "Chain transition did not complete to C"
#     a.refresh_from_db()
#     assert a.status == STATES.C


# @pytest.mark.django_db
# def test_chain_of_transitions_with_error_for_superuser(superuser):
#     """ Test chain of transitions with error for superuser in the middle of the chain.
#     Superuser should raise an error in the go_to_C transition and stay in B state.
#     """
#     a = A.objects.create(name='A', status=STATES.A)
#     assert a.status == STATES.A
#     process = ChainProcess(instance=a)
#     process.go_to_B(user=superuser)
#     # Wait for error to be handled (should stay in B)
#     # time.sleep(1.0)  # Give time for on_commit to fire and failure callback to execute
#     a.refresh_from_db()
#     assert a.status == STATES.B
#     assert a.error == 'Error for superuser'
