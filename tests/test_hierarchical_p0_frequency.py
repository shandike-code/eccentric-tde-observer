from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.multiresolution_frequency import (
    budgeted_hierarchical_p0_grid,
    hierarchical_p0_option_error,
    nested_log_frequency_hierarchy,
)
from eccentric_tde_observer.source import PhysicalDomainError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_hierarchical_p0_constant_spectrum_has_zero_defect() -> None:
    hierarchy = nested_log_frequency_hierarchy(
        np.geomspace(1.0e15, 1.0e18, 5)
    )
    spectra = np.ones((hierarchy.master_edge_hz.size - 1, 3))
    error = hierarchical_p0_option_error(hierarchy, spectra)
    assert np.array_equal(error.option_leaf_counts, np.array([1, 2, 4]))
    assert np.array_equal(error.normalized_score_by_option, np.zeros((4, 3)))
    assert np.array_equal(
        error.energy_defect_fraction_by_option, np.zeros((4, 3))
    )
    assert np.array_equal(
        error.rate_defect_fraction_by_species_and_option,
        np.zeros((3, 4, 3)),
    )


def test_hierarchical_budget_is_exact_and_no_worse_than_uniform_pilot() -> None:
    hierarchy = nested_log_frequency_hierarchy(
        np.geomspace(1.0e15, 1.0e18, 5)
    )
    centre = np.sqrt(
        hierarchy.master_edge_hz[:-1] * hierarchy.master_edge_hz[1:]
    )
    spectra = np.column_stack(
        (
            np.exp(-centre / 2.0e16),
            (centre / 1.0e15) ** -0.7,
            0.4 * np.exp(-centre / 8.0e16) + 0.6,
        )
    )
    error = hierarchical_p0_option_error(hierarchy, spectra)
    grid = budgeted_hierarchical_p0_grid(error, leaf_group_budget=8)
    assert grid.leaf_group_count == 8
    assert int(np.sum(grid.leaf_count_by_parent)) == 8
    assert set(grid.leaf_count_by_parent).issubset({1, 2, 4})
    assert int(np.sum(grid.option_parent_counts)) == 4
    assert np.all(np.isin(grid.group_edge_hz, hierarchy.master_edge_hz))
    uniform_pilot_objective = float(
        np.sum(error.normalized_score_by_option[:, 1])
    )
    assert grid.objective_sum_normalized_local_defect <= uniform_pilot_objective


def test_hierarchical_budget_rejects_unrepresentable_exact_count() -> None:
    hierarchy = nested_log_frequency_hierarchy(np.array([1.0e15, 1.0e17]))
    spectra = np.ones((4, 1))
    error = hierarchical_p0_option_error(hierarchy, spectra)
    with pytest.raises(PhysicalDomainError, match="not representable"):
        budgeted_hierarchical_p0_grid(error, leaf_group_budget=3)


def test_hierarchical_frequency_source_uses_no_forbidden_repairs() -> None:
    source = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "multiresolution_frequency.py"
    ).read_text(encoding="utf-8")
    assert "nan_to_num" not in source
    assert "np.clip" not in source
