"""ZO Hamiltonian 二维样条及坐标链式求导测试。"""

from __future__ import annotations

import numpy as np
import pytest

from eccentric_tde_observer.hamiltonian_table import (
    ZOHamiltonianSplineTable,
    build_zo_hamiltonian_spline_table,
)
from eccentric_tde_observer.source import PhysicalDomainError


def _synthetic_g(eccentricity: float, nonlinearity: float) -> float:
    """双三次样条可精确表示的二次控制函数。"""
    e = eccentricity
    q = nonlinearity
    return 2.3 + 0.7 * e - 0.4 * q + 1.1 * e**2 + 0.3 * e * q + 0.8 * q**2


def _synthetic_f(eccentricity: float, f_value: float) -> float:
    denominator = 1.0 - eccentricity * f_value
    q = (f_value - eccentricity) / denominator
    return _synthetic_g(eccentricity, q)


def _table() -> ZOHamiltonianSplineTable:
    eccentricity = np.linspace(0.0, 0.8, 9)
    nonlinearity = np.linspace(-0.85, 0.85, 13)
    values = np.array(
        [[_synthetic_g(e, q) for q in nonlinearity] for e in eccentricity]
    )
    return ZOHamiltonianSplineTable(eccentricity, nonlinearity, values)


def test_spline_recovers_quadratic_function_and_e_q_derivatives() -> None:
    table = _table()
    e = 0.37
    q = -0.26
    assert table.evaluate_e_q(e, q) == pytest.approx(_synthetic_g(e, q), abs=2.0e-13)
    assert table.evaluate_e_q(
        e, q, eccentricity_derivative_order=1
    ) == pytest.approx(0.7 + 2.2 * e + 0.3 * q, abs=3.0e-12)
    assert table.evaluate_e_q(
        e, q, nonlinearity_derivative_order=1
    ) == pytest.approx(-0.4 + 0.3 * e + 1.6 * q, abs=3.0e-12)
    assert table.evaluate_e_q(
        e, q, eccentricity_derivative_order=2
    ) == pytest.approx(2.2, abs=2.0e-11)
    assert table.evaluate_e_q(
        e,
        q,
        eccentricity_derivative_order=1,
        nonlinearity_derivative_order=1,
    ) == pytest.approx(0.3, abs=2.0e-11)
    assert table.evaluate_e_q(
        e, q, nonlinearity_derivative_order=2
    ) == pytest.approx(1.6, abs=2.0e-11)


def test_e_f_chain_rule_matches_independent_finite_differences() -> None:
    table = _table()
    e = 0.31
    f_value = -0.18
    result = table.evaluate_e_f(e, f_value)
    step = 2.0e-4

    f_00 = _synthetic_f(e, f_value)
    f_ep = _synthetic_f(e + step, f_value)
    f_em = _synthetic_f(e - step, f_value)
    f_fp = _synthetic_f(e, f_value + step)
    f_fm = _synthetic_f(e, f_value - step)
    f_pp = _synthetic_f(e + step, f_value + step)
    f_pm = _synthetic_f(e + step, f_value - step)
    f_mp = _synthetic_f(e - step, f_value + step)
    f_mm = _synthetic_f(e - step, f_value - step)

    derivative_e = (f_ep - f_em) / (2.0 * step)
    derivative_f = (f_fp - f_fm) / (2.0 * step)
    second_ee = (f_ep - 2.0 * f_00 + f_em) / step**2
    second_ff = (f_fp - 2.0 * f_00 + f_fm) / step**2
    second_ef = (f_pp - f_pm - f_mp + f_mm) / (4.0 * step**2)

    assert result.dimensionless_hamiltonian == pytest.approx(f_00, abs=2.0e-13)
    assert result.derivative_e_at_fixed_f == pytest.approx(derivative_e, rel=2.0e-7)
    assert result.derivative_f_at_fixed_e == pytest.approx(derivative_f, rel=2.0e-7)
    assert result.second_derivative_ee == pytest.approx(second_ee, rel=2.0e-7)
    assert result.second_derivative_ef == pytest.approx(second_ef, rel=2.0e-7)
    assert result.second_derivative_ff == pytest.approx(second_ff, rel=2.0e-7)


@pytest.mark.parametrize(
    ("eccentricity", "nonlinearity"),
    [(-1.0e-12, 0.0), (0.800000000001, 0.0), (0.3, -0.850000000001), (0.3, 0.850000000001)],
)
def test_table_rejects_extrapolation(eccentricity: float, nonlinearity: float) -> None:
    with pytest.raises(PhysicalDomainError, match="outside"):
        _table().evaluate_e_q(eccentricity, nonlinearity)


def test_table_rejects_invalid_nodes_and_derivative_orders() -> None:
    table = _table()
    with pytest.raises(PhysicalDomainError, match="integer from zero to two"):
        table.evaluate_e_q(0.3, 0.0, eccentricity_derivative_order=True)
    with pytest.raises(PhysicalDomainError, match="total order two"):
        table.evaluate_e_q(
            0.3,
            0.0,
            eccentricity_derivative_order=2,
            nonlinearity_derivative_order=1,
        )
    with pytest.raises(PhysicalDomainError, match="strictly increasing"):
        ZOHamiltonianSplineTable(
            [0.0, 0.2, 0.1, 0.3],
            [-0.6, -0.2, 0.2, 0.6],
            np.ones((4, 4)),
        )


def test_physical_table_builder_recovers_circular_hamiltonian() -> None:
    table = build_zo_hamiltonian_spline_table(
        np.linspace(0.0, 0.03, 4),
        np.linspace(-0.03, 0.03, 5),
        anomaly_points=32,
    )
    assert table.evaluate_e_q(0.0, 0.0) == pytest.approx(3.5, abs=2.0e-11)
