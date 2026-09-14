from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.fixtures import (
    constant_temperature_circular_annulus,
)
from eccentric_tde_observer.photosphere import solve_gray_photosphere
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.validity import (
    audit_local_vertical_domain,
    local_orbital_radius_cm,
)
from eccentric_tde_observer.vertical import (
    RADIATION_PRESSURE_POLYTROPE_PROFILE,
)


def test_local_radius_recovers_circular_semimajor_axis() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=9, anomaly_points=64
    )
    radius = local_orbital_radius_cm(source)
    assert np.array_equal(
        radius,
        np.broadcast_to(source.semimajor_axis_cm[:, None], source.shape),
    )


def test_constant_aspect_annulus_audit_recovers_uniform_node_ratios() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=33, anomaly_points=256
    )
    photosphere = solve_gray_photosphere(source, 0.34)
    audit = audit_local_vertical_domain(
        source, photosphere, ratio_thresholds=(0.01, 0.1, 1.0)
    )
    expected_h_over_radius = 0.01
    expected_photosphere_over_radius = (
        0.01 * photosphere.scaled_height[0, 0]
    )
    assert audit.h_over_radius_min_max == (
        expected_h_over_radius,
        expected_h_over_radius,
    )
    assert np.allclose(
        audit.photosphere_over_radius_min_max,
        (expected_photosphere_over_radius, expected_photosphere_over_radius),
        rtol=2.0e-15,
    )
    assert np.array_equal(
        audit.corrected_h_over_radius_fraction_above,
        np.array([1.0, 0.0, 0.0]),
    )
    assert np.array_equal(
        audit.corrected_photosphere_over_radius_fraction_above,
        np.array([1.0, 0.0, 0.0]),
    )
    assert audit.oriented_single_valued_surface_graph
    assert np.isclose(
        audit.surface_area_to_projected_mesh_area,
        np.sqrt(1.0 + expected_photosphere_over_radius**2),
        rtol=4.0e-5,
    )
    assert audit.projected_area_fraction_with_surface_slope_ge_1 == 0.0


def test_finite_polytrope_gives_lower_photosphere_ratio_than_gaussian() -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=17, anomaly_points=128
    )
    gaussian = audit_local_vertical_domain(
        source, solve_gray_photosphere(source, 0.34)
    )
    polytrope = audit_local_vertical_domain(
        source,
        solve_gray_photosphere(
            source, 0.34, profile=RADIATION_PRESSURE_POLYTROPE_PROFILE
        ),
    )
    assert (
        polytrope.corrected_mean_photosphere_over_radius
        < gaussian.corrected_mean_photosphere_over_radius
    )


@pytest.mark.parametrize(
    "thresholds",
    [(), (0.3, 0.1), (0.1, 0.1), (0.0, 0.1), (0.1, np.nan)],
)
def test_invalid_validity_thresholds_are_rejected(
    thresholds: tuple[float, ...],
) -> None:
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 5.0e4, radial_points=5, anomaly_points=32
    )
    photosphere = solve_gray_photosphere(source, 0.34)
    with pytest.raises(PhysicalDomainError, match="ratio_thresholds"):
        audit_local_vertical_domain(source, photosphere, thresholds)
