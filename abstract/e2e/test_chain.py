import pytest
from abstract.models import A, STATES
from django_logic import Process
from core.transition import ProxyTransition as Transition
from core.logic.callbacks import run_action
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user


class ChainProcess(Process):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, callbacks=[run_action('go_to_C')]),
        Transition('go_to_C', [STATES.B], STATES.C, callbacks=[run_action('go_to_D')], side_effects=[error_for_superuser]), 
        Transition('go_to_D', [STATES.C], STATES.D, permissions=[is_user]),
    ]


@pytest.mark.django_db
def test_chain_of_transitions(user):
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = ChainProcess(instance=a, field_name='status')
    process.go_to_B(user=user)
    a.refresh_from_db()
    assert a.status == STATES.B


# @pytest.mark.django_db
# def test_chain_of_transitions_with_no_permissions(staff_user):
#     """ Test chain of transitions with no permissions in the middle: C0_C1 -> C1_C2 -> C2_C3.
#     Staff user have no permissions to run C2_C3 transition, so it should be stay in C2 state.
#     """
#     c = C.objects.create(name='C', status=C_STATES.C0)
#     assert c.status == C_STATES.C0
#     c.process.C0_C1(user=staff_user)
#     c.refresh_from_db()
#     assert c.status == C_STATES.C2


# @pytest.mark.django_db
# def test_chain_of_transitions_with_error_for_superuser(superuser):
#     """ Test chain of transitions with error for superuser: C0_C1 -> C1_C2 -> C2_C3.
#     Superuser should raise an error in the C2_C3 transition and stay in C1 state.
#     """
#     c = C.objects.create(name='C', status=C_STATES.C0)
#     assert c.status == C_STATES.C0
#     c.process.C0_C1(user=superuser)
#     c.refresh_from_db()
#     assert c.status == C_STATES.C1
