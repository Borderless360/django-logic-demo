import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock
from abstract.logic.test_chain import ChainProcess


@pytest.mark.django_db(transaction=True)
def test_chain_happy_path(user):
    """Full chain A -> B -> C -> D completes successfully for a regular user."""
    a = A.objects.create(name='A')
    process = ChainProcess(instance=a)
    process.go_to_B(user=user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D


@pytest.mark.django_db(transaction=True)
def test_chain_stops_when_user_has_no_permissions(staff_user):
    """Chain stops at C because staff user has no permission to run go_to_D transition."""
    a = A.objects.create(name='A', status=STATES.A)
    process = ChainProcess(instance=a)
    process.go_to_B(user=staff_user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.C  # staff user has no permissions to run go_to_D transition
    assert a.error is None       # no permission is not an error, just stop the chain execution


@pytest.mark.django_db(transaction=True)
def test_chain_stops_with_error_for_superuser(superuser):
    """Chain fails at go_to_C for superuser due to side_effect error, stopping at B."""
    a = A.objects.create(name='A', status=STATES.A)
    process = ChainProcess(instance=a)
    process.go_to_B(user=superuser)  # should raise an error for superuser in the go_to_C transition

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    # go_to_C transition should raise an error for superuser
    assert a.status == STATES.B  
    assert a.error == 'Error for superuser'


@pytest.mark.django_db(transaction=True)
def test_chain_mid_entry_from_B(user):
    """Starting the chain from state B (mid-chain) should continue through C to D."""
    a = A.objects.create(name='A', status=STATES.B)
    process = ChainProcess(instance=a)
    process.go_to_C(user=user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D  # chain continues B -> C -> D via callbacks


@pytest.mark.django_db(transaction=True)
def test_chain_recovery_after_mid_chain_failure(user, superuser):
    """After superuser fails at go_to_C (stuck at B), a regular user can resume the chain from B."""
    a = A.objects.create(name='A')
    process = ChainProcess(instance=a)

    # First: superuser triggers the full chain, fails at go_to_C side_effect
    process.go_to_B(user=superuser)
    assert wait_state_unlock(process.state), "State should be unlocked after failure"
    a.refresh_from_db()
    assert a.status == STATES.B
    assert a.error == 'Error for superuser'

    # Second: regular user resumes from B by calling go_to_C directly
    process = ChainProcess(instance=a)
    process.go_to_C(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after recovery"
    a.refresh_from_db()
    assert a.status == STATES.D  # chain completes B -> C -> D


@pytest.mark.django_db(transaction=True)
def test_chain_with_no_user():
    """When no user is provided, go_to_B succeeds but go_to_C fails with 'User is required'."""
    a = A.objects.create(name='A')
    process = ChainProcess(instance=a)
    process.go_to_B(user=None)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.B       # go_to_B succeeded, but go_to_C failed in callback
    assert a.error == 'User is required'  # error_for_superuser raises when no user
