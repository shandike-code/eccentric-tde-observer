from copy import deepcopy
import numpy as np
import pytest
from operations.diagnose_history_slow_modes import basis_claims, serial, algebra


def test_basis_requires_consecutive_current_states():
    state = {'history': [{}, {}, {'input_path': 'a', 'input_sha256': 'a', 'output_path': 'b', 'output_sha256': 'b'},
                         {'input_path': 'b', 'input_sha256': 'b', 'output_path': 'c', 'output_sha256': 'c'}]}
    assert [r['sha256'] for r in basis_claims(state)] == ['a', 'b', 'c']
    broken = deepcopy(state); broken['history'][-1]['input_sha256'] = 'other'
    with pytest.raises(ValueError): basis_claims(broken)
    state['active_map'] = {'iteration': 5}
    with pytest.raises(ValueError): basis_claims(state)


def test_nan_is_not_hidden_as_unbounded_positivity_limit():
    assert serial(np.inf) is None
    with pytest.raises(ArithmeticError): serial(np.nan)


def test_reused_algebra_predicts_known_affine_fixed_point_without_writing(tmp_path):
    shape = (2, 2, 2)
    config = {'scan_frequency_chunk': 1, 'diagnostic_frequency_block': 1,
              'minimum_forward_picard_fraction': 1., 'maximum_forward_picard_fraction': 96.}
    before = {}
    for i, value in zip((9, 10, 11), (1., 1.5, 1.75), strict=True):
        path = tmp_path / f'x{i}.dat'
        np.full(shape, value).tofile(path)
        config[f'x{i}_state_path'] = str(path)
        before[path] = path.read_bytes()
    direction = algebra._scan_direction(config, shape)
    assert direction['selected_forward_fraction'] == 2.
    metrics = algebra._candidate_metrics(config, shape, 2., np.array([1., 2., 3.]))
    assert metrics['predicted_global_original_operator_residual'] == 0.
    assert metrics['candidate_negative_count'] == 0
    assert all(path.read_bytes() == data for path, data in before.items())
