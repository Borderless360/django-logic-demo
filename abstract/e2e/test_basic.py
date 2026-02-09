import pytest
from abstract.models import A, STATES
from abstract.e2e.utils import wait_state_unlock
from abstract.logic.test_basic import BasicProcess
from abstract.e2e.utils import get_logs_by_tr_id


# @pytest.mark.django_db(transaction=True)
# def test_basic_transition(user):

#     a = A.objects.create(name='A')
#     process = BasicProcess(instance=a)
#     tr_id = process.go_to_B(user=user)

#     assert tr_id is not None
#     assert wait_state_unlock(process.state), "State should be unlocked"
#     a.refresh_from_db()
#     assert a.status == STATES.B

#     logs = get_logs_by_tr_id(tr_id, as_dict=True)
#     assert len(logs) == 7, "Should be 7 logs"
#     assert logs[0]['message'] == f'{tr_id} Start BasicProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
#     assert logs[1]['message'] == f'{tr_id} Lock'
#     assert logs[2]['message'] == f'{tr_id} SideEffects 1'
#     assert logs[3]['message'] == f'{tr_id} SideEffect error_for_superuser'
#     assert logs[4]['message'] == f'{tr_id} Set State B'
#     assert logs[5]['message'] == f'{tr_id} Unlock'
#     assert logs[6]['message'] == f'{tr_id} Callbacks 0'


@pytest.mark.django_db(transaction=True)
def test_basic_transition_with_error(superuser):

    a = A.objects.create(name='A')
    process = BasicProcess(instance=a)
    tr_id = process.go_to_B(user=superuser) # should raise an error for superuser

    assert wait_state_unlock(process.state), "State should be unlocked"
    a.refresh_from_db()
    assert a.status == STATES.A
    assert a.error == 'Error for superuser'

    logs = get_logs_by_tr_id(tr_id, as_dict=True)
    assert len(logs) == 9, "Should be 9 logs"
    assert logs[0]['message'] == f'{tr_id} Start BasicProcess go_to_B {process.state.instance_key} {tr_id} {tr_id}'
    assert logs[1]['message'] == f'{tr_id} Lock'
    assert logs[2]['message'] == f'{tr_id} SideEffects 1'
    assert logs[3]['message'] == f'{tr_id} SideEffect error_for_superuser'
    assert logs[4]['message'] == f'{tr_id} Error for superuser'
    assert logs[5]['message'] == f'{tr_id} FailureSideEffects 1'
    assert logs[6]['message'] == f'{tr_id} FailureSideEffect save_error'
    assert logs[7]['message'] == f'{tr_id} Unlock'
    assert logs[8]['message'] == f'{tr_id} Callbacks 0'
