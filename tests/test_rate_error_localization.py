from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.radiation import PLANCK_ERG_S
from eccentric_tde_observer.rate_error_localization import (
    localize_hydrogen_photoionization_rate_error,
    project_piecewise_constant_intensity,
    project_piecewise_constant_intensity_to_log_p1,
)


def _hz(energy_ev):
    return np.asarray(energy_ev, dtype=np.float64) * EV_ERG / PLANCK_ERG_S


def test_piecewise_constant_projection_preserves_physical_energy_integral():
    source_edge = _hz([0.1, 13.6, 24.59, 54.42, 5000.0])
    source = np.array([2.0, 5.0, 3.0, 0.5])
    target_edge = _hz([0.1, 1.0, 13.6, 18.0, 24.59, 54.42, 5000.0])
    audit = project_piecewise_constant_intensity_to_log_p1(
        source_edge, source, target_edge
    )
    expected = np.sum(source * np.diff(source_edge))
    recovered = np.sum(
        audit.mean_energy_density * np.diff(np.log(target_edge))
    )
    assert audit.reference_energy_integral == expected
    assert recovered == audit.projected_energy_integral
    assert abs(recovered - expected) / expected < 3.0e-15
    assert audit.relative_energy_integral_error < 3.0e-15


def test_piecewise_constant_p0_projection_preserves_energy_and_constant_field():
    source_edge = _hz([0.1, 2.0, 13.6, 18.0, 54.42, 5000.0])
    source = np.full(source_edge.size - 1, 2.75)
    target_edge = _hz([0.1, 13.6, 24.59, 54.42, 5000.0])
    audit = project_piecewise_constant_intensity(
        source_edge, source, target_edge
    )
    assert np.array_equal(
        audit.mean_intensity_density,
        np.full(target_edge.size - 1, 2.75),
    )
    assert audit.relative_energy_integral_error < 3.0e-15


def test_piecewise_constant_p0_projection_matches_direct_overlap_integrals():
    source_edge = _hz([0.1, 1.0, 13.6, 24.59, 5000.0])
    source = np.array([2.0, 4.0, 3.0, 0.5])
    target_edge = _hz([0.1, 13.6, 54.42, 5000.0])
    audit = project_piecewise_constant_intensity(
        source_edge, source, target_edge
    )
    expected_first = (
        source[0] * (source_edge[1] - source_edge[0])
        + source[1] * (source_edge[2] - source_edge[1])
    ) / (target_edge[1] - target_edge[0])
    assert audit.mean_intensity_density[0] == expected_first
    assert audit.relative_energy_integral_error < 3.0e-15


def test_rate_localization_bins_close_the_signed_and_absolute_ledgers():
    edge_ev = np.array([0.1, 13.6, 20.0, 24.59, 54.42, 5000.0])
    edge_hz = _hz(edge_ev)
    reference = np.array([1.0, 2.0, 1.5, 0.8, 0.2])
    projection = project_piecewise_constant_intensity_to_log_p1(
        edge_hz, reference, edge_hz
    )
    result = localize_hydrogen_photoionization_rate_error(
        edge_hz,
        projection.mean_energy_density,
        projection.realizable_first_moment_energy_density,
        edge_hz,
        reference,
        edge_ev,
        quadrature_order_per_native_overlap=16,
    )
    assert np.sum(result.candidate_rate_bin_s1) == result.candidate_total_rate_s1
    assert np.sum(result.reference_rate_bin_s1) == result.reference_total_rate_s1
    assert np.all(
        result.signed_error_bin_s1
        == result.candidate_rate_bin_s1 - result.reference_rate_bin_s1
    )
    assert np.all(result.absolute_integrand_difference_bin_s1 >= 0.0)
    assert abs(
        np.sum(result.signed_error_bin_s1)
        - (result.candidate_total_rate_s1 - result.reference_total_rate_s1)
    ) < 1.0e-12 * result.reference_total_rate_s1


def test_rate_localization_native_overlap_quadrature_converges():
    reference_edge = _hz(np.geomspace(0.1, 5000.0, 401))
    reference_centre = np.sqrt(reference_edge[:-1] * reference_edge[1:])
    reference = 1.0 / (1.0 + (reference_centre / _hz(30.0)) ** 2)
    candidate_edge = _hz(
        np.unique(
            np.concatenate(
                (
                    np.geomspace(0.1, 5000.0, 81),
                    [13.6, 24.59, 54.42],
                )
            )
        )
    )
    projection = project_piecewise_constant_intensity_to_log_p1(
        reference_edge, reference, candidate_edge
    )
    analysis_edge = np.unique(
        np.concatenate((np.geomspace(0.1, 5000.0, 65), [13.6, 24.59, 54.42]))
    )
    low = localize_hydrogen_photoionization_rate_error(
        candidate_edge,
        projection.mean_energy_density,
        projection.realizable_first_moment_energy_density,
        reference_edge,
        reference,
        analysis_edge,
        quadrature_order_per_native_overlap=8,
    )
    high = localize_hydrogen_photoionization_rate_error(
        candidate_edge,
        projection.mean_energy_density,
        projection.realizable_first_moment_energy_density,
        reference_edge,
        reference,
        analysis_edge,
        quadrature_order_per_native_overlap=16,
    )
    assert abs(low.candidate_total_rate_s1 - high.candidate_total_rate_s1) / abs(
        high.candidate_total_rate_s1
    ) < 2.0e-11
    assert abs(low.reference_total_rate_s1 - high.reference_total_rate_s1) / abs(
        high.reference_total_rate_s1
    ) < 2.0e-11


def test_rate_error_localization_uses_no_forbidden_repairs():
    path = Path("src/eccentric_tde_observer/rate_error_localization.py")
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
