from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.adaptive import render_source_surface_quadrature
from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.geometry import build_orbital_surface_mesh
from eccentric_tde_observer.gr_transfer import (
    beloborodov_schwarzschild_direct_image_transfer,
    gr_direct_image_sed,
)
from eccentric_tde_observer.observer import Observer
from eccentric_tde_observer.polarization import surface_stokes_sed
from eccentric_tde_observer.source import PhysicalDomainError


def _case(inclination_deg: float = 60.0):
    source = constant_temperature_circular_annulus(
        1.0e14, 2.0e14, 2.0e4, radial_points=17, anomaly_points=128
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(1.0e26, np.deg2rad(inclination_deg), 0.4)
    return source, mesh, observer


def test_zero_compactness_limit_recovers_flat_projection_and_direction() -> None:
    source, mesh, observer = _case()
    transfer = beloborodov_schwarzschild_direct_image_transfer(
        source, mesh, observer, 1.0e-12
    )
    projected_area = np.pi * ((2.0e14) ** 2 - (1.0e14) ** 2) * np.cos(np.deg2rad(60.0))
    # 128 点多边形圆周误差约为 (Delta E)^2/6。
    assert np.isclose(transfer.direct_image_area_cm2, projected_area, rtol=4.2e-4)
    direction_error = np.linalg.norm(
        transfer.photon_direction_at_emitter - observer.direction_from_source,
        axis=-1,
    )
    assert np.max(direction_error) < 3.0e-14
    # 残余量由同一极小质量下仍非零的 Kepler 速度主导。
    assert np.max(np.abs(transfer.frequency_shift_factor - 1.0)) < 5.0e-11


def test_zero_compactness_spectrum_recovers_straight_image_with_same_limb_law() -> None:
    source, mesh, observer = _case(45.0)
    quadrature = render_source_surface_quadrature(
        mesh, observer, subdivision_level=0, bins_long_axis=128
    )
    straight = surface_stokes_sed(
        source,
        mesh,
        observer,
        quadrature,
        np.geomspace(3.0e14, 3.0e15, 21),
        apply_scattering_polarization=False,
    )
    transfer = beloborodov_schwarzschild_direct_image_transfer(
        source, mesh, observer, 1.0e-12
    )
    curved = gr_direct_image_sed(
        source, mesh, observer, transfer, straight.frequency_hz
    )
    assert np.allclose(
        curved.flux_density_erg_s_cm2_hz,
        straight.flux_i_erg_s_cm2_hz,
        rtol=3.0e-12,
    )


def test_physical_weak_field_map_is_finite_and_lensed_area_is_positive() -> None:
    source, mesh, observer = _case(75.0)
    transfer = beloborodov_schwarzschild_direct_image_transfer(
        source, mesh, observer, 1.0e6
    )
    assert transfer.direct_image_area_cm2 > 0.0
    assert np.all(transfer.frequency_shift_factor > 0.0)
    assert np.max(transfer.compactness_2gm_rc2) < 0.01


def test_horizon_state_is_rejected_instead_of_repaired() -> None:
    source = constant_temperature_circular_annulus(
        1.0e10, 2.0e10, 2.0e4, radial_points=5, anomaly_points=32
    )
    mesh = build_orbital_surface_mesh(source)
    observer = Observer(1.0e26, 0.4, 0.2)
    with pytest.raises(PhysicalDomainError, match="horizon"):
        beloborodov_schwarzschild_direct_image_transfer(
            source, mesh, observer, 1.0e6
        )


def test_gr_transfer_source_does_not_use_forbidden_masking_helpers() -> None:
    from eccentric_tde_observer import gr_transfer

    source_text = open(gr_transfer.__file__, encoding="utf-8").read()
    assert "nan_to_num" not in source_text
    assert "np.clip" not in source_text
