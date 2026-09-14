"""ZO Eq. (38) 非线性射击求解器测试。"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer import (
    ZOHamiltonianSplineTable,
    solve_zo_nonlinear_apsidal_mode,
    solve_zo_nonlinear_apsidal_mode_bvp,
    zo_free_boundary_nonlinearity,
)
from eccentric_tde_observer.source import PhysicalDomainError


ROOT = Path(__file__).resolve().parents[1]


def _linearized_three_dimensional_table() -> ZOHamiltonianSplineTable:
    eccentricity = np.linspace(0.0, 0.002, 33)
    nonlinearity = np.linspace(-0.004, 0.001, 65)
    values = np.empty((eccentricity.size, nonlinearity.size))
    for e_index, e_value in enumerate(eccentricity):
        for q_index, q_value in enumerate(nonlinearity):
            f_value = (e_value + q_value) / (1.0 + e_value * q_value)
            values[e_index, q_index] = (
                3.5 - e_value**2 + 0.25 * e_value * f_value + 0.3125 * f_value**2
            )
    return ZOHamiltonianSplineTable(eccentricity, nonlinearity, values)


def test_free_boundary_and_small_amplitude_mode_recover_linear_limit() -> None:
    table = _linearized_three_dimensional_table()
    inner_eccentricity = 1.0e-4
    q_boundary = zo_free_boundary_nonlinearity(table, inner_eccentricity)
    expected_f = -0.4 * inner_eccentricity
    expected_q = (expected_f - inner_eccentricity) / (
        1.0 - inner_eccentricity * expected_f
    )
    assert q_boundary == pytest.approx(expected_q, rel=2.0e-7)

    mode = solve_zo_nonlinear_apsidal_mode(
        table,
        inner_eccentricity=inner_eccentricity,
        outer_to_inner_semimajor_axis=1.3,
        delta_gr=0.0305649613,
        frequency_bracket=(1.6, 2.0),
        radial_points=256,
    )
    assert mode.dimensionless_frequency == pytest.approx(1.8088649, rel=4.0e-6)
    assert mode.eccentricity[-1] / inner_eccentricity == pytest.approx(
        0.6872294, rel=5.0e-6
    )
    assert abs(mode.inner_boundary_residual) < 2.0e-12
    assert abs(mode.outer_boundary_residual) < 2.0e-11
    assert mode.radial_node_count == 0


def test_mode_solver_rejects_unbracketed_frequency() -> None:
    with pytest.raises(PhysicalDomainError, match="does not contain"):
        solve_zo_nonlinear_apsidal_mode(
            _linearized_three_dimensional_table(),
            inner_eccentricity=1.0e-4,
            outer_to_inner_semimajor_axis=1.3,
            delta_gr=0.0305649613,
            frequency_bracket=(2.2, 2.5),
            radial_points=64,
        )


def test_collocation_bvp_independently_recovers_linear_limit() -> None:
    mode = solve_zo_nonlinear_apsidal_mode_bvp(
        _linearized_three_dimensional_table(),
        inner_eccentricity=1.0e-4,
        outer_to_inner_semimajor_axis=1.3,
        delta_gr=0.0305649613,
        frequency_guess=1.8,
        radial_points=96,
        relative_tolerance=2.0e-7,
    )
    assert mode.dimensionless_frequency == pytest.approx(1.8088649, rel=5.0e-6)
    assert mode.eccentricity[-1] / 1.0e-4 == pytest.approx(0.6872294, rel=6.0e-6)
    assert abs(mode.inner_boundary_residual) < 2.0e-11
    assert abs(mode.outer_boundary_residual) < 2.0e-11


def test_nonlinear_mode_source_contains_no_numerical_repairs() -> None:
    source = (ROOT / "src/eccentric_tde_observer/nonlinear_apsidal_mode.py").read_text()
    tree = ast.parse(source)
    forbidden = {"clip", "nan_to_num"}
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert forbidden.isdisjoint(calls)
