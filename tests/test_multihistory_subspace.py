import numpy as np
import pytest
from operations.scan_multihistory_subspace import solve_direction, residual_system, fields, bounded_step, prediction_metrics
from operations.prepare_cross_feedback import validated_cross_seed


def files(tmp_path, arrays):
    paths = [tmp_path/str(i) for i in range(len(arrays))]
    for p, a in zip(paths, arrays): np.asarray(a, dtype=np.float64).tofile(p)
    return paths


def test_resolved_psd_system_and_degenerate_mode():
    c, info = solve_direction(np.diag([1., 2., 0.]), np.array([2., 4., 0.]))
    assert np.allclose(c, [2., 2., 0.]) and info['retained_rank'] == 2


@pytest.mark.parametrize('g', [np.diag([1., 2., -1.]), np.full((3, 3), np.nan)])
def test_invalid_small_system_rejected(g):
    with pytest.raises((ValueError, ArithmeticError)): solve_direction(g, np.ones(3))


def test_three_resolved_modes_recover_known_affine_fixed_point(tmp_path):
    root = np.full((1, 4, 2), 10.)
    q = np.array([.2, .5, .9, .2, .5, .9, .2, .5]).reshape(root.shape)
    b0 = root+np.array([1., 2., 3., 1., 2., 3., 1., 2.]).reshape(root.shape)
    o0 = root+np.array([3., -1., 1., 3., -1., 1., 3., -1.]).reshape(root.shape)
    transform = lambda x: root+q*(x-root)
    b1 = transform(b0); o1 = transform(o0)
    arrays = [b0, b1, transform(b1), o0, o1, transform(o1)]
    paths = files(tmp_path, arrays); before = [p.read_bytes() for p in paths]
    anchor = np.array([0., .8, 0., .2])
    target, info = residual_system(paths, root.shape, anchor)
    assert info['retained_rank'] == 3 and target.sum() == pytest.approx(1.)
    x, y = fields(arrays, target)
    assert np.max(abs(x-root)) < 1e-9 and np.max(abs(y-root)) < 1e-9
    step, bounds = bounded_step(paths, root.shape, anchor, target)
    assert step == 1. and bounds['effective_coefficient_l1'] < 32.
    result = prediction_metrics(paths, root.shape, anchor, target, step, np.array([1., 2.]))
    assert result['predicted_residual'] < 1e-10
    assert [p.read_bytes() for p in paths] == before


def test_negative_raw_combination_requires_global_backtracking(tmp_path):
    shape = (1, 4, 2)
    arrays = [np.full(shape, x) for x in (1., 1., 1., 10., 10., 10.)]
    anchor = np.array([0., 1., 0., 0.]); target = np.array([0., 2., 0., -1.])
    paths = files(tmp_path, arrays)
    step, bounds = bounded_step(paths, shape, anchor, target)
    assert 0 < step < 1/9 and bounds['raw_candidate_negative_count'] == 8
    r = prediction_metrics(paths, shape, anchor, target, step, np.array([1., 2.]))
    assert r['candidate_negative_count'] == r['map_negative_count'] == 0


def test_scalar_only_validation_is_not_a_cross_feedback_seed():
    with pytest.raises(ValueError, match='full-field'): validated_cross_seed({}, {}, {})


def test_full_field_flag_does_not_override_failed_validation():
    r = {'full_intensity_prediction_error_evaluated': True, 'full_field_error': {'prediction_error_resolved': True}}
    with pytest.raises(ValueError): validated_cross_seed({}, {'status': 'failed'}, r)
