import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock, get_logs_by_tr_id, LogChecker
from abstract.logic.test_branch import BranchProcess
from django_logic.exceptions import TransitionNotAllowed
from django_logic.logger import TransitionEventType


# ────────────────────────────────────────────────────────────
# Permission-based branching
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_branch_user_goes_to_B(user):
    """Regular user takes 'go_next' and lands at state B."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)
    tr_id = process.go_next(user=user)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_next {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_branch_superuser_goes_to_C(superuser):
    """Superuser takes 'go_next' and lands at state C."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)
    tr_id = process.go_next(user=superuser)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.C

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_next {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} C')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_branch_staff_no_valid_path(staff_user):
    """Staff user matches neither is_user nor is_superuser — no valid branch exists."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)

    with pytest.raises(TransitionNotAllowed):
        process.go_next(user=staff_user)

    a.refresh_from_db()
    assert a.status == STATES.A, "State should remain unchanged"


@pytest.mark.django_db(transaction=True)
def test_branch_no_user_ambiguous():
    """With user=None both permission gates pass, creating an ambiguous branch."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)

    with pytest.raises(TransitionNotAllowed):
        process.go_next(user=None)

    a.refresh_from_db()
    assert a.status == STATES.A, "State should remain unchanged"


# ────────────────────────────────────────────────────────────
# Condition-based branching
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_conditional_branch_special(user):
    """Instance named 'special' takes 'conditional_go' and lands at E."""
    a = A.objects.create(name='special')
    process = BranchProcess(instance=a)
    tr_id = process.conditional_go(user=user)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.E

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess conditional_go {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} E')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_conditional_branch_not_special(user):
    """Instance with a regular name takes 'conditional_go' and lands at F."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)
    tr_id = process.conditional_go(user=user)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.F

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess conditional_go {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} F')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


# ────────────────────────────────────────────────────────────
# Convergence (fan-in)
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_converge_from_B_to_D(user):
    """After branching to B, 'go_to_D' converges to state D."""
    a = A.objects.create(name='A', status=STATES.B)
    process = BranchProcess(instance=a)
    tr_id = process.go_to_D(user=user)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_to_D {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} D')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_converge_from_C_to_D(user):
    """After branching to C, 'go_to_D' converges to state D."""
    a = A.objects.create(name='A', status=STATES.C)
    process = BranchProcess(instance=a)
    tr_id = process.go_to_D(user=user)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_to_D {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} D')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


# ────────────────────────────────────────────────────────────
# Branch → then converge (full path)
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_branch_then_converge_user(user):
    """Regular user branches A→B via 'go_next', then converges B→D via 'go_to_D'."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)

    # Branch to B
    tr_id_1 = process.go_next(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after branch"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id_1, as_dict=True))
    logs.check(f'{tr_id_1} {TransitionEventType.START.value} BranchProcess go_next {process.state.instance_key} {tr_id_1} {tr_id_1}')
    logs.check(f'{tr_id_1} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id_1} SideEffects 0')
    logs.check(f'{tr_id_1} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id_1} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id_1} Callbacks 0')

    # Converge to D
    process = BranchProcess(instance=a)
    tr_id_2 = process.go_to_D(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after converge"
    a.refresh_from_db()
    assert a.status == STATES.D

    logs = LogChecker(get_logs_by_tr_id(tr_id_2, as_dict=True))
    logs.check(f'{tr_id_2} {TransitionEventType.START.value} BranchProcess go_to_D {process.state.instance_key} {tr_id_2} {tr_id_2}')
    logs.check(f'{tr_id_2} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id_2} SideEffects 0')
    logs.check(f'{tr_id_2} {TransitionEventType.SET_STATE.value} D')
    logs.check(f'{tr_id_2} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id_2} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_branch_then_converge_superuser(superuser, user):
    """Superuser branches A→C via 'go_next', then converges C→D via 'go_to_D'."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)

    # Branch to C
    tr_id_1 = process.go_next(user=superuser)
    assert wait_state_unlock(process.state), "State should be unlocked after branch"
    a.refresh_from_db()
    assert a.status == STATES.C

    logs = LogChecker(get_logs_by_tr_id(tr_id_1, as_dict=True))
    logs.check(f'{tr_id_1} {TransitionEventType.START.value} BranchProcess go_next {process.state.instance_key} {tr_id_1} {tr_id_1}')
    logs.check(f'{tr_id_1} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id_1} SideEffects 0')
    logs.check(f'{tr_id_1} {TransitionEventType.SET_STATE.value} C')
    logs.check(f'{tr_id_1} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id_1} Callbacks 0')

    # Converge to D
    process = BranchProcess(instance=a)
    tr_id_2 = process.go_to_D(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after converge"
    a.refresh_from_db()
    assert a.status == STATES.D

    logs = LogChecker(get_logs_by_tr_id(tr_id_2, as_dict=True))
    logs.check(f'{tr_id_2} {TransitionEventType.START.value} BranchProcess go_to_D {process.state.instance_key} {tr_id_2} {tr_id_2}')
    logs.check(f'{tr_id_2} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id_2} SideEffects 0')
    logs.check(f'{tr_id_2} {TransitionEventType.SET_STATE.value} D')
    logs.check(f'{tr_id_2} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id_2} Callbacks 0')


# ────────────────────────────────────────────────────────────
# Branch + chain (callback auto-continues)
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_branch_and_chain(user):
    """'go_and_chain' branches to B, then callback auto-triggers 'go_to_D' → arrives at D."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)
    tr_id = process.go_and_chain(user=user)

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.D

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_and_chain {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 1')
    logs.check(f'{tr_id} Callback callback')


# ────────────────────────────────────────────────────────────
# Recovery: fail on one branch, succeed via another
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_branch_recovery_after_no_permission(staff_user, user):
    """Staff user fails 'go_next' (no matching branch), then regular user succeeds."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)

    # Staff user: no valid branch
    with pytest.raises(TransitionNotAllowed):
        process.go_next(user=staff_user)
    a.refresh_from_db()
    assert a.status == STATES.A

    # Regular user: succeeds on the is_user branch
    process = BranchProcess(instance=a)
    tr_id = process.go_next(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after recovery"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_next {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_branch_recovery_after_ambiguous(user):
    """Ambiguous branch with user=None fails, then specific user succeeds."""
    a = A.objects.create(name='A')
    process = BranchProcess(instance=a)

    # None user: ambiguous (both branches valid)
    with pytest.raises(TransitionNotAllowed):
        process.go_next(user=None)
    a.refresh_from_db()
    assert a.status == STATES.A

    # Regular user: succeeds on the is_user branch
    process = BranchProcess(instance=a)
    tr_id = process.go_next(user=user)
    assert wait_state_unlock(process.state), "State should be unlocked after recovery"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BranchProcess go_next {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


# ────────────────────────────────────────────────────────────
# Invalid source state
# ────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_branch_from_wrong_source(user):
    """Attempting 'go_next' from state D (not a valid source) raises TransitionNotAllowed."""
    a = A.objects.create(name='A', status=STATES.D)
    process = BranchProcess(instance=a)

    with pytest.raises(TransitionNotAllowed):
        process.go_next(user=user)

    a.refresh_from_db()
    assert a.status == STATES.D, "State should remain unchanged"
