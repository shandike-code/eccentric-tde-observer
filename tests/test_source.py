from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.fixtures import constant_temperature_circular_annulus
from eccentric_tde_observer.source import PhysicalDomainError, ZOSourceGrid


def _valid_fields() -> dict[str, object]:
    a = np.array([1.0e14, 1.5e14, 2.0e14])
    anomaly = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
    shape = (a.size, anomaly.size)
    return {
        "semimajor_axis_cm": a,
        "eccentric_anomaly_rad": anomaly,
        "eccentricity": np.array([0.1, 0.1, 0.1]),
        "jacobian": np.ones(shape),
        "surface_density_g_cm2": np.ones(shape),
        "scale_height_cm": np.full(shape, 1.0e12),
        "effective_temperature_k": np.full(shape, 5.0e4),
    }


def test_valid_source_is_immutable_and_has_expected_shape() -> None:
    source = ZOSourceGrid(**_valid_fields())
    assert source.shape == (3, 8)
    with pytest.raises(ValueError):
        source.jacobian[0, 0] = 2.0


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("jacobian", 0.0),
        ("surface_density_g_cm2", -1.0),
        ("scale_height_cm", 0.0),
        ("effective_temperature_k", np.nan),
    ],
)
def test_invalid_local_field_is_rejected(field: str, bad_value: float) -> None:
    values = _valid_fields()
    array = np.array(values[field], copy=True)
    array[1, 2] = bad_value
    values[field] = array
    with pytest.raises(PhysicalDomainError, match=field):
        ZOSourceGrid(**values)


def test_unbound_eccentricity_is_rejected() -> None:
    values = _valid_fields()
    values["eccentricity"] = np.array([0.1, 1.0, 0.1])
    with pytest.raises(PhysicalDomainError, match="0 <= e < 1"):
        ZOSourceGrid(**values)


def test_duplicate_periodic_endpoint_is_rejected() -> None:
    values = _valid_fields()
    values["eccentric_anomaly_rad"] = np.linspace(0.0, 2.0 * np.pi, 8)
    with pytest.raises(PhysicalDomainError, match="no repeated endpoint"):
        ZOSourceGrid(**values)


def test_failed_nested_orbit_condition_is_rejected() -> None:
    values = _valid_fields()
    values["eccentricity_gradient_per_cm"] = np.full(3, 1.0e-14)
    with pytest.raises(PhysicalDomainError, match="nested-orbit condition failed"):
        ZOSourceGrid(**values)


def test_analytic_fixture_passes_independent_nesting_check() -> None:
    source = constant_temperature_circular_annulus(1.0e14, 2.0e14, 5.0e4)
    assert source.has_independent_nesting_check


def test_source_code_does_not_use_forbidden_masking_helpers() -> None:
    source_root = Path(__file__).parents[1] / "src"
    forbidden = ("nan_to_num", "np.clip(")
    for path in source_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token!r} found in {path}"
