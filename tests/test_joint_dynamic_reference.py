from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.joint_dynamic_reference import (
    compare_nested_depth_resolution,
    compare_periodic_time_resolution,
    dynamic_reference_fields,
    joint_dynamic_error_meets_target,
    resample_periodic_dynamic_fields,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _fields(phase: np.ndarray, edges: np.ndarray):
    centre = 0.5 * (edges[:-1] + edges[1:])
    modulation = 1.0 + 0.04 * np.sin(2.0 * np.pi * phase)
    temperature = modulation[:, None] * (2.0e4 + 3.0e4 * centre[None, :])
    opacity = (1.0 / modulation[:, None]) * (
        0.2 + 0.1 * centre[None, :]
    )
    h_ii = 0.7 + 0.1 * centre[None, :] + 0.0 * phase[:, None]
    he_iii = 0.9 - 0.8 * centre[None, :] + 0.0 * phase[:, None]
    return dynamic_reference_fields(
        phase,
        edges,
        np.diff(edges) * 12.0,
        temperature,
        opacity,
        h_ii,
        he_iii,
        3.0e14 * modulation,
    )


def test_periodic_time_comparison_recovers_its_linear_resampling_control() -> None:
    coarse = _fields(np.arange(8) / 8.0, np.linspace(0.0, 1.0, 5))
    reference = resample_periodic_dynamic_fields(
        coarse, np.arange(16) / 16.0
    )
    error = compare_periodic_time_resolution(coarse, reference)
    assert error.surface_flux_relative_error == 0.0
    assert error.maximum_pointwise_temperature_or_opacity_relative_error == 0.0
    assert error.maximum_pointwise_population_absolute_error == 0.0
    assert error.front_status_mismatch_phase_count == 0
    assert joint_dynamic_error_meets_target(error, 1.0e-12)


def test_nested_depth_comparison_recovers_linear_mass_profiles() -> None:
    phase = np.arange(8) / 8.0
    candidate = _fields(phase, np.array([0.0, 0.5, 1.0]))
    reference = _fields(phase, np.linspace(0.0, 1.0, 5))
    error = compare_nested_depth_resolution(candidate, reference)
    assert error.surface_flux_relative_error == 0.0
    assert error.maximum_pointwise_temperature_or_opacity_relative_error < 4.0e-16
    assert error.maximum_pointwise_population_absolute_error < 3.0e-16
    assert error.maximum_column_mean_temperature_or_opacity_relative_error < 3.0e-16
    assert error.maximum_column_mean_population_absolute_error < 3.0e-16
    assert error.maximum_he_iii_half_front_mass_fraction_error < 3.0e-16
    assert joint_dynamic_error_meets_target(error, 1.0e-12)


def test_joint_gate_reports_a_declared_population_failure() -> None:
    reference = _fields(np.arange(8) / 8.0, np.linspace(0.0, 1.0, 5))
    candidate = dynamic_reference_fields(
        reference.orbital_phase,
        reference.mass_fraction_edges,
        reference.cell_mass_g_cm2,
        reference.temperature_k,
        reference.rosseland_opacity_cm2_g,
        reference.hydrogen_ionized_fraction,
        reference.helium_doubly_ionized_fraction + 2.0e-3,
        reference.surface_flux_erg_s_cm2,
    )
    error = compare_periodic_time_resolution(candidate, reference)
    assert np.isclose(error.maximum_pointwise_population_absolute_error, 2.0e-3)
    assert not joint_dynamic_error_meets_target(error, 1.0e-3)


def test_joint_comparisons_reject_incompatible_grids() -> None:
    phase = np.arange(8) / 8.0
    coarse = _fields(phase, np.array([0.0, 0.4, 1.0]))
    reference = _fields(phase, np.linspace(0.0, 1.0, 5))
    with pytest.raises(PhysicalDomainError, match="identical depth edges"):
        compare_periodic_time_resolution(coarse, reference)
    with pytest.raises(PhysicalDomainError, match="strict subset"):
        compare_nested_depth_resolution(coarse, reference)


def test_joint_dynamic_module_uses_no_forbidden_numerical_repairs() -> None:
    source = Path(
        "src/eccentric_tde_observer/joint_dynamic_reference.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("nan_to_num", "np.clip", "numpy.clip"):
        assert forbidden not in source
