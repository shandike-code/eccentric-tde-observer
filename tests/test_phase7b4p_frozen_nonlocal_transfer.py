from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase7b4p_frozen_nonlocal_transfer import (
    _local_closure_row,
    _mass_reduce_fields,
    _nearest_phase_index,
    periodic_interpolate,
    scale_normalized_maximum_error,
)


def test_periodic_interpolate_preserves_grid_values_and_wraps_orbit() -> None:
    source_phase = np.array([0.0, 0.25, 0.5, 0.75])
    values = np.column_stack((source_phase, 2.0 * source_phase))
    target_phase = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    result = periodic_interpolate(source_phase, values, target_phase)
    assert np.array_equal(result[:-1], values)
    assert np.array_equal(result[-1], values[0])


def test_scale_normalized_maximum_error_uses_reference_scale() -> None:
    candidate = np.array([-2.0, 5.0])
    reference = np.array([-4.0, 4.0])
    assert np.isclose(
        scale_normalized_maximum_error(candidate, reference),
        0.5,
    )


def test_mass_reduction_keeps_flux_and_integrates_specific_heating() -> None:
    mass = np.array([1.0, 3.0])
    fields = {
        "bolometric_flux": np.array([7.0]),
        "radiation_energy_density": np.array([2.0, 6.0]),
        "radiative_heating": np.array([-1.0, 2.0]),
        "photoionization": np.array([[1.0, 2.0, 3.0], [5.0, 6.0, 7.0]]),
        "recombination": np.array([[2.0, 3.0, 4.0], [6.0, 7.0, 8.0]]),
    }
    reduced = _mass_reduce_fields(fields, mass)
    assert np.array_equal(reduced["bolometric_flux"], np.array([7.0]))
    assert np.array_equal(reduced["radiation_energy_density"], np.array([5.0]))
    assert np.array_equal(reduced["radiative_heating"], np.array([5.0]))
    assert np.array_equal(reduced["photoionization"], np.array([4.0, 5.0, 6.0]))


def test_local_closure_row_reports_pointwise_and_mass_weighted_ratios() -> None:
    local = np.array([[2.0, 4.0], [1.0, 3.0]])
    nonlocal_values = np.array([[1.0, 8.0], [1.0, 6.0]])
    row = _local_closure_row(
        "fixture", nonlocal_values, local, np.array([1.0, 3.0])
    )
    assert row["minimum_pointwise_nonlocal_over_local"] == 0.5
    assert row["maximum_pointwise_nonlocal_over_local"] == 2.0
    assert np.isclose(row["minimum_mass_weighted_nonlocal_over_local"], 25.0 / 14.0)


def test_nearest_phase_index_uses_periodic_distance() -> None:
    phase = np.array([0.01, 0.25, 0.5, 0.75])
    assert _nearest_phase_index(phase, 0.99) == 0


def test_phase7b4p_script_calls_no_forbidden_numerical_repairs() -> None:
    path = Path("scripts/phase7b4p_frozen_nonlocal_transfer.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
