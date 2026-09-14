"""Formal H/He feedback-pair diagnostics for a converged radiation pair."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EncodedResidualNorms:
    """Three residual norms frozen by the Phase 7B9bu acceptance rule."""

    l2: float
    mass_weighted: float
    maximum_cell: float


@dataclass(frozen=True)
class TrialFeedbackPairDiagnostics:
    """Pure numerical diagnostics needed before accepting one material trial."""

    photoionization_volume_l1: np.ndarray
    total_recombination_volume_l1: np.ndarray
    atomic_heating_volume_l1: float
    direct_heating_volume_l1: float
    formal_heating_volume_l1: float
    inner_noise_to_trial_signal_l2_ratio: float
    candidate_norms: EncodedResidualNorms
    base_norms: EncodedResidualNorms


def weighted_volume_l1(
    previous: np.ndarray,
    final: np.ndarray,
    cell_width: np.ndarray,
) -> np.ndarray:
    """Return the volume-weighted symmetric L1 change without floors or clipping."""
    previous_array = np.asarray(previous, dtype=np.float64)
    final_array = np.asarray(final, dtype=np.float64)
    width = np.asarray(cell_width, dtype=np.float64)
    if (
        previous_array.shape != final_array.shape
        or previous_array.ndim < 1
        or previous_array.shape[0] != width.size
        or np.any(~np.isfinite(previous_array))
        or np.any(~np.isfinite(final_array))
        or np.any(~np.isfinite(width))
        or np.any(width <= 0.0)
    ):
        raise ValueError("formal feedback arrays or cell widths are invalid")
    trailing = previous_array.ndim - 1
    weight = width.reshape((width.size,) + (1,) * trailing)
    numerator = np.sum(weight * np.abs(final_array - previous_array), axis=0)
    denominator = np.sum(
        weight * np.maximum(np.abs(previous_array), np.abs(final_array)), axis=0
    )
    # 中文：零信号分量只有在两态都严格为零时才定义为零差异。
    if np.any((denominator == 0.0) & (numerator != 0.0)):
        raise ArithmeticError("non-zero feedback difference has zero normalization")
    result = np.zeros_like(numerator, dtype=np.float64)
    np.divide(numerator, denominator, out=result, where=denominator > 0.0)
    return result


def encoded_residual_norms(
    residual: np.ndarray,
    cell_mass: np.ndarray,
) -> EncodedResidualNorms:
    """Evaluate L2, mass-weighted, and maximum-cell encoded residual norms."""
    array = np.asarray(residual, dtype=np.float64)
    mass = np.asarray(cell_mass, dtype=np.float64)
    if array.ndim == 1 and array.size == 4 * mass.size:
        array = array.reshape(mass.size, 4)
    if (
        array.ndim != 2
        or array.shape[0] != mass.size
        or array.shape[1] != 4
        or np.any(~np.isfinite(array))
        or np.any(~np.isfinite(mass))
        or np.any(mass <= 0.0)
    ):
        raise ValueError("encoded residual or cell masses are invalid")
    cell_squared = np.sum(array * array, axis=1)
    return EncodedResidualNorms(
        l2=float(np.linalg.norm(array)),
        mass_weighted=float(np.sqrt(np.sum(mass * cell_squared) / np.sum(mass))),
        maximum_cell=float(np.sqrt(np.max(cell_squared))),
    )


def _strict_ratio(numerator: float, denominator: float, *, name: str) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator):
        raise ValueError(f"{name} ratio inputs must be finite")
    if denominator <= 0.0:
        raise ValueError(f"{name} ratio requires a positive denominator")
    return numerator / denominator


def trial_feedback_pair_diagnostics(
    *,
    previous_feedback: dict[str, np.ndarray],
    final_feedback: dict[str, np.ndarray],
    previous_encoded_residual: np.ndarray,
    final_encoded_residual: np.ndarray,
    base_encoded_residual: np.ndarray,
    cell_width: np.ndarray,
    cell_mass: np.ndarray,
) -> TrialFeedbackPairDiagnostics:
    """Evaluate the unchanged Phase 7B9f/7B9bu feedback and residual metrics."""
    required = (
        "photoionization_s1",
        "total_recombination_cm3_s",
        "atomic_rate_heating_erg_s_cm3",
        "source_direct_heating_erg_s_cm3",
        "source_formal_heating_erg_s_cm3",
    )
    if any(name not in previous_feedback or name not in final_feedback for name in required):
        raise KeyError("formal feedback pair is incomplete")
    previous_residual = np.asarray(previous_encoded_residual, dtype=np.float64)
    final_residual = np.asarray(final_encoded_residual, dtype=np.float64)
    base_residual = np.asarray(base_encoded_residual, dtype=np.float64)
    if (
        previous_residual.shape != final_residual.shape
        or previous_residual.shape != base_residual.shape
    ):
        raise ValueError("encoded residual shapes are inconsistent")
    candidate_norms = encoded_residual_norms(final_residual, cell_mass)
    base_norms = encoded_residual_norms(base_residual, cell_mass)
    inner_noise = final_residual - previous_residual
    trial_signal = final_residual - base_residual
    return TrialFeedbackPairDiagnostics(
        photoionization_volume_l1=weighted_volume_l1(
            previous_feedback["photoionization_s1"],
            final_feedback["photoionization_s1"],
            cell_width,
        ),
        total_recombination_volume_l1=weighted_volume_l1(
            previous_feedback["total_recombination_cm3_s"],
            final_feedback["total_recombination_cm3_s"],
            cell_width,
        ),
        atomic_heating_volume_l1=float(
            weighted_volume_l1(
                previous_feedback["atomic_rate_heating_erg_s_cm3"],
                final_feedback["atomic_rate_heating_erg_s_cm3"],
                cell_width,
            )
        ),
        direct_heating_volume_l1=float(
            weighted_volume_l1(
                previous_feedback["source_direct_heating_erg_s_cm3"],
                final_feedback["source_direct_heating_erg_s_cm3"],
                cell_width,
            )
        ),
        formal_heating_volume_l1=float(
            weighted_volume_l1(
                previous_feedback["source_formal_heating_erg_s_cm3"],
                final_feedback["source_formal_heating_erg_s_cm3"],
                cell_width,
            )
        ),
        inner_noise_to_trial_signal_l2_ratio=_strict_ratio(
            float(np.linalg.norm(inner_noise)),
            float(np.linalg.norm(trial_signal)),
            name="inner-noise/trial-signal",
        ),
        candidate_norms=candidate_norms,
        base_norms=base_norms,
    )


def trial_feedback_pair_gate_checks(
    diagnostics: TrialFeedbackPairDiagnostics,
    gates: dict[str, object],
) -> dict[str, bool]:
    """Apply the frozen Phase 7B9bu thresholds without changing any cutoff."""
    candidate = diagnostics.candidate_norms
    base = diagnostics.base_norms
    return {
        "last_two_photoionization_pass": bool(
            np.max(diagnostics.photoionization_volume_l1)
            < float(gates["maximum_last_two_photoionization_volume_l1_below"])
        ),
        "last_two_total_recombination_pass": bool(
            np.max(diagnostics.total_recombination_volume_l1)
            < float(gates["maximum_last_two_total_recombination_volume_l1_below"])
        ),
        "last_two_atomic_heating_pass": diagnostics.atomic_heating_volume_l1
        < float(gates["last_two_atomic_heating_volume_l1_below"]),
        "last_two_direct_heating_pass": diagnostics.direct_heating_volume_l1
        < float(gates["last_two_direct_heating_volume_l1_below"]),
        "last_two_formal_heating_pass": diagnostics.formal_heating_volume_l1
        < float(gates["last_two_formal_heating_volume_l1_below"]),
        "inner_noise_resolved_pass": diagnostics.inner_noise_to_trial_signal_l2_ratio
        < float(gates["inner_noise_to_trial_signal_l2_ratio_below"]),
        "candidate_l2_contraction_pass": _strict_ratio(
            candidate.l2, base.l2, name="candidate/base L2"
        )
        < float(gates["candidate_to_base_residual_l2_ratio_below"]),
        "candidate_mass_weighted_contraction_pass": _strict_ratio(
            candidate.mass_weighted,
            base.mass_weighted,
            name="candidate/base mass-weighted",
        )
        < float(gates["candidate_to_base_mass_weighted_norm_ratio_below"]),
        "candidate_maximum_cell_contraction_pass": _strict_ratio(
            candidate.maximum_cell,
            base.maximum_cell,
            name="candidate/base maximum-cell",
        )
        < float(gates["candidate_to_base_maximum_cell_norm_ratio_below"]),
    }
