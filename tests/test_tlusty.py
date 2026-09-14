from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.radiation import STEFAN_BOLTZMANN_ERG_S_CM2_K4
from eccentric_tde_observer.source import PhysicalDomainError
from eccentric_tde_observer.tlusty import (
    TlustyAnnulusInput,
    TlustyNumericalControls,
    parse_final_relative_change,
    parse_disk_scale_heights,
    parse_direct_annulus_input,
    parse_unit13,
    render_h_he_annulus_input,
)


def test_render_disk_annulus_uses_direct_teff_q_m0_and_lte_switch():
    lte = render_h_he_annulus_input(TlustyAnnulusInput(1.2e4, 3.4e-13, 500.0))
    nlte = render_h_he_annulus_input(
        TlustyAnnulusInput(1.2e4, 3.4e-13, 500.0, lte=False, grey_start=False)
    )
    assert lte.startswith(" 0.0 1.200000000000e+04 3.400000000000e-13 5.000000000000e+02")
    assert " T  T" in lte
    assert " F  F" in nlte
    assert "  100" in lte
    assert "  100" in nlte
    assert "./data/he2.dat" in nlte


def test_bound_bound_lines_are_an_explicit_opt_in():
    continuum = render_h_he_annulus_input(
        TlustyAnnulusInput(1.2e4, 3.4e-13, 500.0, lte=False)
    )
    with_lines = render_h_he_annulus_input(
        TlustyAnnulusInput(
            1.2e4,
            3.4e-13,
            500.0,
            lte=False,
            include_bound_bound_lines=True,
        )
    )
    assert "' H 1' './data/h1.dat'" in continuum
    assert "    100      0    ' H 1'" in continuum
    assert "      0      0    ' H 1'" in with_lines


def test_numerical_controls_are_explicit_and_bounded():
    controls = TlustyNumericalControls(
        maximum_iterations=100,
        radiative_equilibrium_division_tau=0.05,
        general_change_limit=1.25,
        surface_column_mass_g_cm2=1.0e-7,
        hydrostatic_surface_boundary_mode=0,
    )
    assert controls.render() == (
        "NITER=100\nCHMAX=0.001\nTAUDIV=0.05\nDPSILG=1.25\nDM1=1e-07\nIBCHE=0\n"
    )


def test_parse_unit13_converts_hnu_to_surface_flux(tmp_path: Path):
    path = tmp_path / "fort.13"
    path.write_text(" 2.0D+00 2.0D+00 5.0D-01\n 1.0D+00 1.0D+00 5.0D-01\n")
    spectrum = parse_unit13(path, 100.0)
    assert np.array_equal(spectrum.frequency_hz, [1.0, 2.0])
    assert np.allclose(spectrum.surface_flux_fnu_cgs, 4.0 * np.pi * np.array([1.0, 2.0]))
    target = STEFAN_BOLTZMANN_ERG_S_CM2_K4 * 100.0**4
    assert spectrum.target_surface_flux_cgs == target


def test_parse_final_relative_change_uses_last_iteration(tmp_path: Path):
    path = tmp_path / "fort.9"
    path.write_text(
        " RELATIVE CHANGES OF VECTOR PSI\n"
        " 1 2 1D-1 2D-1 3D-1 4D-1 -5D-1 3 4\n"
        " 2 2 1D-4 2D-4 3D-4 4D-4 -7D-4 3 4\n"
        " 2 1 1D-4 2D-4 3D-4 4D-4 6D-4 3 4\n"
    )
    assert parse_final_relative_change(path) == (2, 7.0e-4)


def test_parse_disk_scale_heights_checks_reported_ratio(tmp_path: Path):
    path = tmp_path / "annulus.6"
    path.write_text(
        " GAS PRESSURE SCALE HEIGHT  =  2.000D+10\n"
        " RAD.PRESSURE SCALE HEIGHT  =  5.000D+10\n"
        " RATIO                      =  2.500D+00\n"
    )
    result = parse_disk_scale_heights(path)
    assert result.gas_pressure_scale_height_cm == 2.0e10
    assert result.radiation_pressure_scale_height_cm == 5.0e10
    assert result.radiation_to_gas_ratio == 2.5


def test_parse_direct_annulus_input_requires_xmstar_zero(tmp_path: Path):
    path = tmp_path / "annulus.5"
    path.write_text("0.0 1.2D+04 3.4D-13 5.0D+02 ! direct inputs\n")
    result = parse_direct_annulus_input(path)
    assert result.effective_temperature_k == 1.2e4
    assert result.gravity_coefficient_s2 == 3.4e-13
    assert result.midplane_column_mass_g_cm2 == 5.0e2

    path.write_text("0.8 1.2D+04 3.4D-13 5.0D+02\n")
    with pytest.raises(PhysicalDomainError, match="XMSTAR"):
        parse_direct_annulus_input(path)
