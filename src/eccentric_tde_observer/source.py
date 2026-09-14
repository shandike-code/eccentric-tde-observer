"""Input contract for fields supplied by the Zanazzi--Ogilvie source model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


class PhysicalDomainError(ValueError):
    """Raised when a source field is outside the model's physical domain."""


def _finite_array(name: str, values: ArrayLike, ndim: int) -> NDArray[np.float64]:
    array = np.array(values, dtype=np.float64, copy=True)
    if array.ndim != ndim:
        raise PhysicalDomainError(f"{name} must have {ndim} dimensions; got {array.shape}")
    invalid = ~np.isfinite(array)
    if np.any(invalid):
        index = tuple(int(i) for i in np.argwhere(invalid)[0])
        raise PhysicalDomainError(f"{name} contains a non-finite value at index {index}")
    array.setflags(write=False)
    return array


def _require_positive(name: str, values: NDArray[np.float64]) -> None:
    invalid = values <= 0.0
    if np.any(invalid):
        index = tuple(int(i) for i in np.argwhere(invalid)[0])
        raise PhysicalDomainError(
            f"{name} must be strictly positive; got {values[index]!r} at index {index}"
        )


@dataclass(frozen=True)
class ZOSourceGrid:
    """Zanazzi--Ogilvie source fields sampled on an ``(a, E)`` grid.

    All quantities use cgs units.  The eccentric anomaly grid is periodic and
    must not repeat the endpoint at ``2*pi``.  ``jacobian`` is the ZO
    dimensionless canonical Jacobian ``j``.  The ZO 2022 Erratum corrected
    radiative area is ``a*j*(1-e*cos(E))*da*dE``.  The supplied source fields
    remain unchanged; only downstream radiative quadrature receives this
    factor.

    The optional gradients allow an independent nested-orbit check.  They are
    not reconstructed numerically here because doing so would introduce an
    unstated differentiation prescription.
    """

    semimajor_axis_cm: ArrayLike
    eccentric_anomaly_rad: ArrayLike
    eccentricity: ArrayLike
    jacobian: ArrayLike
    surface_density_g_cm2: ArrayLike
    scale_height_cm: ArrayLike
    effective_temperature_k: ArrayLike
    apsidal_angle_rad: float = 0.0
    eccentricity_gradient_per_cm: ArrayLike | None = None
    apsidal_gradient_per_cm: ArrayLike | None = None
    label: str = "unspecified"
    provenance: str = "unspecified"

    def __post_init__(self) -> None:
        a = _finite_array("semimajor_axis_cm", self.semimajor_axis_cm, 1)
        anomaly = _finite_array("eccentric_anomaly_rad", self.eccentric_anomaly_rad, 1)
        eccentricity = _finite_array("eccentricity", self.eccentricity, 1)
        jacobian = _finite_array("jacobian", self.jacobian, 2)
        sigma = _finite_array("surface_density_g_cm2", self.surface_density_g_cm2, 2)
        height = _finite_array("scale_height_cm", self.scale_height_cm, 2)
        temperature = _finite_array(
            "effective_temperature_k", self.effective_temperature_k, 2
        )

        if a.size < 2:
            raise PhysicalDomainError("semimajor_axis_cm needs at least two points")
        if anomaly.size < 4:
            raise PhysicalDomainError("eccentric_anomaly_rad needs at least four points")
        _require_positive("semimajor_axis_cm", a)
        if np.any(np.diff(a) <= 0.0):
            raise PhysicalDomainError("semimajor_axis_cm must be strictly increasing")
        if np.any(np.diff(anomaly) <= 0.0):
            raise PhysicalDomainError("eccentric_anomaly_rad must be strictly increasing")
        if anomaly[0] < 0.0 or anomaly[-1] >= 2.0 * np.pi:
            raise PhysicalDomainError(
                "eccentric_anomaly_rad must lie in [0, 2*pi) with no repeated endpoint"
            )

        expected_radial = (a.size,)
        expected_field = (a.size, anomaly.size)
        if eccentricity.shape != expected_radial:
            raise PhysicalDomainError(
                f"eccentricity must have shape {expected_radial}; got {eccentricity.shape}"
            )
        for name, field in (
            ("jacobian", jacobian),
            ("surface_density_g_cm2", sigma),
            ("scale_height_cm", height),
            ("effective_temperature_k", temperature),
        ):
            if field.shape != expected_field:
                raise PhysicalDomainError(
                    f"{name} must have shape {expected_field}; got {field.shape}"
                )

        invalid_eccentricity = (eccentricity < 0.0) | (eccentricity >= 1.0)
        if np.any(invalid_eccentricity):
            index = int(np.argwhere(invalid_eccentricity)[0, 0])
            raise PhysicalDomainError(
                "eccentricity must satisfy 0 <= e < 1; "
                f"got {eccentricity[index]!r} at index {(index,)}"
            )
        _require_positive("jacobian", jacobian)
        _require_positive("surface_density_g_cm2", sigma)
        _require_positive("scale_height_cm", height)
        _require_positive("effective_temperature_k", temperature)

        apsidal_angle = float(self.apsidal_angle_rad)
        if not np.isfinite(apsidal_angle):
            raise PhysicalDomainError("apsidal_angle_rad must be finite")

        e_gradient = None
        varpi_gradient = None
        if self.eccentricity_gradient_per_cm is not None:
            e_gradient = _finite_array(
                "eccentricity_gradient_per_cm",
                self.eccentricity_gradient_per_cm,
                1,
            )
            if e_gradient.shape != expected_radial:
                raise PhysicalDomainError(
                    "eccentricity_gradient_per_cm must match the radial grid"
                )
            if self.apsidal_gradient_per_cm is None:
                varpi_gradient = np.zeros_like(e_gradient)
                varpi_gradient.setflags(write=False)
            else:
                varpi_gradient = _finite_array(
                    "apsidal_gradient_per_cm", self.apsidal_gradient_per_cm, 1
                )
                if varpi_gradient.shape != expected_radial:
                    raise PhysicalDomainError(
                        "apsidal_gradient_per_cm must match the radial grid"
                    )

            nesting_measure = (eccentricity + a * e_gradient) ** 2 + (
                a * eccentricity * varpi_gradient
            ) ** 2
            invalid_nesting = nesting_measure >= 1.0
            if np.any(invalid_nesting):
                index = int(np.argwhere(invalid_nesting)[0, 0])
                raise PhysicalDomainError(
                    "nested-orbit condition failed: "
                    "(e + a*de/da)^2 + (a*e*dvarpi/da)^2 must be < 1; "
                    f"got {nesting_measure[index]!r} at index {(index,)}"
                )
        elif self.apsidal_gradient_per_cm is not None:
            raise PhysicalDomainError(
                "apsidal_gradient_per_cm requires eccentricity_gradient_per_cm"
            )

        for name, value in (
            ("semimajor_axis_cm", a),
            ("eccentric_anomaly_rad", anomaly),
            ("eccentricity", eccentricity),
            ("jacobian", jacobian),
            ("surface_density_g_cm2", sigma),
            ("scale_height_cm", height),
            ("effective_temperature_k", temperature),
            ("apsidal_angle_rad", apsidal_angle),
            ("eccentricity_gradient_per_cm", e_gradient),
            ("apsidal_gradient_per_cm", varpi_gradient),
        ):
            object.__setattr__(self, name, value)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.semimajor_axis_cm.size, self.eccentric_anomaly_rad.size)

    @property
    def has_independent_nesting_check(self) -> bool:
        return self.eccentricity_gradient_per_cm is not None
