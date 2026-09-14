from __future__ import annotations

import numpy as np

from eccentric_tde_observer.adaptive import (
    render_source_surface_quadrature,
    source_surface_blackbody_sed,
)
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.polarization import (
    chandrasekhar_polarization_fraction,
    eddington_limb_darkening_factor,
    surface_stokes_sed,
)
from eccentric_tde_observer.source import PhysicalDomainError
import pytest


def test_eddington_limb_law_preserves_hemispheric_flux() -> None:
    mu = np.linspace(0.0, 1.0, 10001)
    normalized_flux = 2.0 * np.trapezoid(
        eddington_limb_darkening_factor(mu) * mu, mu
    )
    assert np.isclose(normalized_flux, 1.0, rtol=0.0, atol=3.0e-9)


def test_chandrasekhar_fit_has_required_normal_and_limb_limits() -> None:
    assert chandrasekhar_polarization_fraction(1.0) == 0.0
    assert chandrasekhar_polarization_fraction(0.0) == 0.1171
    assert np.all(np.diff(chandrasekhar_polarization_fraction(np.linspace(0.0, 1.0, 101))) < 0.0)


def _flat_case(inclination_deg: float):
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 2.0e4, radial_points=17, anomaly_points=128
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(1.0e26, np.deg2rad(inclination_deg), 0.3)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=128
    )
    return source, mesh, observer, quadrature


def test_disabling_angular_closures_recovers_existing_isotropic_sed() -> None:
    source, mesh, observer, quadrature = _flat_case(60.0)
    frequency = np.geomspace(3.0e14, 3.0e15, 17)
    baseline = source_surface_blackbody_sed(
        source, mesh, observer, quadrature, frequency
    )
    stokes = surface_stokes_sed(
        source,
        mesh,
        observer,
        quadrature,
        frequency,
        apply_limb_darkening=False,
        apply_scattering_polarization=False,
    )
    assert np.array_equal(stokes.flux_i_erg_s_cm2_hz, baseline.flux_density_erg_s_cm2_hz)
    assert np.all(stokes.flux_q_erg_s_cm2_hz == 0.0)
    assert np.all(stokes.flux_u_erg_s_cm2_hz == 0.0)


def test_flat_disc_unresolved_polarization_matches_local_plane_parallel_value() -> None:
    source, mesh, observer, quadrature = _flat_case(60.0)
    stokes = surface_stokes_sed(
        source, mesh, observer, quadrature, np.array([5.0e14, 1.0e15])
    )
    expected = chandrasekhar_polarization_fraction(np.cos(np.deg2rad(60.0)))
    assert np.allclose(stokes.polarization_fraction, expected, rtol=3.0e-14)
    assert np.allclose(stokes.polarization_angle_rad, 0.0, atol=3.0e-15)


def test_face_on_flat_disc_has_zero_polarization_and_finite_stokes() -> None:
    source, mesh, observer, quadrature = _flat_case(0.0)
    stokes = surface_stokes_sed(
        source, mesh, observer, quadrature, np.array([1.0e15])
    )
    assert stokes.polarization_fraction[0] == 0.0
    assert np.all(np.isfinite(stokes.flux_i_erg_s_cm2_hz))


def test_exact_zero_wien_flux_rejects_undefined_polarization() -> None:
    source, mesh, observer, quadrature = _flat_case(60.0)
    with pytest.raises(PhysicalDomainError, match="undefined where total flux is zero"):
        surface_stokes_sed(
            source, mesh, observer, quadrature, np.array([1.0e22])
        )


def test_polarization_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import polarization

    source_text = open(polarization.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
