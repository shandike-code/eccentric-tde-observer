import numpy as np
import pytest

from eccentric_tde_observer import (
    PhysicalDomainError,
    build_ol_2d_hamiltonian_spline_table,
    ol_linearized_2d_dimensionless_hamiltonian,
    ol_untwisted_2d_dimensionless_hamiltonian,
)


def test_ol_2d_hamiltonian_recovers_circular_limit() -> None:
    value = ol_untwisted_2d_dimensionless_hamiltonian(0.0, 0.0)
    assert value == pytest.approx(3.0, abs=2.0e-15)


def test_ol_2d_hamiltonian_recovers_quadratic_hessian() -> None:
    step = 3.0e-4

    def value(eccentricity: float, f_value: float) -> float:
        return ol_untwisted_2d_dimensionless_hamiltonian(
            eccentricity, f_value, anomaly_points=1024
        )

    central = value(0.0, 0.0)
    second_e = (
        value(step, 0.0) - 2.0 * central + value(-step, 0.0)
    ) / step**2
    second_f = (
        value(0.0, step) - 2.0 * central + value(0.0, -step)
    ) / step**2
    mixed = (
        value(step, step)
        - value(step, -step)
        - value(-step, step)
        + value(-step, -step)
    ) / (4.0 * step**2)
    assert second_e == pytest.approx(2.0 / 3.0, rel=8.0e-7)
    assert second_f == pytest.approx(2.0 / 3.0, rel=8.0e-7)
    assert mixed == pytest.approx(-1.0 / 6.0, rel=8.0e-7)


def test_ol_2d_full_and_linearized_hamiltonians_converge_at_small_amplitude() -> None:
    direction = np.array((0.7, -0.4))
    errors = []
    for amplitude in (2.0e-2, 1.0e-2, 5.0e-3):
        eccentricity, f_value = amplitude * direction
        full = ol_untwisted_2d_dimensionless_hamiltonian(
            eccentricity, f_value
        )
        linearized = ol_linearized_2d_dimensionless_hamiltonian(
            eccentricity, f_value
        )
        errors.append(abs(full - linearized))
    assert errors[1] / errors[0] < 0.14
    assert errors[2] / errors[1] < 0.14


def test_ol_2d_periodic_quadrature_converges_without_rescaling() -> None:
    coarse = ol_untwisted_2d_dimensionless_hamiltonian(
        0.65, 0.25, anomaly_points=64
    )
    medium = ol_untwisted_2d_dimensionless_hamiltonian(
        0.65, 0.25, anomaly_points=128
    )
    fine = ol_untwisted_2d_dimensionless_hamiltonian(
        0.65, 0.25, anomaly_points=256
    )
    assert abs(fine / medium - 1.0) < 1.0e-12
    assert abs(medium / coarse - 1.0) < 1.0e-10


def test_ol_2d_spline_table_matches_direct_value_and_derivatives() -> None:
    table = build_ol_2d_hamiltonian_spline_table(
        np.linspace(0.0, 0.30, 25),
        np.linspace(-0.50, 0.15, 49),
        anomaly_points=256,
    )
    eccentricity = 0.191833
    f_value = 0.08
    interpolated = table.evaluate_e_f(eccentricity, f_value)
    direct = ol_untwisted_2d_dimensionless_hamiltonian(
        eccentricity, f_value, anomaly_points=1024
    )
    assert interpolated.dimensionless_hamiltonian == pytest.approx(
        direct, rel=2.0e-8
    )
    assert interpolated.second_derivative_ff > 0.0


@pytest.mark.parametrize(
    ("eccentricity", "f_value", "anomaly_points"),
    ((1.0, 0.0, 64), (0.5, 2.0, 64), (0.2, 0.1, 15), (0.2, 0.1, True)),
)
def test_ol_2d_hamiltonian_rejects_invalid_domain(
    eccentricity: float,
    f_value: float,
    anomaly_points: int,
) -> None:
    with pytest.raises(PhysicalDomainError):
        ol_untwisted_2d_dimensionless_hamiltonian(
            eccentricity, f_value, anomaly_points=anomaly_points
        )
