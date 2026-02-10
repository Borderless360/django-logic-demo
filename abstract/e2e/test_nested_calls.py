import pytest
from abstract.models import A, B, C, STATES
from abstract.logic.test_nested_calls import AProcess, BProcess, CProcess
from abstract.e2e.utils import wait_state_unlock, get_nested_tr_ids, get_all_logs_by_root_id


@pytest.mark.django_db(transaction=True)
def test_nested_calls_happy_path(user):
    """Test that nested process calls propagate transitions through the full chain.

    Sets up a chain of linked objects: A -> B -> C. When AProcess.go_to_B is
    triggered, it fires BProcess.go_to_B as a side effect, which in turn fires
    CProcess.go_to_B. With a regular user (who has `is_user` permission), all
    three transitions should complete successfully, moving every object from
    state A to state B.
    """
    # Create the object chain: C <- B <- A
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    process = AProcess(instance=a)
    tr_id = process.go_to_B(user=user)
    
    # State A should be unloacked after B and C 
    assert wait_state_unlock(process.state), "State A should be unlocked"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.B
    assert b.status == STATES.B
    assert c.status == STATES.B

    # Get all logs across AProcess, BProcess, and CProcess in execution order
    logs = get_all_logs_by_root_id(tr_id, expected_count=20, as_dict=True)
    assert len(logs) == 20, f"Should be 20 logs total (A:7 + B:7 + C:6), got {len(logs)}"

    # Extract nested tr_ids from Start messages
    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=2)
    b_tr_id = nested_tr_ids[0]
    c_tr_id = nested_tr_ids[1]
    b_process = BProcess(instance=b)
    c_process = CProcess(instance=c)

    # Full interleaved execution sequence: A starts -> B starts -> C completes -> B completes -> A completes
    assert logs[0]['message'] == f'{tr_id} Start AProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
    assert logs[1]['message'] == f'{tr_id} Lock'
    assert logs[2]['message'] == f'{tr_id} SideEffects 1'
    assert logs[3]['message'] == f'{tr_id} SideEffect run_b_action'
    # BProcess starts inside AProcess's run_b_action side effect
    assert logs[4]['message'] == f'{b_tr_id} Start AProcess go_to_B {b_process.state.instance_key} {tr_id} {tr_id}'
    assert logs[5]['message'] == f'{b_tr_id} Lock'
    assert logs[6]['message'] == f'{b_tr_id} SideEffects 1'
    assert logs[7]['message'] == f'{b_tr_id} SideEffect run_c_action'
    # CProcess starts inside BProcess's run_c_action side effect
    assert logs[8]['message'] == f'{c_tr_id} Start AProcess go_to_B {c_process.state.instance_key} {tr_id} {b_tr_id}'
    assert logs[9]['message'] == f'{c_tr_id} Lock'
    assert logs[10]['message'] == f'{c_tr_id} SideEffects 0'
    assert logs[11]['message'] == f'{c_tr_id} Set State B'
    assert logs[12]['message'] == f'{c_tr_id} Unlock'
    assert logs[13]['message'] == f'{c_tr_id} Callbacks 0'
    # CProcess done, BProcess completes
    assert logs[14]['message'] == f'{b_tr_id} Set State B'
    assert logs[15]['message'] == f'{b_tr_id} Unlock'
    assert logs[16]['message'] == f'{b_tr_id} Callbacks 0'
    # BProcess done, AProcess completes
    assert logs[17]['message'] == f'{tr_id} Set State B'
    assert logs[18]['message'] == f'{tr_id} Unlock'
    assert logs[19]['message'] == f'{tr_id} Callbacks 0'


@pytest.mark.django_db(transaction=True)
def test_nested_calls_with_no_permissions(staff_user):
    """Test that a permission failure in a nested process rolls back the entire chain.

    A staff_user does not satisfy the `is_user` or `is_superuser` permission
    checks on CProcess.go_to_B. When the deepest nested transition (C) is
    rejected due to missing permissions, the error should propagate back up
    through BProcess and AProcess, leaving all objects in their original state A.
    The error message should reference the failing process class and the user.
    C itself should have no error because its transition was never executed.
    """
    # Create the object chain: C <- B <- A
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    process = AProcess(instance=a)
    tr_id = process.go_to_B(user=staff_user)

    # State A should be unloacked after B and C 
    assert wait_state_unlock(process.state), "State A should be unlocked"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    # staff_user has no permissions to run go_to_B transition in CProcess, 
    # so the last transition is not run, but BProcess is run and raises an error
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A
    assert a.error.startswith("Process class") and staff_user.username in a.error
    assert b.error.startswith("Process class") and staff_user.username in b.error
    assert c.error is None  # nothing happened in CProcess

    # Get all logs across AProcess and BProcess in execution order
    # CProcess never starts (no matching transition for staff_user)
    logs = get_all_logs_by_root_id(tr_id, expected_count=18, as_dict=True)
    assert len(logs) == 18, f"Should be 18 logs total (A:9 + B:9, C never starts), got {len(logs)}"

    # Extract nested tr_id (only BProcess, CProcess never started)
    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=1)
    assert len(nested_tr_ids) == 1, "Should have 1 nested transition ID (BProcess only)"
    b_tr_id = nested_tr_ids[0]
    b_process = BProcess(instance=b)

    # Full interleaved sequence: A starts -> B starts -> C permission denied -> B fails -> A fails
    assert logs[0]['message'] == f'{tr_id} Start AProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
    assert logs[1]['message'] == f'{tr_id} Lock'
    assert logs[2]['message'] == f'{tr_id} SideEffects 1'
    assert logs[3]['message'] == f'{tr_id} SideEffect run_b_action'
    # BProcess starts inside AProcess's run_b_action side effect
    assert logs[4]['message'] == f'{b_tr_id} Start AProcess go_to_B {b_process.state.instance_key} {tr_id} {tr_id}'
    assert logs[5]['message'] == f'{b_tr_id} Lock'
    assert logs[6]['message'] == f'{b_tr_id} SideEffects 1'
    assert logs[7]['message'] == f'{b_tr_id} SideEffect run_c_action'
    # CProcess has no matching transition for staff_user -> TransitionNotAllowed
    assert logs[8]['message'].startswith(f'{b_tr_id} Process class') and staff_user.username in logs[8]['message']
    assert logs[9]['message'] == f'{b_tr_id} FailureSideEffects 0'
    assert logs[10]['message'] == f'{b_tr_id} Unlock'
    assert logs[11]['message'] == f'{b_tr_id} Callbacks 1'
    assert logs[12]['message'] == f'{b_tr_id} Callback save_error'
    # BProcess error propagates to AProcess
    assert logs[13]['message'].startswith(f'{tr_id} Process class') and staff_user.username in logs[13]['message']
    assert logs[14]['message'] == f'{tr_id} FailureSideEffects 0'
    assert logs[15]['message'] == f'{tr_id} Unlock'
    assert logs[16]['message'] == f'{tr_id} Callbacks 1'
    assert logs[17]['message'] == f'{tr_id} Callback save_error'


@pytest.mark.django_db(transaction=True)
def test_nested_calls_with_error(superuser):
    """Test that a side-effect error in the deepest nested process propagates to all parents.

    A superuser matches the `is_superuser` permission on CProcess.go_to_B, which
    runs the `error_for_superuser` side effect. This side effect raises an error
    during C's transition. The error should bubble up through BProcess and
    AProcess via their failure_callbacks (`save_error`), rolling back all objects
    to state A and recording the same error message on every object in the chain.
    """
    # Create the object chain: C <- B <- A
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    process = AProcess(instance=a)
    tr_id = process.go_to_B(user=superuser)

    assert wait_state_unlock(process.state), "State A should be unlocked"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    # any error in the nested process should be propagated to the parent process
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A
    assert a.error == 'Error for superuser'
    assert b.error == 'Error for superuser'
    assert c.error == 'Error for superuser'

    # Get all logs across AProcess, BProcess, and CProcess in execution order
    logs = get_all_logs_by_root_id(tr_id, expected_count=27, as_dict=True)
    assert len(logs) == 27, f"Should be 27 logs total (A:9 + B:9 + C:9), got {len(logs)}"

    # Extract nested tr_ids
    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=2)
    b_tr_id = nested_tr_ids[0]
    c_tr_id = nested_tr_ids[1]
    b_process = BProcess(instance=b)
    c_process = CProcess(instance=c)

    # Full interleaved sequence: A starts -> B starts -> C fails -> B fails -> A fails
    assert logs[0]['message'] == f'{tr_id} Start AProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
    assert logs[1]['message'] == f'{tr_id} Lock'
    assert logs[2]['message'] == f'{tr_id} SideEffects 1'
    assert logs[3]['message'] == f'{tr_id} SideEffect run_b_action'
    # BProcess starts inside AProcess's run_b_action side effect
    assert logs[4]['message'] == f'{b_tr_id} Start AProcess go_to_B {b_process.state.instance_key} {tr_id} {tr_id}'
    assert logs[5]['message'] == f'{b_tr_id} Lock'
    assert logs[6]['message'] == f'{b_tr_id} SideEffects 1'
    assert logs[7]['message'] == f'{b_tr_id} SideEffect run_c_action'
    # CProcess starts inside BProcess's run_c_action side effect (superuser matches is_superuser)
    assert logs[8]['message'] == f'{c_tr_id} Start AProcess go_to_B {c_process.state.instance_key} {tr_id} {b_tr_id}'
    assert logs[9]['message'] == f'{c_tr_id} Lock'
    assert logs[10]['message'] == f'{c_tr_id} SideEffects 1'
    assert logs[11]['message'] == f'{c_tr_id} SideEffect error_for_superuser'
    assert logs[12]['message'] == f'{c_tr_id} Error for superuser'
    assert logs[13]['message'] == f'{c_tr_id} FailureSideEffects 0'
    assert logs[14]['message'] == f'{c_tr_id} Unlock'
    assert logs[15]['message'] == f'{c_tr_id} Callbacks 1'
    assert logs[16]['message'] == f'{c_tr_id} Callback save_error'
    # CProcess error propagates to BProcess
    assert logs[17]['message'] == f'{b_tr_id} Error for superuser'
    assert logs[18]['message'] == f'{b_tr_id} FailureSideEffects 0'
    assert logs[19]['message'] == f'{b_tr_id} Unlock'
    assert logs[20]['message'] == f'{b_tr_id} Callbacks 1'
    assert logs[21]['message'] == f'{b_tr_id} Callback save_error'
    # BProcess error propagates to AProcess
    assert logs[22]['message'] == f'{tr_id} Error for superuser'
    assert logs[23]['message'] == f'{tr_id} FailureSideEffects 0'
    assert logs[24]['message'] == f'{tr_id} Unlock'
    assert logs[25]['message'] == f'{tr_id} Callbacks 1'
    assert logs[26]['message'] == f'{tr_id} Callback save_error'


@pytest.mark.django_db(transaction=True)
def test_nested_calls_recovery_after_error(superuser, user):
    """Test that after a superuser error rolls back the entire chain, a regular user can retry successfully.

    First attempt with superuser triggers `error_for_superuser` in CProcess, which
    propagates the error up through BProcess and AProcess, leaving all objects at
    state A with an error. A second attempt with a regular user (who has `is_user`
    permission) should succeed, moving all objects from state A to state B and
    clearing the error state.
    """
    # Create the object chain: C <- B <- A
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    process = AProcess(instance=a)

    # First attempt: superuser triggers error, all stay at A
    tr_id_fail = process.go_to_B(user=superuser)
    assert wait_state_unlock(process.state), "State A should be unlocked after failure"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A
    assert a.error == 'Error for superuser'

    # Check failed attempt: all 3 processes fail (A:9 + B:9 + C:9 = 27)
    fail_logs = get_all_logs_by_root_id(tr_id_fail, expected_count=27, as_dict=True)
    assert len(fail_logs) == 27, f"Should be 27 logs for failed attempt, got {len(fail_logs)}"

    fail_nested = get_nested_tr_ids(tr_id_fail, expected_count=2)
    b_tr_fail = fail_nested[0]
    c_tr_fail = fail_nested[1]
    b_process = BProcess(instance=b)
    c_process = CProcess(instance=c)

    assert fail_logs[0]['message'] == f'{tr_id_fail} Start AProcess go_to_B {process.state.instance_key} {tr_id_fail} {tr_id_fail}'
    assert fail_logs[1]['message'] == f'{tr_id_fail} Lock'
    assert fail_logs[2]['message'] == f'{tr_id_fail} SideEffects 1'
    assert fail_logs[3]['message'] == f'{tr_id_fail} SideEffect run_b_action'
    assert fail_logs[4]['message'] == f'{b_tr_fail} Start AProcess go_to_B {b_process.state.instance_key} {tr_id_fail} {tr_id_fail}'
    assert fail_logs[5]['message'] == f'{b_tr_fail} Lock'
    assert fail_logs[6]['message'] == f'{b_tr_fail} SideEffects 1'
    assert fail_logs[7]['message'] == f'{b_tr_fail} SideEffect run_c_action'
    assert fail_logs[8]['message'] == f'{c_tr_fail} Start AProcess go_to_B {c_process.state.instance_key} {tr_id_fail} {b_tr_fail}'
    assert fail_logs[9]['message'] == f'{c_tr_fail} Lock'
    assert fail_logs[10]['message'] == f'{c_tr_fail} SideEffects 1'
    assert fail_logs[11]['message'] == f'{c_tr_fail} SideEffect error_for_superuser'
    assert fail_logs[12]['message'] == f'{c_tr_fail} Error for superuser'
    assert fail_logs[13]['message'] == f'{c_tr_fail} FailureSideEffects 0'
    assert fail_logs[14]['message'] == f'{c_tr_fail} Unlock'
    assert fail_logs[15]['message'] == f'{c_tr_fail} Callbacks 1'
    assert fail_logs[16]['message'] == f'{c_tr_fail} Callback save_error'
    assert fail_logs[17]['message'] == f'{b_tr_fail} Error for superuser'
    assert fail_logs[18]['message'] == f'{b_tr_fail} FailureSideEffects 0'
    assert fail_logs[19]['message'] == f'{b_tr_fail} Unlock'
    assert fail_logs[20]['message'] == f'{b_tr_fail} Callbacks 1'
    assert fail_logs[21]['message'] == f'{b_tr_fail} Callback save_error'
    assert fail_logs[22]['message'] == f'{tr_id_fail} Error for superuser'
    assert fail_logs[23]['message'] == f'{tr_id_fail} FailureSideEffects 0'
    assert fail_logs[24]['message'] == f'{tr_id_fail} Unlock'
    assert fail_logs[25]['message'] == f'{tr_id_fail} Callbacks 1'
    assert fail_logs[26]['message'] == f'{tr_id_fail} Callback save_error'

    # Second attempt: regular user succeeds, all move to B
    process = AProcess(instance=a)
    tr_id_ok = process.go_to_B(user=user)
    assert tr_id_ok != tr_id_fail, "Should be a new transition ID"
    assert wait_state_unlock(process.state), "State A should be unlocked after recovery"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.B
    assert b.status == STATES.B
    assert c.status == STATES.B

    # Check successful attempt: all 3 processes succeed (A:7 + B:7 + C:6 = 20)
    ok_logs = get_all_logs_by_root_id(tr_id_ok, expected_count=20, as_dict=True)
    assert len(ok_logs) == 20, f"Should be 20 logs for successful attempt, got {len(ok_logs)}"

    ok_nested = get_nested_tr_ids(tr_id_ok, expected_count=2)
    b_tr_ok = ok_nested[0]
    c_tr_ok = ok_nested[1]

    assert ok_logs[0]['message'] == f'{tr_id_ok} Start AProcess go_to_B {process.state.instance_key} {tr_id_ok} {tr_id_ok}'
    assert ok_logs[1]['message'] == f'{tr_id_ok} Lock'
    assert ok_logs[2]['message'] == f'{tr_id_ok} SideEffects 1'
    assert ok_logs[3]['message'] == f'{tr_id_ok} SideEffect run_b_action'
    assert ok_logs[4]['message'] == f'{b_tr_ok} Start AProcess go_to_B {b_process.state.instance_key} {tr_id_ok} {tr_id_ok}'
    assert ok_logs[5]['message'] == f'{b_tr_ok} Lock'
    assert ok_logs[6]['message'] == f'{b_tr_ok} SideEffects 1'
    assert ok_logs[7]['message'] == f'{b_tr_ok} SideEffect run_c_action'
    assert ok_logs[8]['message'] == f'{c_tr_ok} Start AProcess go_to_B {c_process.state.instance_key} {tr_id_ok} {b_tr_ok}'
    assert ok_logs[9]['message'] == f'{c_tr_ok} Lock'
    assert ok_logs[10]['message'] == f'{c_tr_ok} SideEffects 0'
    assert ok_logs[11]['message'] == f'{c_tr_ok} Set State B'
    assert ok_logs[12]['message'] == f'{c_tr_ok} Unlock'
    assert ok_logs[13]['message'] == f'{c_tr_ok} Callbacks 0'
    assert ok_logs[14]['message'] == f'{b_tr_ok} Set State B'
    assert ok_logs[15]['message'] == f'{b_tr_ok} Unlock'
    assert ok_logs[16]['message'] == f'{b_tr_ok} Callbacks 0'
    assert ok_logs[17]['message'] == f'{tr_id_ok} Set State B'
    assert ok_logs[18]['message'] == f'{tr_id_ok} Unlock'
    assert ok_logs[19]['message'] == f'{tr_id_ok} Callbacks 0'


@pytest.mark.django_db(transaction=True)
def test_nested_calls_recovery_after_permission_failure(staff_user, user):
    """Test that after a permission failure rolls back the chain, a regular user can retry successfully.

    First attempt with staff_user is rejected at CProcess (no `is_user` or
    `is_superuser` permission), rolling back all objects to state A. A second
    attempt with a regular user should succeed, completing the entire chain
    from A to B for all objects.
    """
    # Create the object chain: C <- B <- A
    c = C.objects.create(name='C')
    b = B.objects.create(name='B', c=c)
    a = A.objects.create(name='A', b=b)
    process = AProcess(instance=a)

    # First attempt: staff_user has no permissions at CProcess, all stay at A
    tr_id_fail = process.go_to_B(user=staff_user)
    assert wait_state_unlock(process.state), "State A should be unlocked after permission failure"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert c.status == STATES.A

    # Check failed attempt: A and B fail, C never starts (A:9 + B:9 = 18)
    fail_logs = get_all_logs_by_root_id(tr_id_fail, expected_count=18, as_dict=True)
    assert len(fail_logs) == 18, f"Should be 18 logs for failed attempt, got {len(fail_logs)}"

    fail_nested = get_nested_tr_ids(tr_id_fail, expected_count=1)
    assert len(fail_nested) == 1, "Should have 1 nested transition ID (BProcess only)"
    b_tr_fail = fail_nested[0]
    b_process = BProcess(instance=b)

    assert fail_logs[0]['message'] == f'{tr_id_fail} Start AProcess go_to_B {process.state.instance_key} {tr_id_fail} {tr_id_fail}'
    assert fail_logs[1]['message'] == f'{tr_id_fail} Lock'
    assert fail_logs[2]['message'] == f'{tr_id_fail} SideEffects 1'
    assert fail_logs[3]['message'] == f'{tr_id_fail} SideEffect run_b_action'
    assert fail_logs[4]['message'] == f'{b_tr_fail} Start AProcess go_to_B {b_process.state.instance_key} {tr_id_fail} {tr_id_fail}'
    assert fail_logs[5]['message'] == f'{b_tr_fail} Lock'
    assert fail_logs[6]['message'] == f'{b_tr_fail} SideEffects 1'
    assert fail_logs[7]['message'] == f'{b_tr_fail} SideEffect run_c_action'
    assert fail_logs[8]['message'].startswith(f'{b_tr_fail} Process class') and staff_user.username in fail_logs[8]['message']
    assert fail_logs[9]['message'] == f'{b_tr_fail} FailureSideEffects 0'
    assert fail_logs[10]['message'] == f'{b_tr_fail} Unlock'
    assert fail_logs[11]['message'] == f'{b_tr_fail} Callbacks 1'
    assert fail_logs[12]['message'] == f'{b_tr_fail} Callback save_error'
    assert fail_logs[13]['message'].startswith(f'{tr_id_fail} Process class') and staff_user.username in fail_logs[13]['message']
    assert fail_logs[14]['message'] == f'{tr_id_fail} FailureSideEffects 0'
    assert fail_logs[15]['message'] == f'{tr_id_fail} Unlock'
    assert fail_logs[16]['message'] == f'{tr_id_fail} Callbacks 1'
    assert fail_logs[17]['message'] == f'{tr_id_fail} Callback save_error'

    # Second attempt: regular user succeeds, all move to B
    process = AProcess(instance=a)
    tr_id_ok = process.go_to_B(user=user)
    assert tr_id_ok != tr_id_fail, "Should be a new transition ID"
    assert wait_state_unlock(process.state), "State A should be unlocked after recovery"
    a.refresh_from_db()
    b.refresh_from_db()
    c.refresh_from_db()
    assert a.status == STATES.B
    assert b.status == STATES.B
    assert c.status == STATES.B

    # Check successful attempt: all 3 processes succeed (A:7 + B:7 + C:6 = 20)
    ok_logs = get_all_logs_by_root_id(tr_id_ok, expected_count=20, as_dict=True)
    assert len(ok_logs) == 20, f"Should be 20 logs for successful attempt, got {len(ok_logs)}"

    ok_nested = get_nested_tr_ids(tr_id_ok, expected_count=2)
    b_tr_ok = ok_nested[0]
    c_tr_ok = ok_nested[1]
    c_process = CProcess(instance=c)

    assert ok_logs[0]['message'] == f'{tr_id_ok} Start AProcess go_to_B {process.state.instance_key} {tr_id_ok} {tr_id_ok}'
    assert ok_logs[1]['message'] == f'{tr_id_ok} Lock'
    assert ok_logs[2]['message'] == f'{tr_id_ok} SideEffects 1'
    assert ok_logs[3]['message'] == f'{tr_id_ok} SideEffect run_b_action'
    assert ok_logs[4]['message'] == f'{b_tr_ok} Start AProcess go_to_B {b_process.state.instance_key} {tr_id_ok} {tr_id_ok}'
    assert ok_logs[5]['message'] == f'{b_tr_ok} Lock'
    assert ok_logs[6]['message'] == f'{b_tr_ok} SideEffects 1'
    assert ok_logs[7]['message'] == f'{b_tr_ok} SideEffect run_c_action'
    assert ok_logs[8]['message'] == f'{c_tr_ok} Start AProcess go_to_B {c_process.state.instance_key} {tr_id_ok} {b_tr_ok}'
    assert ok_logs[9]['message'] == f'{c_tr_ok} Lock'
    assert ok_logs[10]['message'] == f'{c_tr_ok} SideEffects 0'
    assert ok_logs[11]['message'] == f'{c_tr_ok} Set State B'
    assert ok_logs[12]['message'] == f'{c_tr_ok} Unlock'
    assert ok_logs[13]['message'] == f'{c_tr_ok} Callbacks 0'
    assert ok_logs[14]['message'] == f'{b_tr_ok} Set State B'
    assert ok_logs[15]['message'] == f'{b_tr_ok} Unlock'
    assert ok_logs[16]['message'] == f'{b_tr_ok} Callbacks 0'
    assert ok_logs[17]['message'] == f'{tr_id_ok} Set State B'
    assert ok_logs[18]['message'] == f'{tr_id_ok} Unlock'
    assert ok_logs[19]['message'] == f'{tr_id_ok} Callbacks 0'


@pytest.mark.django_db(transaction=True)
def test_nested_calls_missing_b_link(user):
    """Test that a missing B link on A causes an error that propagates via failure callbacks.

    When A has no associated B object, the `run_b_action` side effect in AProcess
    will fail when trying to access `obj.b`. This error should be caught and
    recorded via `save_error`, leaving A in state A with an error message.
    """
    a = A.objects.create(name='A')  # no B linked
    process = AProcess(instance=a)
    tr_id = process.go_to_B(user=user)

    assert wait_state_unlock(process.state), "State A should be unlocked after error"
    a.refresh_from_db()
    assert a.status == STATES.A
    assert a.error is not None  # error from accessing None.b

    # Only AProcess logs (no nested processes started, run_b_action fails on obj.b)
    logs = get_all_logs_by_root_id(tr_id, expected_count=9, as_dict=True)
    assert len(logs) == 9, f"Should be 9 logs (A only, no nested), got {len(logs)}"

    assert logs[0]['message'] == f'{tr_id} Start AProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
    assert logs[1]['message'] == f'{tr_id} Lock'
    assert logs[2]['message'] == f'{tr_id} SideEffects 1'
    assert logs[3]['message'] == f'{tr_id} SideEffect run_b_action'
    assert logs[4]['message'].startswith(f'{tr_id} ')  # error message from accessing None.b
    assert logs[5]['message'] == f'{tr_id} FailureSideEffects 0'
    assert logs[6]['message'] == f'{tr_id} Unlock'
    assert logs[7]['message'] == f'{tr_id} Callbacks 1'
    assert logs[8]['message'] == f'{tr_id} Callback save_error'


@pytest.mark.django_db(transaction=True)
def test_nested_calls_missing_c_link(user):
    """Test that a missing C link on B causes an error that propagates up through the chain.

    When B has no associated C object, `run_c_action` in BProcess will fail when
    trying to access `obj.c`. This error should propagate back to AProcess via
    failure callbacks, leaving both A and B in state A with error messages.
    """
    b = B.objects.create(name='B')  # no C linked
    a = A.objects.create(name='A', b=b)
    process = AProcess(instance=a)
    tr_id = process.go_to_B(user=user)

    assert wait_state_unlock(process.state), "State A should be unlocked after error"
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.status == STATES.A
    assert b.status == STATES.A
    assert a.error is not None  # error from accessing None.c
    assert b.error is not None  # error from accessing None.c

    # A and B fail, C never starts (A:9 + B:9 = 18)
    logs = get_all_logs_by_root_id(tr_id, expected_count=18, as_dict=True)
    assert len(logs) == 18, f"Should be 18 logs total (A:9 + B:9, C never starts), got {len(logs)}"

    # Extract nested tr_id (only BProcess, CProcess never started)
    nested_tr_ids = get_nested_tr_ids(tr_id, expected_count=1)
    assert len(nested_tr_ids) == 1, "Should have 1 nested transition ID (BProcess only)"
    b_tr_id = nested_tr_ids[0]
    b_process = BProcess(instance=b)

    # Full interleaved sequence: A starts -> B starts -> C access fails -> B fails -> A fails
    assert logs[0]['message'] == f'{tr_id} Start AProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
    assert logs[1]['message'] == f'{tr_id} Lock'
    assert logs[2]['message'] == f'{tr_id} SideEffects 1'
    assert logs[3]['message'] == f'{tr_id} SideEffect run_b_action'
    # BProcess starts inside AProcess's run_b_action side effect
    assert logs[4]['message'] == f'{b_tr_id} Start AProcess go_to_B {b_process.state.instance_key} {tr_id} {tr_id}'
    assert logs[5]['message'] == f'{b_tr_id} Lock'
    assert logs[6]['message'] == f'{b_tr_id} SideEffects 1'
    assert logs[7]['message'] == f'{b_tr_id} SideEffect run_c_action'
    # run_c_action fails accessing obj.c (None)
    assert logs[8]['message'].startswith(f'{b_tr_id} ')  # error from accessing None.c
    assert logs[9]['message'] == f'{b_tr_id} FailureSideEffects 0'
    assert logs[10]['message'] == f'{b_tr_id} Unlock'
    assert logs[11]['message'] == f'{b_tr_id} Callbacks 1'
    assert logs[12]['message'] == f'{b_tr_id} Callback save_error'
    # BProcess error propagates to AProcess
    assert logs[13]['message'].startswith(f'{tr_id} ')  # same error from accessing None.c
    assert logs[14]['message'] == f'{tr_id} FailureSideEffects 0'
    assert logs[15]['message'] == f'{tr_id} Unlock'
    assert logs[16]['message'] == f'{tr_id} Callbacks 1'
    assert logs[17]['message'] == f'{tr_id} Callback save_error'
