import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock
from abstract.logic.test_basic import BasicProcess
from abstract.e2e.utils import get_logs_by_tr_id, LogChecker
from django_logic.exceptions import TransitionNotAllowed
from django_logic.logger import TransitionEventType


@pytest.mark.django_db(transaction=True)
def test_happy_path(user):
    """ Happy path test for basic transition """
    a = A.objects.create(name='A')
    process = BasicProcess(instance=a)
    tr_id = process.go_to_B(user=user, message='test')  # message is not used, we just test ignoring unexpected kwargs

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BasicProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 1')
    logs.check(f'{tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_basic_transition_with_error(superuser):
    """ Test for basic transition with error """
    a = A.objects.create(name='A')
    process = BasicProcess(instance=a)
    tr_id = process.go_to_B(user=superuser) 
    # with pytest.raises(Exception) as exc_info:
    #     process.go_to_B(user=superuser)  # should raise an error for superuser
    # tr_id = exc_info.value.tr_id

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.A
    assert a.error == 'Error for superuser'

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BasicProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 1')
    logs.check(f'{tr_id} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{tr_id} Error for superuser')
    logs.check(f'{tr_id} FailureSideEffects 1')
    logs.check(f'{tr_id} {TransitionEventType.FAILURE_SIDE_EFFECT.value} save_error')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')
    logs.check(f'{tr_id} {TransitionEventType.FAIL.value}: Exception: Error for superuser')


@pytest.mark.django_db(transaction=True)
def test_recovery_after_failure(user, superuser):
    """After a failed transition (superuser error), a regular user can still transition successfully."""
    a = A.objects.create(name='A')
    process = BasicProcess(instance=a)

    # First attempt: superuser triggers an error, state stays A
    tr_id_fail = process.go_to_B(user=superuser)
    # with pytest.raises(Exception) as exc_info:
    #     process.go_to_B(user=superuser)
    # tr_id_fail = exc_info.value.tr_id
    assert wait_state_unlock(process.state), "State should be unlocked after failure"
    a.refresh_from_db()
    assert a.status == STATES.A
    assert a.error == 'Error for superuser'

    # Second attempt: regular user succeeds, state goes to B
    tr_id_ok = process.go_to_B(user=user)
    assert tr_id_ok is not None
    assert tr_id_ok != tr_id_fail, "Should be a new transition ID"
    assert wait_state_unlock(process.state), "State should be unlocked after success"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id_ok, as_dict=True))
    logs.check(f'{tr_id_ok} {TransitionEventType.START.value} BasicProcess go_to_B {process.state.instance_key} {tr_id_ok} {tr_id_ok}')
    logs.check(f'{tr_id_ok} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id_ok} SideEffects 1')
    logs.check(f'{tr_id_ok} {TransitionEventType.SIDE_EFFECT.value} error_for_superuser')
    logs.check(f'{tr_id_ok} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id_ok} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id_ok} Callbacks 0')


@pytest.mark.django_db(transaction=True)
def test_invalid_source_state(user):
    """Transition from an invalid source state should raise TransitionNotAllowed."""
    a = A.objects.create(name='A', status=STATES.B)
    process = BasicProcess(instance=a)

    with pytest.raises(TransitionNotAllowed):
        process.go_to_B(user=user)

    a.refresh_from_db()
    assert a.status == STATES.B, "State should remain unchanged"


@pytest.mark.django_db(transaction=True)
def test_transition_without_user():
    """Side effect raises 'User is required' when no user is provided."""
    a = A.objects.create(name='A')
    process = BasicProcess(instance=a)
    tr_id = process.go_to_B(user=None)
    # with pytest.raises(Exception) as exc_info:
    #     process.go_to_B(user=None)
    # tr_id = exc_info.value.tr_id

    assert wait_state_unlock(process.state), "State should be unlocked after failure"
    a.refresh_from_db()
    assert a.status == STATES.A, "State should remain A after error"

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BasicProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 1')
    logs.check(f'{tr_id} {TransitionEventType.SIDE_EFFECT.value}')
    logs.check(f'{tr_id} User is required')
    logs.check(f'{tr_id} FailureSideEffects 1')
    logs.check(f'{tr_id} {TransitionEventType.FAILURE_SIDE_EFFECT.value} save_error')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 0')
    # logs.check(f'{tr_id} {TransitionEventType.FAIL.value}:')


@pytest.mark.django_db(transaction=True)
def test_transition_with_failed_callback(superuser):
    """Callback exception should not fail transition and state should still be updated."""
    a = A.objects.create(name='A')
    process = BasicProcess(instance=a)
    tr_id = process.fail_callback(user=superuser)

    assert tr_id is not None
    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.B

    logs = LogChecker(get_logs_by_tr_id(tr_id, as_dict=True))
    logs.check(f'{tr_id} {TransitionEventType.START.value} BasicProcess fail_callback {process.state.instance_key} {tr_id} {tr_id}')
    logs.check(f'{tr_id} {TransitionEventType.LOCK.value}')
    logs.check(f'{tr_id} SideEffects 0')
    logs.check(f'{tr_id} {TransitionEventType.SET_STATE.value} B')
    logs.check(f'{tr_id} {TransitionEventType.UNLOCK.value}')
    logs.check(f'{tr_id} Callbacks 2')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} error_for_superuser')
    logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} error_for_superuser: Error for superuser')
    # TODO: callback should not stop execution of other callbacks
    # logs.check(f'{tr_id} {TransitionEventType.CALLBACK.value} short_action')
