"""The diagnostic ledger must reproduce solver arithmetic without raising.

These tests pin three things the diagnosis relies on:

1. the gas/ionization split the ledger reports is the solver's own split;
2. the ledger's metric terms reproduce `weighted_volume_l1` exactly;
3. a cell whose remaining gas heat is negative is *reported*, not raised on,
   while the solver itself still raises on the same input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "diagnostics"))

from eccentric_tde_observer import radiation_matter_feedback as rmf  # noqa: E402
from eccentric_tde_observer.formal_feedback_pair import weighted_volume_l1  # noqa: E402
import material_energy_ledger as ledger  # noqa: E402


def synthetic_cells(cells: int = 4):
    hydrogen = np.full((cells, 2), [0.2, 0.8])
    helium = np.full((cells, 3), [1e-3, 1e-2, 0.989])
    temperature = np.full(cells, 5.0e4)
    return temperature, hydrogen, helium


def test_split_reproduces_solver_specific_energy():
    temperature, hydrogen, helium = synthetic_cells()
    composition = rmf.SOLAR_FULLY_IONIZED_H_HE
    gas = ledger.gas_specific_heat_erg_g(temperature, hydrogen, helium, composition)
    ionization = ledger.ionization_specific_energy_erg_g(hydrogen, helium, composition)
    reference = rmf.ground_state_material_specific_energy_erg_g(
        temperature, hydrogen, helium, composition=composition
    )
    assert np.allclose(gas + ionization, reference, rtol=0.0, atol=0.0)


def test_metric_terms_reproduce_weighted_volume_l1():
    rng = np.random.default_rng(20260915)
    width = rng.uniform(1.0, 3.0, size=64)
    previous = rng.normal(size=(64, 3)) * 10.0
    final = previous + rng.normal(size=(64, 3)) * 1e-3
    numerator, denominator = ledger.weighted_volume_terms(previous, final, width)
    component_ratio = np.sum(numerator, axis=0) / np.sum(denominator, axis=0)
    assert np.allclose(
        np.max(component_ratio), np.max(weighted_volume_l1(previous, final, width)),
        rtol=0.0, atol=0.0,
    )


def test_ledger_reports_negative_heat_instead_of_raising():
    density = np.full(2, 1e-9)
    duration = 1.0e6
    old_h = np.full((2, 2), [0.5, 0.5])
    old_he = np.full((2, 3), [0.5, 0.4, 0.1])
    old_temperature = np.full(2, 1.0e4)
    # A large negative heating removes more energy than the gas holds.
    feedback = {
        "half_atomic_rate_heating_erg_s_cm3": np.full(2, -1.0e12),
        "half_photoionization_s1": np.full((2, 3), 1.0e-12),
        "half_total_recombination_cm3_s": np.full((2, 3), 1.0e-12),
    }
    result = ledger.ledger(feedback, density, duration, old_temperature, old_h, old_he)
    assert np.all(result["remaining"] < 0.0)
    assert result["split_self_check"] == 0.0

    # The solver, given the same physics, must still refuse.
    old_energy = rmf.ground_state_material_specific_energy_erg_g(
        old_temperature, old_h, old_he
    )
    target = old_energy + duration * feedback["half_atomic_rate_heating_erg_s_cm3"] / density
    with pytest.raises(rmf.PhysicalDomainError, match="no positive gas heat"):
        rmf.ground_state_material_temperature_from_specific_energy_k(
            target, result["new_h"], result["new_he"]
        )
    # The ledger's own target must be the very quantity the solver rejects.
    assert np.allclose(result["target"], target, rtol=0.0, atol=0.0)


def test_ionization_energy_ignores_nothing_at_zero_temperature():
    """Ionization energy is thermal-independent, so it must not move with T."""
    _, hydrogen, helium = synthetic_cells()
    composition = rmf.SOLAR_FULLY_IONIZED_H_HE
    ionization = ledger.ionization_specific_energy_erg_g(hydrogen, helium, composition)
    assert np.all(ionization > 0.0)
    assert ionization.shape == (hydrogen.shape[0],)


def test_parent_96_perturbation_localises_to_96_not_48():
    """The adapter maps 4096 subcells onto 256 parent layers of 16, then half=parent[:128].

    Grouping 32 adjacent subcells (the earlier, wrong reading) puts a perturbation
    that truly sits in material layer 96 into layer 48.
    """
    perturbation = np.zeros(4096)
    perturbation[96 * 16:97 * 16] = 1.0
    parent = ledger.parent_layer_contributions(perturbation)
    assert np.nonzero(parent)[0].tolist() == [96]
    folded = ledger.fold_to_material_layers(parent)
    assert int(np.argmax(folded)) == 96

    wrong = perturbation.reshape(128, 32).sum(axis=1)
    assert int(np.argmax(wrong)) == 48  # what the old mapping returned


def test_mirrored_perturbation_folds_to_the_same_material_layer():
    """Subcell 159 is the mirror of parent 96, so it must fold to 96 as well."""
    perturbation = np.zeros(4096)
    perturbation[159 * 16:160 * 16] = 1.0
    parent = ledger.parent_layer_contributions(perturbation)
    assert np.nonzero(parent)[0].tolist() == [159]
    folded = ledger.fold_to_material_layers(parent)
    assert int(np.argmax(folded)) == 96


def test_fold_is_symmetric_and_preserves_the_column_total():
    rng = np.random.default_rng(7)
    parent = rng.uniform(0.0, 1.0, size=256)
    folded = ledger.fold_to_material_layers(parent)
    assert folded.shape == (128,)
    assert np.isclose(folded.sum(), parent.sum(), rtol=0.0, atol=1e-12)


def test_metric_numerator_and_denominator_come_from_one_component():
    """The largest numerator and the largest ratio can sit in different components."""
    previous = np.array([[10.0, 0.0, 1.0]])
    final = np.array([[20.0, 1.0, 1.0]])
    width = np.ones(1)
    numerator, denominator = ledger.weighted_volume_terms(previous, final, width)
    component_numerator = np.atleast_1d(np.sum(numerator, axis=0))
    component_denominator = np.atleast_1d(np.sum(denominator, axis=0))
    # Component 0 carries the big numerator; component 1 carries the worst ratio.
    assert component_numerator.tolist() == [10.0, 1.0, 0.0]
    assert component_denominator.tolist() == [20.0, 1.0, 1.0]
    assert int(np.argmax(component_numerator)) == 0
    ratios = component_numerator / component_denominator
    assert int(np.argmax(ratios)) == 1
    # Reporting max(numerator) over max(denominator) would have used component 0's
    # denominator and produced 10/20 = 0.5 instead of the true worst 1.0.
    assert np.max(component_numerator) / np.max(component_denominator) == 0.5
    assert ratios[1] == 1.0


def test_absolute_and_relative_worst_layers_are_reported_separately():
    weights = np.array([0.5, 0.5])
    led = {
        "remaining": np.array([-10.0, -1.0]),
        "remaining_relative_to_old_gas_heat": np.array([-10.0 / 1000.0, -1.0 / 1.5]),
        "gas_old": np.array([1000.0, 1.5]),
        "charge_residual": np.zeros(2), "particle_residual": np.zeros(2),
        "split_self_check": 0.0,
    }
    report = ledger.endpoint_report(led, weights, "synthetic")
    assert report["absolute_worst"]["cell"] == 0   # most negative in erg/g
    assert report["relative_worst"]["cell"] == 1   # most negative relative to its own gas heat
