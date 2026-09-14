"""Gray vertical photosphere closure for the bare eccentric disc."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .source import PhysicalDomainError, ZOSourceGrid
from .vertical import GAUSSIAN_VERTICAL_PROFILE, VerticalDensityProfile


class OpticallyThinColumnError(PhysicalDomainError):
    """Raised when an upper photosphere does not exist above the midplane."""


def _readonly(array: NDArray[np.float64]) -> NDArray[np.float64]:
    array.setflags(write=False)
    return array


@dataclass(frozen=True)
class GrayPhotosphere:
    """Upper ``tau=tau_star`` surface for a specified gray opacity."""

    opacity_cm2_g: NDArray[np.float64]
    target_optical_depth: float
    total_vertical_optical_depth: NDArray[np.float64]
    midplane_to_surface_optical_depth: NDArray[np.float64]
    scaled_height: NDArray[np.float64]
    height_cm: NDArray[np.float64]
    profile_name: str


def solve_gray_photosphere(
    source: ZOSourceGrid,
    opacity_cm2_g: ArrayLike,
    target_optical_depth: float = 2.0 / 3.0,
    profile: VerticalDensityProfile = GAUSSIAN_VERTICAL_PROFILE,
) -> GrayPhotosphere:
    """Solve ``kappa*integral_z^infinity rho dz = tau_star``.

    Opacity is an explicit caller input.  No cell is promoted to optically
    thick by clipping its column or moving the photosphere below the midplane.
    """
    opacity_input = np.asarray(opacity_cm2_g, dtype=np.float64)
    try:
        opacity = np.array(
            np.broadcast_to(opacity_input, source.shape), dtype=np.float64, copy=True
        )
    except ValueError as error:
        raise PhysicalDomainError(
            f"opacity_cm2_g cannot broadcast to source shape {source.shape}"
        ) from error
    invalid_opacity = (~np.isfinite(opacity)) | (opacity <= 0.0)
    if np.any(invalid_opacity):
        index = tuple(int(i) for i in np.argwhere(invalid_opacity)[0])
        raise PhysicalDomainError(
            "opacity_cm2_g must be finite and positive; "
            f"got {opacity[index]!r} at index {index}"
        )

    target = float(target_optical_depth)
    if not np.isfinite(target) or target <= 0.0:
        raise PhysicalDomainError("target_optical_depth must be finite and positive")

    total_depth = opacity * source.surface_density_g_cm2
    if not np.all(np.isfinite(total_depth)) or np.any(total_depth <= 0.0):
        raise PhysicalDomainError("kappa*Sigma produced an invalid optical depth")
    midplane_depth = 0.5 * total_depth
    marginal = np.isclose(
        midplane_depth,
        target,
        rtol=8.0 * np.finfo(np.float64).eps,
        atol=0.0,
    )
    optically_thin = (midplane_depth < target) & (~marginal)
    if np.any(optically_thin):
        index = tuple(int(i) for i in np.argwhere(optically_thin)[0])
        raise OpticallyThinColumnError(
            "no upper tau=tau_star photosphere exists above the midplane: "
            f"kappa*Sigma/2={midplane_depth[index]!r} < {target!r} "
            f"at index {index}"
        )

    scaled_height = np.empty(source.shape, dtype=np.float64)
    scaled_height[marginal] = 0.0
    optically_thick = ~marginal
    required_upper_fraction = target / total_depth[optically_thick]
    scaled_height[optically_thick] = profile.inverse_upper_column_fraction(
        required_upper_fraction
    )
    height = source.scale_height_cm * scaled_height
    reconstructed_depth = total_depth * profile.upper_column_fraction(scaled_height)
    if not np.allclose(reconstructed_depth, target, rtol=1.0e-12, atol=0.0):
        maximum_error = float(np.max(np.abs(reconstructed_depth / target - 1.0)))
        raise ArithmeticError(
            f"photosphere optical-depth reconstruction failed: {maximum_error!r}"
        )

    return GrayPhotosphere(
        opacity_cm2_g=_readonly(opacity),
        target_optical_depth=target,
        total_vertical_optical_depth=_readonly(total_depth),
        midplane_to_surface_optical_depth=_readonly(midplane_depth),
        scaled_height=_readonly(scaled_height),
        height_cm=_readonly(height),
        profile_name=profile.name,
    )
