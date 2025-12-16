import pytest
from abstract.models import A, STATES
from django_logic import Process
from core.transition import BaseProcess, ProxyTransition as Transition
from core.logic.side_effects import error_for_superuser
from core.logic.conditions import is_user
from abstract.logic.callbacks import save_error


def run_action(action_name):
    def callback(obj, *args, **kwargs):
        process = ChainProcess(instance=obj)
        action_method = getattr(process, action_name)
        action_method(*args, **kwargs)
    return callback

class ChainProcess(BaseProcess):
    transitions = [
        Transition('go_to_B', [STATES.A], STATES.B, callbacks=[run_action('go_to_C')]),
        Transition('go_to_C', [STATES.B], STATES.C, callbacks=[run_action('go_to_D')], side_effects=[error_for_superuser], failure_callbacks=[save_error]), 
        Transition('go_to_D', [STATES.C], STATES.D, permissions=[is_user]),
    ]


@pytest.mark.django_db
def test_chain_of_transitions(user):
    a = A.objects.create(name='A')
    assert a.status == STATES.A

    process = ChainProcess(instance=a)
    process.go_to_B(user=user)
    a.refresh_from_db()
    assert a.status == STATES.D


@pytest.mark.django_db
def test_chain_of_transitions_with_no_permissions(staff_user):
    """ Test chain of transitions with no permissions in the middle of the chain.
    Staff user have no permissions to run go_to_D transition, so it should be stay in C state.
    """
    a = A.objects.create(name='A', status=STATES.A)
    assert a.status == STATES.A

    process = ChainProcess(instance=a)
    process.go_to_B(user=staff_user)
    a.refresh_from_db()
    assert a.status == STATES.C


@pytest.mark.django_db
def test_chain_of_transitions_with_error_for_superuser(superuser):
    """ Test chain of transitions with error for superuser in the middle of the chain.
    Superuser should raise an error in the go_to_C transition and stay in B state.
    """
    a = A.objects.create(name='A', status=STATES.A)
    assert a.status == STATES.A
    process = ChainProcess(instance=a)
    process.go_to_B(user=superuser)
    a.refresh_from_db()
    assert a.status == STATES.B
    assert a.error == 'Error for superuser'
