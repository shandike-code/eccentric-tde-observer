from copy import deepcopy
import numpy as np
import pytest

from test_encoded_backtrack import example
from operations.prepare_encoded_backtrack import candidate_arrays
from operations.prepare_half_step_after_audit import (
    ALPHA, REQUIRED_GATES, guarded_half_trial, assert_written_trial)


def inputs():
    original, old = example()
    source, _ = candidate_arrays(original, old, original['base_residual'], 2*ALPHA)
    summary = {'gate_checks': {k: True for k in REQUIRED_GATES},
               'decision': {'finite_trial_accepted_as_one_nonlinear_step': False}}
    for k in ('candidate_l2_contraction_pass', 'candidate_mass_weighted_contraction_pass'):
        summary['gate_checks'][k] = False
    return source, old, summary


def test_halving_preserves_frozen_physics_and_changes_the_actual_trial(tmp_path):
    source, old, summary = inputs(); before = deepcopy(source)
    new, checks = guarded_half_trial(source, old, source['base_residual'], summary)
    assert all(checks.values())
    np.testing.assert_array_equal(new['encoded_state'], source['base_encoded_state'] + ALPHA*source['finite_direction'])
    assert float(new['relaxation']) == ALPHA
    assert not np.array_equal(new['temperature_k'], source['temperature_k'])
    for k in ('base_encoded_state', 'finite_direction', 'base_residual', 'density_g_cm3', 'step_duration_s', 'phase_index'):
        np.testing.assert_array_equal(new[k], source[k])
    for k in source: np.testing.assert_array_equal(source[k], before[k])
    np.savez(tmp_path/'trial.npz', **new)
    with np.load(tmp_path/'trial.npz', allow_pickle=False) as data:
        assert_written_trial(dict(data), new)


@pytest.mark.parametrize('fault', ['heating_failed', 'noise_missing', 'accepted', 'contraction_passed', 'extra_gate'])
def test_only_the_declared_complete_rejection_is_eligible(fault):
    source, old, summary = inputs()
    if fault == 'heating_failed': summary['gate_checks']['last_two_atomic_heating_pass'] = False
    if fault == 'noise_missing': del summary['gate_checks']['inner_noise_resolved_pass']
    if fault == 'accepted': summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] = True
    if fault == 'contraction_passed': summary['gate_checks']['candidate_l2_contraction_pass'] = True
    if fault == 'extra_gate': summary['gate_checks']['unknown_gate'] = True
    with pytest.raises(ValueError, match='stable pair'):
        guarded_half_trial(source, old, source['base_residual'], summary)


def test_wrong_source_alpha_is_rejected():
    source, old, summary = inputs(); source['relaxation'] = np.array(.0625)
    with pytest.raises(ValueError, match='source is not'):
        guarded_half_trial(source, old, source['base_residual'], summary)


@pytest.mark.parametrize('fault', ['field_changed', 'field_missing', 'old_trial'])
def test_written_trial_mismatch_cannot_initialize(fault):
    source, old, summary = inputs()
    new, _ = guarded_half_trial(source, old, source['base_residual'], summary)
    written = deepcopy(new)
    if fault == 'field_changed': written['step_duration_s'] += 1
    if fault == 'field_missing': del written['helium_fraction']
    if fault == 'old_trial': written = source
    with pytest.raises(RuntimeError, match='written material'):
        assert_written_trial(written, new)
