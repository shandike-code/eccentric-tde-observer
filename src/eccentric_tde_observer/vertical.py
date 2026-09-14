"""Explicit vertical-density closures for the bare-disc model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import betainc, betaincc, betainccinv, erfc, ndtri_exp

from .source import PhysicalDomainError, ZOSourceGrid


class FiniteSupportTailResolutionError(ArithmeticError):
    """Raised when an inverse column collapses onto a finite profile edge."""


class VerticalDensityProfile(Protocol):
    """Interface required by density and gray-photosphere calculations."""

    name: str

    def density_shape(self, scaled_height: ArrayLike) -> NDArray[np.float64]: ...

    def upper_column_fraction(
        self, scaled_height: ArrayLike
    ) -> NDArray[np.float64]: ...

    def inverse_upper_column_fraction(
        self, upper_fraction: ArrayLike
    ) -> NDArray[np.float64]: ...


@dataclass(frozen=True)
class GaussianVerticalProfile:
    """Normalized isothermal Gaussian closure in ``zeta = z/H``.

    This is a working closure, not a result of the ZO eccentric-disc theory.
    Its dimensionless density shape integrates to unity over both sides.
    """

    name: str = "normalized Gaussian [A]"

    def density_shape(self, scaled_height: ArrayLike) -> NDArray[np.float64]:
        zeta = np.asarray(scaled_height, dtype=np.float64)
        if not np.all(np.isfinite(zeta)):
            raise PhysicalDomainError("scaled_height must be finite")
        shape = np.exp(-0.5 * zeta**2) / np.sqrt(2.0 * np.pi)
        if not np.all(np.isfinite(shape)) or np.any(shape < 0.0):
            raise ArithmeticError("Gaussian density evaluation failed")
        return shape

    def upper_column_fraction(self, scaled_height: ArrayLike) -> NDArray[np.float64]:
        """Return ``integral_zeta^infinity f(u) du``."""
        zeta = np.asarray(scaled_height, dtype=np.float64)
        if not np.all(np.isfinite(zeta)):
            raise PhysicalDomainError("scaled_height must be finite")
        fraction = 0.5 * erfc(zeta / np.sqrt(2.0))
        if not np.all(np.isfinite(fraction)) or np.any(fraction < 0.0):
            raise ArithmeticError("Gaussian column evaluation failed")
        return fraction

    def inverse_upper_column_fraction(
        self, upper_fraction: ArrayLike
    ) -> NDArray[np.float64]:
        """Invert the upper-tail fraction for ``0 < q <= 1/2``.

        ``ndtri_exp(log(q))`` evaluates the inverse normal CDF without losing
        very small optical-depth fractions to ``1-q == 1`` roundoff.
        """
        fraction = np.asarray(upper_fraction, dtype=np.float64)
        invalid = (
            (~np.isfinite(fraction))
            | (fraction <= 0.0)
            | (fraction > 0.5)
        )
        if np.any(invalid):
            index = tuple(int(i) for i in np.argwhere(invalid)[0])
            raise PhysicalDomainError(
                "upper_fraction must satisfy 0 < q <= 1/2; "
                f"got {fraction[index]!r} at index {index}"
            )
        scaled_height = -ndtri_exp(np.log(fraction))
        if not np.all(np.isfinite(scaled_height)) or np.any(scaled_height < 0.0):
            raise ArithmeticError("Gaussian inverse-column evaluation failed")
        return scaled_height


GAUSSIAN_VERTICAL_PROFILE = GaussianVerticalProfile()


@dataclass(frozen=True)
class RadiationPressurePolytropeProfile:
    """Normalized finite-support ``n=3`` polytrope in ``zeta=z/H``.

    Lynch & Ogilvie (2021, arXiv:2011.02219), Appendix A, impose unit
    dimensionless column and unit second moment.  Their radiation-pressure
    dominated, vertically mixed solution has ``zeta_s=3`` and
    ``rho_tilde(0)=35/96``.  Applying that vertical solution to the ZO source
    is an explicit source-to-observer closure, not a new ZO source equation.
    """

    surface_scaled_height: float = 3.0
    central_density_shape: float = 35.0 / 96.0
    name: str = "n=3 finite polytrope (Lynch--Ogilvie 2021 A8) [L/A]"

    def density_shape(self, scaled_height: ArrayLike) -> NDArray[np.float64]:
        zeta = np.asarray(scaled_height, dtype=np.float64)
        if not np.all(np.isfinite(zeta)):
            raise PhysicalDomainError("scaled_height must be finite")
        shape = np.zeros_like(zeta)
        interior = np.abs(zeta) < self.surface_scaled_height
        scaled = zeta[interior] / self.surface_scaled_height
        shape[interior] = self.central_density_shape * (1.0 - scaled**2) ** 3
        if not np.all(np.isfinite(shape)) or np.any(shape < 0.0):
            raise ArithmeticError("finite polytrope density evaluation failed")
        return shape

    def upper_column_fraction(self, scaled_height: ArrayLike) -> NDArray[np.float64]:
        """Return ``integral_zeta^3 rho_tilde(u) du``."""
        zeta = np.asarray(scaled_height, dtype=np.float64)
        if not np.all(np.isfinite(zeta)):
            raise PhysicalDomainError("scaled_height must be finite")
        fraction = np.empty_like(zeta)
        below = zeta <= -self.surface_scaled_height
        above = zeta >= self.surface_scaled_height
        interior = ~(below | above)
        fraction[below] = 1.0
        fraction[above] = 0.0
        squared_scaled = (
            zeta[interior] / self.surface_scaled_height
        ) ** 2
        positive = zeta[interior] >= 0.0
        interior_fraction = np.empty_like(squared_scaled)
        interior_fraction[positive] = 0.5 * betaincc(
            0.5, 4.0, squared_scaled[positive]
        )
        interior_fraction[~positive] = 0.5 + 0.5 * betainc(
            0.5, 4.0, squared_scaled[~positive]
        )
        fraction[interior] = interior_fraction
        invalid = (
            (~np.isfinite(fraction)) | (fraction < 0.0) | (fraction > 1.0)
        )
        if np.any(invalid):
            index = tuple(int(i) for i in np.argwhere(invalid)[0])
            raise ArithmeticError(
                "finite polytrope column evaluation failed at "
                f"index {index}: {fraction[index]!r}"
            )
        return fraction

    def inverse_upper_column_fraction(
        self, upper_fraction: ArrayLike
    ) -> NDArray[np.float64]:
        """Invert the upper column for ``0 < q <= 1/2`` without clipping."""
        fraction = np.asarray(upper_fraction, dtype=np.float64)
        invalid = (
            (~np.isfinite(fraction)) | (fraction <= 0.0) | (fraction > 0.5)
        )
        if np.any(invalid):
            index = tuple(int(i) for i in np.argwhere(invalid)[0])
            raise PhysicalDomainError(
                "upper_fraction must satisfy 0 < q <= 1/2; "
                f"got {fraction[index]!r} at index {index}"
            )
        squared_scaled = betainccinv(0.5, 4.0, 2.0 * fraction)
        scaled_height = self.surface_scaled_height * np.sqrt(squared_scaled)
        collapsed = (fraction < 0.5) & (
            scaled_height >= self.surface_scaled_height
        )
        if np.any(collapsed):
            index = tuple(int(i) for i in np.argwhere(collapsed)[0])
            raise FiniteSupportTailResolutionError(
                "finite-support photosphere is closer to zeta_s than float64 "
                "can represent; refusing to place it exactly on the zero-density "
                f"edge for upper_fraction={fraction[index]!r} at index {index}"
            )
        if not np.all(np.isfinite(scaled_height)) or np.any(scaled_height < 0.0):
            raise ArithmeticError("finite polytrope inverse-column evaluation failed")
        return scaled_height


RADIATION_PRESSURE_POLYTROPE_PROFILE = RadiationPressurePolytropeProfile()


def density_on_scaled_height_grid_g_cm3(
    source: ZOSourceGrid,
    scaled_height_grid: ArrayLike,
    profile: VerticalDensityProfile = GAUSSIAN_VERTICAL_PROFILE,
) -> NDArray[np.float64]:
    """Evaluate ``rho = Sigma/H*f(z/H)`` on a one-dimensional zeta grid."""
    zeta = np.asarray(scaled_height_grid, dtype=np.float64)
    if zeta.ndim != 1 or zeta.size < 2:
        raise PhysicalDomainError(
            "scaled_height_grid must be one-dimensional with at least two points"
        )
    if not np.all(np.isfinite(zeta)) or np.any(np.diff(zeta) <= 0.0):
        raise PhysicalDomainError("scaled_height_grid must be finite and increasing")
    density = (
        source.surface_density_g_cm2[:, :, None]
        / source.scale_height_cm[:, :, None]
        * profile.density_shape(zeta)[None, None, :]
    )
    if not np.all(np.isfinite(density)) or np.any(density < 0.0):
        raise ArithmeticError("vertical density grid contains an invalid value")
    return density


def upper_column_density_g_cm2(
    source: ZOSourceGrid,
    scaled_height: ArrayLike,
    profile: VerticalDensityProfile = GAUSSIAN_VERTICAL_PROFILE,
) -> NDArray[np.float64]:
    """Return mass column above a scaled height, broadcast over the source grid."""
    zeta = np.asarray(scaled_height, dtype=np.float64)
    try:
        zeta_on_source = np.broadcast_to(zeta, source.shape)
    except ValueError as error:
        raise PhysicalDomainError(
            f"scaled_height cannot broadcast to source shape {source.shape}"
        ) from error
    column = source.surface_density_g_cm2 * profile.upper_column_fraction(
        zeta_on_source
    )
    if not np.all(np.isfinite(column)) or np.any(column < 0.0):
        raise ArithmeticError("upper column density contains an invalid value")
    return column
