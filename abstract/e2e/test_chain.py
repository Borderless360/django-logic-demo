import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock, get_all_logs_by_root_id, get_nested_tr_ids, LogChecker
from abstract.logic.test_chain import ChainProcess
from django_logic.logger import TransitionEventType


@pytest.mark.django_db(transaction=True)
def test_chain_happy_path(user):
    """Full chain A -> B -> C -> D completes successfully for a regular user."""
    a = A.objects.create(name='A')
    process = ChainProcess(instance=a)
    tr_id = process.go_to_B(user=user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D

    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=2)
    go_to_C_tr_id, go_to_D_tr_id = nested_tr_ids[0], nested_tr_ids[1]
    logs = LogChecker(get_all_logs_by_root_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} ChainProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 1')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} callback')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{go_to_C_tr_id} SideEffects 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SET_STATE.value} C')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{go_to_C_tr_id} Callbacks 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.CALLBACK.value} callback')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.START.value} ChainProcess go_to_D {process.state.instance_key} {tr_id} {go_to_C_tr_id}')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{go_to_D_tr_id} SideEffects 0')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.SET_STATE.value} D')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{go_to_D_tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_chain_stops_when_user_has_no_permissions(staff_user):
    """Chain stops at C because staff user has no permission to run go_to_D transition."""
    a = A.objects.create(name='A', status=STATES.A)
    process = ChainProcess(instance=a)
    tr_id = process.go_to_B(user=staff_user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.C  # staff user has no permissions to run go_to_D transition
    assert a.error is None       # no permission is not an error, just stop the chain execution

    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=1)
    go_to_C_tr_id = nested_tr_ids[0]
    logs = LogChecker(get_all_logs_by_root_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} ChainProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 1')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} callback')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{go_to_C_tr_id} SideEffects 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SET_STATE.value} C')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{go_to_C_tr_id} Callbacks 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.CALLBACK.value} callback')


@pytest.mark.django_db(transaction=True)
def test_chain_stops_with_error_for_superuser(superuser):
    """Chain fails at go_to_C for superuser due to side_effect error, stopping at B."""
    a = A.objects.create(name='A', status=STATES.A)
    process = ChainProcess(instance=a)
    tr_id = process.go_to_B(user=superuser)  # should raise an error for superuser in the go_to_C transition

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    # go_to_C transition should raise an error for superuser
    assert a.status == STATES.B  
    assert a.error == 'Error for superuser'

    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=1)
    go_to_C_tr_id = nested_tr_ids[0]
    logs = LogChecker(get_all_logs_by_root_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} ChainProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 1')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} callback')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{go_to_C_tr_id} SideEffects 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{go_to_C_tr_id} Callbacks 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.CALLBACK.value} save_error')


@pytest.mark.django_db(transaction=True)
def test_chain_mid_entry_from_B(user):
    """Starting the chain from state B (mid-chain) should continue through C to D."""
    a = A.objects.create(name='A', status=STATES.B)
    process = ChainProcess(instance=a)
    tr_id = process.go_to_C(user=user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D  # chain continues B -> C -> D via callbacks

    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=1)
    go_to_D_tr_id = nested_tr_ids[0]
    logs = LogChecker(get_all_logs_by_root_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 1')
    logs.check(f'{tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} C')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 1')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} callback')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.START.value} ChainProcess go_to_D {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{go_to_D_tr_id} SideEffects 0')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.SET_STATE.value} D')
    logs.check(f'{go_to_D_tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{go_to_D_tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_chain_recovery_after_mid_chain_failure(user, superuser):
    """After superuser fails at go_to_C (stuck at B), a regular user can resume the chain from B."""
    a = A.objects.create(name='A')
    process = ChainProcess(instance=a)

    # First: superuser triggers the full chain, fails at go_to_C side_effect
    tr_id_fail = process.go_to_B(user=superuser)
    assert wait_state_unlock(process.state), "State should be unlocked after failure"
    a.refresh_from_db()
    assert a.status == STATES.B
    assert a.error == 'Error for superuser'

    nested_fail = get_nested_tr_ids(tr_id_fail, expected_count=1)
    go_to_C_tr_id = nested_fail[0]
    logs_fail = LogChecker(get_all_logs_by_root_id(tr_id_fail, as_dict=True))
    logs_fail.check(f'{tr_id_fail} {TransitionEventType.START.value} ChainProcess go_to_B {process.state.instance_key} {tr_id_fail} {tr_id_fail}')
    logs_fail.check(f'{tr_id_fail} {TransitionEventType.LOCK.value}')
    logs_fail.check(f'{tr_id_fail} SideEffects 0')
    logs_fail.check(f'{tr_id_fail} {TransitionEventType.SET_STATE.value} B')
    logs_fail.check(f'{tr_id_fail} {TransitionEventType.UNLOCK.value}')
    logs_fail.check(f'{tr_id_fail} Callbacks 1')
    logs_fail.check(f'{tr_id_fail} {TransitionEventType.CALLBACK.value} callback')
    logs_fail.check(f'{go_to_C_tr_id} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id_fail} {tr_id_fail}')
    logs_fail.check(f'{go_to_C_tr_id} {TransitionEventType.LOCK.value}')
    logs_fail.check(f'{go_to_C_tr_id} SideEffects 1')
    logs_fail.check(f'{go_to_C_tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs_fail.check(f'{go_to_C_tr_id} {TransitionEventType.SET_STATE.value} B')
    logs_fail.check(f'{go_to_C_tr_id} {TransitionEventType.UNLOCK.value}')
    logs_fail.check(f'{go_to_C_tr_id} Callbacks 1')
    logs_fail.check(f'{go_to_C_tr_id} {TransitionEventType.CALLBACK.value} save_error')

    # Second: regular user resumes from B by calling go_to_C directly
    process = ChainProcess(instance=a)
    tr_id_ok = process.go_to_C(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after recovery"
    a.refresh_from_db()
    assert a.status == STATES.D  # chain completes B -> C -> D

    nested_ok = get_nested_tr_ids(tr_id_ok, expected_count=1)
    go_to_D_tr_id = nested_ok[0]
    logs_ok = LogChecker(get_all_logs_by_root_id(tr_id_ok, as_dict=True))
    logs_ok.check(f'{tr_id_ok} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id_ok} {tr_id_ok}')
    logs_ok.check(f'{tr_id_ok} {TransitionEventType.LOCK.value}')
    logs_ok.check(f'{tr_id_ok} SideEffects 1')
    logs_ok.check(f'{tr_id_ok} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs_ok.check(f'{tr_id_ok} {TransitionEventType.SET_STATE.value} C')
    logs_ok.check(f'{tr_id_ok} {TransitionEventType.UNLOCK.value}')
    logs_ok.check(f'{tr_id_ok} Callbacks 1')
    logs_ok.check(f'{tr_id_ok} {TransitionEventType.CALLBACK.value} callback')
    logs_ok.check(f'{go_to_D_tr_id} {TransitionEventType.START.value} ChainProcess go_to_D {process.state.instance_key} {tr_id_ok} {tr_id_ok}')
    logs_ok.check(f'{go_to_D_tr_id} {TransitionEventType.LOCK.value}')
    logs_ok.check(f'{go_to_D_tr_id} SideEffects 0')
    logs_ok.check(f'{go_to_D_tr_id} {TransitionEventType.SET_STATE.value} D')
    logs_ok.check(f'{go_to_D_tr_id} {TransitionEventType.UNLOCK.value}')
    logs_ok.check(f'{go_to_D_tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_chain_with_no_user():
    """When no user is provided, go_to_B succeeds but go_to_C fails with 'User is required'."""
    a = A.objects.create(name='A')
    process = ChainProcess(instance=a)
    tr_id = process.go_to_B(user=None)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.B       # go_to_B succeeded, but go_to_C failed in callback
    assert a.error == 'User is required'  # error_for_superuser raises when no user

    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=1)
    go_to_C_tr_id = nested_tr_ids[0]
    logs = LogChecker(get_all_logs_by_root_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} ChainProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 1')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} callback')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.START.value} ChainProcess go_to_C {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{go_to_C_tr_id} SideEffects 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{go_to_C_tr_id} Callbacks 1')
    logs.check(f'{go_to_C_tr_id} {TransitionEventType.CALLBACK.value} save_error')
