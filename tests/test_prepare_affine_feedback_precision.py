from copy import deepcopy

import pytest

from operations.prepare_affine_feedback_precision import validated_seed


def fixture():
    row = {'input_sha256': 'a' * 64, 'output_path': 'mapped.dat', 'output_sha256': 'b' * 64}
    state = {'status': 'radiation', 'history': [row], 'slots': ['candidate.dat', 'mapped.dat'],
             'current_slot': 1, 'current_sha256': 'b' * 64, 'active_map': None}
    status = {'status': 'complete', 'new_maps': 1, 'extrapolation_validated': True}
    result = {'actual_map': deepcopy(row), 'candidate': {'sha256': 'a' * 64},
              'extrapolation_validated': True, 'validation_checks': {'actual_improvement': True}}
    return state, status, result


def test_continuation_uses_real_output_without_grafting_history():
    state, status, result = fixture()
    before = deepcopy(state)
    assert validated_seed(state, status, result)['path'] == 'mapped.dat'
    assert state == before


@pytest.mark.parametrize('case', [
    'pending', 'partial', 'wrong_slot', 'wrong_hash', 'extra_history',
    'prediction_only', 'failed_validation', 'stale_result', 'wrong_candidate',
])
def test_rejects_incomplete_or_unrelated_validation(case):
    state, status, result = fixture()
    if case == 'pending': state['pending_feedback'] = {'round': 1}
    elif case == 'partial': state['active_map'] = {'iteration': 2}
    elif case == 'wrong_slot': state['current_slot'] = 0
    elif case == 'wrong_hash': state['current_sha256'] = 'c' * 64
    elif case == 'extra_history': state['history'].append(deepcopy(state['history'][0]))
    elif case == 'prediction_only': status['status'] = 'preparing'
    elif case == 'failed_validation': result['validation_checks']['actual_improvement'] = False
    elif case == 'stale_result': result['actual_map']['output_sha256'] = 'c' * 64
    elif case == 'wrong_candidate': result['candidate']['sha256'] = 'c' * 64
    with pytest.raises(ValueError): validated_seed(state, status, result)
