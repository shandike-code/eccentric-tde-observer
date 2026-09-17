import numpy as np
import pytest
from operations.replay_equation_baseline import pair_comparison, check_physical_identity


def test_ratios_retain_all_three_norms_and_weighted_disagreement():
    base = np.array([[10.,0,0,0], [1.,0,0,0]])
    trial = np.array([[5.,0,0,0], [2.,0,0,0]])
    result = pair_comparison((base,base), (trial,trial), [1.,100.])
    assert result['ratios']['l2']['candidate_over_baseline'] < 1
    assert result['ratios']['mass_weighted_l2']['candidate_over_baseline'] > 1
    assert result['ratios']['maximum_cell']['candidate_over_baseline'] == .5
    assert not result['true_inner_error_bound_available']
    assert not result['formal_acceptance_evaluated']


def test_zero_signal_is_undefined_not_floor_or_zero():
    a = np.ones((2,4))
    result = pair_comparison((a,a), (a,a), [1.,1.])
    for row in result['ratios'].values():
        assert row['candidate_drift_over_difference'] is None
        assert row['sum_observed_drifts_over_difference'] is None


def test_drift_sum_uses_both_baseline_and_candidate():
    b = np.zeros((1,4)); b[0,0] = 1
    result = pair_comparison((b,2*b), (4*b,7*b), [1.])
    row = result['ratios']['l2']
    assert row['baseline_drift_over_difference'] == pytest.approx(1/5)
    assert row['candidate_drift_over_difference'] == pytest.approx(3/5)
    assert row['sum_observed_drifts_over_difference'] == pytest.approx(4/5)


@pytest.mark.parametrize('masses', [[1.,0.], [1.,-1.], [1.,np.nan], [1.]])
def test_invalid_mass_measure_rejected(masses):
    a = np.ones((2,4))
    with pytest.raises(ValueError):pair_comparison((a,a),(a,a),masses)


def test_changed_physical_timestep_rejected():
    old = {'step_duration_s':np.array([9.]), 'density_g_cm3':np.array([[1.,2.]])}
    trial = {'phase_index':0, 'step_duration_s':8., 'density_g_cm3':np.array([1.,2.])}
    with pytest.raises(RuntimeError):check_physical_identity(trial,old,0,9.,np.array([1.,2.]))
