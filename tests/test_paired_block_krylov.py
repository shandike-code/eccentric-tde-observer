import numpy as np
import pytest
from operations.paired_block_krylov import evaluate_direction, verify_map_replay


def test_exact_linear_correction_uses_original_map_and_fixed_scale():
    mapping = lambda x: .75*x+.5
    x = np.array([1., 3.]); y = mapping(x)
    candidate, fresh, report = evaluate_direction(x, y, (y-x)/.25, mapping)
    assert np.array_equal(candidate, np.array([2., 2.]))
    assert np.array_equal(candidate, fresh)
    assert all(report['checks'].values())


def test_bad_direction_is_not_accepted_by_line_search():
    mapping = lambda x: .5*x+1.
    x = np.array([1., 1.]); y = mapping(x)
    _, _, report = evaluate_direction(x, y, np.array([-1., -.5]), mapping)
    assert not report['checks']['useful_step']
    assert not report['checks']['l2_halved']


def test_nonlinear_map_prediction_error_is_not_hidden():
    mapping = lambda x: x*x+.1
    x = np.array([.3, .6]); y = mapping(x)
    _, _, report = evaluate_direction(x, y, np.array([1., 1.]), mapping)
    # 此例可能选择零步；另用有限内部极小值的非线性映射，必须显式校验。
    mapping = lambda x: np.array([.2+x[0]**2, .5*x[1]+.2])
    x = np.array([.5, .1]); y = mapping(x)
    _, _, report = evaluate_direction(x, y, np.array([-.2, .6]), mapping)
    assert report['prediction_error_over_raw_l2'] > 1e-6
    assert not report['checks']['affine_prediction']


def test_replay_checks_defect_scale_not_only_bright_field():
    x = np.array([1.e8, 1.e8]); archived = x+1.e-4
    with pytest.raises(ArithmeticError): verify_map_replay(x, archived+1.e-6, archived)


def test_exact_replay_including_zero_defect():
    x = np.ones(2)
    assert verify_map_replay(x, x, x)['array_equal']


@pytest.mark.parametrize('bad', [np.array([-1., 1.]), np.array([np.nan, 1.]), np.ones(3)])
def test_bad_native_output_rejected(bad):
    with pytest.raises(ValueError): verify_map_replay(np.ones(2), bad, np.ones(2))


def test_negative_fresh_field_is_never_clipped():
    with pytest.raises(ValueError):
        evaluate_direction(np.ones(2), np.full(2, 2.), np.ones(2), lambda x: -x)
