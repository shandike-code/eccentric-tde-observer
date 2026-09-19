from copy import deepcopy
import pytest
from operations.audit_affine_feedback_histories import require_settled_pair


def fixture():
    claims = {'previous': {'path': 's0', 'sha256': 'a'}, 'final': {'path': 's1', 'sha256': 'b'}}
    return {'status': 'diagnostic_round_complete', 'history': [
        {'input_path': c['path'], 'input_sha256': c['sha256']} for c in claims.values()],
        'diagnostic': {'rounds': [{'endpoints': [1, 2], 'endpoints_claim': claims}]}}


def test_inspects_completed_pair_without_modifying_it():
    state = fixture(); before = deepcopy(state)
    assert require_settled_pair(state)['endpoints'] == [1, 2]
    assert state == before


@pytest.mark.parametrize('case', ['running', 'partial', 'pending', 'missing_map', 'wrong_pair', 'stale_sha'])
def test_rejects_unfinished_or_unrelated_feedback_pair(case):
    state = fixture()
    if case == 'running': state['status'] = 'radiation'
    elif case == 'partial': state['active_map'] = {'iteration': 3}
    elif case == 'pending': state['pending_feedback'] = {'round': 1}
    elif case == 'missing_map': state['history'].pop()
    elif case == 'wrong_pair': state['diagnostic']['rounds'][0]['endpoints'] = [3, 4]
    elif case == 'stale_sha': state['history'][1]['input_sha256'] = 'c'
    with pytest.raises(RuntimeError): require_settled_pair(state)
