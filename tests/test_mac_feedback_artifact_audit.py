"""Controls for the mapping/component errors exposed by the real artifact audit."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "diagnostics"))
from mac_feedback_artifact_audit import component_metric, depth_contributions, material_replay


def test_parent_and_mirror_are_folded_to_same_physical_cell():
    previous, final = np.zeros(4096), np.zeros(4096)
    final[96 * 16:97 * 16] = 2
    mirror = 255 - 96
    final[mirror * 16:(mirror + 1) * 16] = 3
    width = np.full(4096, 4.)
    terms, parent, folded = depth_contributions(previous, final, width)
    assert parent[96] == 128
    assert parent[mirror] == 192
    assert folded[96] == 320
    assert np.count_nonzero(folded) == 1
    assert terms.sum() == parent.sum() == folded.sum()


def test_component_numerators_keep_their_own_denominators():
    previous = np.tile([100., 1., 1.], (4096, 1))
    final = np.tile([100., 2., 1.], (4096, 1))
    result = component_metric(previous, final, np.ones(4096))
    np.testing.assert_array_equal(result["ratio"], [0., .5, 0.])
    np.testing.assert_array_equal(np.asarray(result["numerator"]) / result["denominator"], result["ratio"])
    assert result["maximum_ratio"] == .5


def test_zero_signal_preserves_zero_without_a_floor():
    zero = np.zeros(4096)
    terms, parent, folded = depth_contributions(zero, zero, np.ones(4096))
    assert terms.sum() == parent.sum() == folded.sum() == 0
    assert component_metric(zero, zero, np.ones(4096))["maximum_ratio"] == 0


def test_replay_observes_original_response_in_positive_and_negative_domains():
    density = np.full(4, 1e-9)
    old = {"step_duration_s": np.array([1.]), "density_g_cm3": density[None],
           "temperature_k": np.full((1, 4), 5e4),
           "hydrogen_fraction": np.tile([.2, .8], (1, 4, 1)),
           "helium_fraction": np.tile([.001, .01, .989], (1, 4, 1)),
           "cell_mass_g_cm2": np.ones(4)}
    feedback = {"half_photoionization_s1": np.full((4, 3), 1e-12),
                "half_total_recombination_cm3_s": np.full((4, 3), 1e-12),
                "half_atomic_rate_heating_erg_s_cm3": np.zeros(4)}
    positive = material_replay(feedback, old, 0, 1., density)
    assert positive["solver_error"] is None
    assert positive["failing_count"] == 0
    np.testing.assert_array_equal(positive["per_cell"]["hydrogen_old"], old["hydrogen_fraction"][0])
    feedback["half_atomic_rate_heating_erg_s_cm3"][:] = -1e12
    negative = material_replay(feedback, old, 0, 1., density)
    assert negative["solver_error"] == "specific material energy leaves no positive gas heat"
    assert negative["failing_count"] == 4
    assert negative["failing_mass_fraction"] == 1
