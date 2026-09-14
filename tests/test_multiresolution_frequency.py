from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.goal_oriented_frequency import (
    hydrogen_photoionization_monitor_group_grid,
)
from eccentric_tde_observer.multiresolution_frequency import (
    budgeted_variable_frequency_grid,
    embedded_p0_frequency_error,
    nested_log_frequency_hierarchy,
    prolong_piecewise_constant_frequency,
    restrict_piecewise_constant_frequency,
)
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.source import PhysicalDomainError


def _small_hierarchy():
    edge_ev = np.array([0.1, 13.6, 24.59, 54.42, 100.0, 5000.0])
    return nested_log_frequency_hierarchy(edge_ev * EV_ERG / PLANCK_ERG_S)


def test_nested_log_hierarchy_preserves_base_and_exact_atomic_thresholds():
    base = hydrogen_photoionization_monitor_group_grid(
        0.1, 5000.0, 2408, 0.25
    ).group_edge_hz
    hierarchy = nested_log_frequency_hierarchy(base)
    assert hierarchy.pilot_edge_hz.size == 4817
    assert hierarchy.master_edge_hz.size == 9633
    assert np.array_equal(hierarchy.pilot_edge_hz[::2], base)
    assert np.array_equal(hierarchy.master_edge_hz[::2], hierarchy.pilot_edge_hz)
    threshold_hz = (
        np.array([13.6, 24.59, 54.42]) * EV_ERG / PLANCK_ERG_S
    )
    for threshold in threshold_hz:
        assert np.count_nonzero(hierarchy.master_edge_hz == threshold) == 1


def test_p0_prolongation_and_restriction_conserve_frequency_integrals():
    hierarchy = _small_hierarchy()
    coarse = np.arange(1.0, 11.0).reshape((5, 2))
    prolongation = prolong_piecewise_constant_frequency(
        hierarchy.base_edge_hz, hierarchy.master_edge_hz, coarse
    )
    restriction = restrict_piecewise_constant_frequency(
        hierarchy.master_edge_hz,
        hierarchy.base_edge_hz,
        prolongation.mean_intensity_density,
    )
    assert prolongation.maximum_relative_integral_residual < 3.0e-16
    assert restriction.maximum_relative_integral_residual < 3.0e-16
    assert np.allclose(
        restriction.mean_intensity_density, coarse, rtol=3.0e-16, atol=0.0
    )


def test_embedded_indicator_ranks_local_child_structure_without_fitted_band():
    hierarchy = _small_hierarchy()
    fine = np.ones(hierarchy.master_edge_hz.size - 1)
    target_parent = 3
    left = 4 * target_parent
    fine[left : left + 4] = np.array([0.4, 1.6, 0.5, 1.5])
    audit8 = embedded_p0_frequency_error(
        hierarchy.base_edge_hz,
        hierarchy.master_edge_hz,
        fine,
        quadrature_order_per_fine_group=8,
    )
    audit16 = embedded_p0_frequency_error(
        hierarchy.base_edge_hz,
        hierarchy.master_edge_hz,
        fine,
        quadrature_order_per_fine_group=16,
    )
    assert audit8.descending_parent_order[0] == target_parent
    assert audit8.normalized_indicator[target_parent] > 0.0
    off_target = np.delete(audit8.normalized_indicator, target_parent)
    assert np.max(off_target) < 3.0e-13
    assert audit8.maximum_restriction_integral_residual < 3.0e-16
    assert np.allclose(
        audit8.rate_defect_fraction_by_species,
        audit16.rate_defect_fraction_by_species,
        rtol=2.0e-12,
        atol=1.0e-16,
    )


def test_budgeted_variable_grid_has_only_one_or_four_children_and_respects_cap():
    hierarchy = _small_hierarchy()
    fine = np.ones(hierarchy.master_edge_hz.size - 1)
    fine[12:16] = np.array([0.4, 1.6, 0.5, 1.5])
    error = embedded_p0_frequency_error(
        hierarchy.base_edge_hz, hierarchy.master_edge_hz, fine
    )
    grid = budgeted_variable_frequency_grid(
        error, hierarchy.master_edge_hz, leaf_group_budget=11
    )
    assert grid.refined_parent_count == 2
    assert grid.leaf_group_count == 11
    assert grid.unused_leaf_budget == 0
    assert set(grid.child_groups_per_base) == {1, 4}
    assert grid.refined_parent_mask[3]
    assert np.array_equal(
        grid.group_edge_hz[np.searchsorted(grid.group_edge_hz, hierarchy.base_edge_hz)],
        hierarchy.base_edge_hz,
    )


def test_zero_reference_atomic_rates_are_excluded_without_a_floor():
    hierarchy = _small_hierarchy()
    fine = np.zeros(hierarchy.master_edge_hz.size - 1)
    fine[:4] = 1.0
    error = embedded_p0_frequency_error(
        hierarchy.base_edge_hz, hierarchy.master_edge_hz, fine
    )
    assert np.array_equal(error.positive_rate_sample_count_by_species, [0, 0, 0])
    assert np.count_nonzero(error.rate_defect_fraction_by_species) == 0


def test_multiresolution_frequency_rejects_invalid_domains_and_budgets():
    hierarchy = _small_hierarchy()
    with pytest.raises(PhysicalDomainError, match="preserve every coarse edge"):
        prolong_piecewise_constant_frequency(
            hierarchy.base_edge_hz,
            hierarchy.master_edge_hz[1:],
            np.ones(5),
        )
    with pytest.raises(PhysicalDomainError, match="non-negative"):
        embedded_p0_frequency_error(
            hierarchy.base_edge_hz,
            hierarchy.master_edge_hz,
            -np.ones(20),
        )
    error = embedded_p0_frequency_error(
        hierarchy.base_edge_hz,
        hierarchy.master_edge_hz,
        np.ones(20),
    )
    with pytest.raises(PhysicalDomainError, match="between base and master"):
        budgeted_variable_frequency_grid(error, hierarchy.master_edge_hz, 4)


def test_multiresolution_frequency_uses_no_forbidden_repairs():
    path = (
        Path("src")
        / "eccentric_tde_observer"
        / "multiresolution_frequency.py"
    )
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
