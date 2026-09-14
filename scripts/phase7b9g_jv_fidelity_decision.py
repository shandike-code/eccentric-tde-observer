"""Phase 7B9g：以实测内迭代噪声判断严格全频 Jv 是否可辨识。"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
    ground_state_material_trial_within_trust_region,
)
from eccentric_tde_observer.low_rank_secant_preconditioner import (
    LowRankInverseSecantPreconditioner,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _material_residual(
    feedback_path: Path,
    codec: GroundStateLogSimplexCodec,
    encoded_current: np.ndarray,
    density: np.ndarray,
    old_temperature: np.ndarray,
    old_hydrogen: np.ndarray,
    old_helium: np.ndarray,
    duration: float,
) -> np.ndarray:
    with np.load(feedback_path) as feedback:
        response = frozen_radiation_material_response(
            density,
            old_temperature,
            old_hydrogen,
            old_helium,
            duration,
            feedback["half_photoionization_s1"],
            feedback["half_total_recombination_cm3_s"],
            feedback["half_atomic_rate_heating_erg_s_cm3"],
        )
    encoded_target = np.asarray(
        codec.encode(
            response.temperature_k,
            response.hydrogen_fraction,
            response.helium_fraction,
        )
    )
    return encoded_target - encoded_current


def _first_trust_relaxation(
    codec: GroundStateLogSimplexCodec,
    state: np.ndarray,
    direction: np.ndarray,
) -> float | None:
    for exponent in range(25):
        relaxation = 2.0 ** (-exponent)
        if ground_state_material_trial_within_trust_region(
            codec,
            state,
            state + relaxation * direction,
            maximum_relative_temperature_change=0.5,
            maximum_absolute_material_energy_increment_fraction=0.25,
            maximum_population_fraction_change=0.05,
        ):
            return relaxation
    return None


def run() -> dict[str, object]:
    source_paths = {
        "phase7b9f_summary": OUTPUT
        / "phase7b9f_converged_feedback_residual_summary.json",
        "phase7b9e2_summary": OUTPUT
        / "phase7b9e2_science_functional_extension_summary.json",
        "previous_feedback": OUTPUT / "phase7b9f_previous_feedback.npz",
        "final_feedback": OUTPUT / "phase7b9f_final_feedback.npz",
        "base_residual": OUTPUT / "phase7b9f_base_material_residual.npy",
        "low_rank_artifact": OUTPUT / "phase7b9c_low_rank_preconditioner.npz",
        "current_material": OUTPUT / "phase7b7h_second_material_iterate.npz",
        "physical_old_time_level": OUTPUT / "phase7b4r_depth128_phase2048.npz",
    }
    sources = {
        name: {
            "path": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for name, path in source_paths.items()
    }
    phase7b9f = json.loads(source_paths["phase7b9f_summary"].read_text(encoding="utf-8"))
    phase7b9e2 = json.loads(
        source_paths["phase7b9e2_summary"].read_text(encoding="utf-8")
    )
    if (
        phase7b9f["decision"]["phase7b9f_gate_passed"] is not True
        or phase7b9f["recoverable_residual_status"] != "complete"
        or phase7b9e2["decision"]["phase7b9e2_gate_passed"] is not True
    ):
        raise RuntimeError("Phase 7B9g requires passed 7B9e2 and 7B9f")
    with np.load(source_paths["current_material"]) as current:
        phase = int(current["phase_index"])
        duration = float(current["step_duration_s"])
        density = np.array(current["density_g_cm3"], copy=True)
        temperature = np.array(current["temperature_k"], copy=True)
        hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        helium = np.array(current["helium_fraction"], copy=True)
    with np.load(source_paths["physical_old_time_level"]) as old:
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
    codec = GroundStateLogSimplexCodec(128)
    encoded_current = np.asarray(codec.encode(temperature, hydrogen, helium))
    previous_residual = _material_residual(
        source_paths["previous_feedback"],
        codec,
        encoded_current,
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
    )
    final_residual = _material_residual(
        source_paths["final_feedback"],
        codec,
        encoded_current,
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
    )
    frozen_residual = np.asarray(np.load(source_paths["base_residual"]))
    if not np.array_equal(final_residual, frozen_residual):
        raise RuntimeError("Phase 7B9g final material residual changed")
    successive_difference = final_residual - previous_residual
    inner_noise_l2 = float(np.linalg.norm(successive_difference))
    with np.load(source_paths["low_rank_artifact"]) as low_rank:
        state_secant = np.array(low_rank["state_secant"], copy=True)
        residual_secant = np.array(low_rank["residual_secant"], copy=True)
        old_direction = np.array(low_rank["low_rank_direction"], copy=True)
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        state_secant[:, None],
        residual_secant[:, None],
        base_inverse_scale=-1.0,
        maximum_gram_condition_number=1.0e8,
    )
    direction = -preconditioner.apply(final_residual)
    relative_step = 1.0e-7
    epsilon = relative_step * (1.0 + float(np.linalg.norm(encoded_current))) / float(
        np.linalg.norm(direction)
    )
    displacement_l2 = float(epsilon * np.linalg.norm(direction))
    # 中文：这是由唯一真实割线给出的方向尺度估计，不冒充已计算的 Jv。
    observed_secant_gain = float(
        np.linalg.norm(residual_secant) / np.linalg.norm(state_secant)
    )
    estimated_signal_l2 = observed_secant_gain * displacement_l2
    noise_to_signal = inner_noise_l2 / estimated_signal_l2
    exact_inverse_signal_l2 = epsilon * float(np.linalg.norm(final_residual))
    exact_inverse_noise_to_signal = inner_noise_l2 / exact_inverse_signal_l2
    trust_relaxation = _first_trust_relaxation(
        codec, encoded_current, direction
    )
    history = phase7b9e2["history"]
    latest_contraction = float(
        history[-1]["raw_source_map_residual"]
        / history[-2]["raw_source_map_residual"]
    )
    if not 0.0 < latest_contraction < 1.0:
        raise ArithmeticError("Phase 7B9g source contraction is invalid")
    sensitivity: dict[str, object] = {}
    for maximum_ratio in (1.0, 0.1, 0.01):
        required_factor = maximum_ratio / noise_to_signal
        additional_maps = max(
            0, int(math.ceil(math.log(required_factor) / math.log(latest_contraction)))
        )
        sensitivity[f"noise_to_signal_below_{maximum_ratio:g}"] = {
            "additional_maps_under_constant_contraction": additional_maps,
            "wall_time_h_using_latest_map": additional_maps
            * float(history[-1]["wall_runtime_s"])
            / 3600.0,
        }
    strict_jv_identifiable = bool(noise_to_signal < 0.1)
    finite_trial_authorized = bool(
        not strict_jv_identifiable
        and trust_relaxation is not None
        and phase7b9f["decision"][
            "one_preconditioned_full_frequency_jv_decision_authorized"
        ]
    )
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    maps = np.asarray([row["total_source_maps_at_current_material"] for row in history])
    axes[0, 0].semilogy(
        maps, [row["raw_source_map_residual"] for row in history], "o-"
    )
    axes[0, 0].axhline(1.0e-4, color="0.25", ls="--", label="Base residual gate")
    axes[0, 0].set(
        xlabel="Total source maps at fixed material",
        ylabel="Global-scale radiation change",
        title="(a) Base radiation convergence",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].bar(
        ("Measured inner\nresidual change", "Secant-scale\nFD signal"),
        (inner_noise_l2, estimated_signal_l2),
        color=("#a45a52", "#4f7cac"),
    )
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        ylabel="Encoded residual L2 norm",
        title="(b) Finite-difference signal is unresolved",
    )
    ratios = np.asarray((1.0, 0.1, 0.01))
    maps_needed = np.asarray(
        [
            sensitivity[f"noise_to_signal_below_{value:g}"][
                "additional_maps_under_constant_contraction"
            ]
            for value in ratios
        ]
    )
    axes[1, 0].semilogx(ratios, maps_needed, "o-")
    axes[1, 0].invert_xaxis()
    axes[1, 0].set(
        xlabel="Allowed inner-noise / FD-signal ratio",
        ylabel="Estimated additional source maps",
        title="(c) Constant-contraction cost sensitivity",
    )
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.03,
        0.96,
        "(d) Decision\n\n"
        f"FD relative step = {relative_step:.1e}\n"
        f"FD state displacement = {displacement_l2:.3e}\n"
        f"Measured residual change = {inner_noise_l2:.3e}\n"
        f"Estimated FD signal = {estimated_signal_l2:.3e}\n"
        f"Noise / signal = {noise_to_signal:.1f}\n"
        f"Largest physical trial relaxation = {trust_relaxation}\n\n"
        "Strict full-frequency Jv: rejected\n"
        "Finite protected quasi-Newton trial: authorized",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.1,
    )
    figure_path = OUTPUT / "phase7b9g_jv_fidelity_decision.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    artifact_path = OUTPUT / "phase7b9g_jv_fidelity_decision.npz"
    temporary = artifact_path.with_name(f"{artifact_path.stem}.tmp.npz")
    np.savez(
        temporary,
        previous_residual=previous_residual,
        final_residual=final_residual,
        successive_residual_difference=successive_difference,
        preconditioned_direction=direction,
    )
    os.replace(temporary, artifact_path)
    report = {
        "phase": "7B9g strict Jv fidelity and finite-trial decision",
        "classification": "[A-diagnostic]+[V]+[O]",
        "sources": sources,
        "finite_difference_relative_step": relative_step,
        "finite_difference_epsilon": epsilon,
        "finite_difference_state_displacement_l2": displacement_l2,
        "previous_residual_l2_norm": float(np.linalg.norm(previous_residual)),
        "final_residual_l2_norm": float(np.linalg.norm(final_residual)),
        "successive_inner_residual_difference_l2": inner_noise_l2,
        "successive_inner_residual_difference_maximum": float(
            np.max(np.abs(successive_difference))
        ),
        "observed_secant_gain": observed_secant_gain,
        "estimated_finite_difference_signal_l2": estimated_signal_l2,
        "measured_noise_to_estimated_signal_ratio": noise_to_signal,
        "exact_inverse_signal_l2_diagnostic": exact_inverse_signal_l2,
        "exact_inverse_noise_to_signal_ratio_diagnostic": (
            exact_inverse_noise_to_signal
        ),
        "preconditioned_direction_l2_norm": float(np.linalg.norm(direction)),
        "preconditioned_direction_cosine_with_phase7b9c": float(
            np.dot(direction, old_direction)
            / (np.linalg.norm(direction) * np.linalg.norm(old_direction))
        ),
        "largest_physical_trust_relaxation": trust_relaxation,
        "latest_global_source_contraction": latest_contraction,
        "cost_sensitivity": sensitivity,
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "artifact_sha256": _sha256(artifact_path),
        "decision": {
            "base_inner_converged_residual_valid": True,
            "strict_full_frequency_jv_signal_identifiable": strict_jv_identifiable,
            "strict_full_frequency_jv_evaluated": False,
            "strict_full_frequency_jv_rejected_at_current_inner_fidelity": bool(
                not strict_jv_identifiable
            ),
            "finite_protected_quasi_newton_trial_authorized": finite_trial_authorized,
            "finite_trial_may_be_called_jv": False,
            "static_approximation_rejected": False,
            "accepted_as_dynamic_nlte_solution": False,
            "phase7b9g_gate_passed": bool(
                not strict_jv_identifiable and finite_trial_authorized
            ),
        },
        "figures": [figure_path.name],
    }
    summary_path = OUTPUT / "phase7b9g_jv_fidelity_decision_summary.json"
    _write_json_atomic(summary_path, report)
    return report


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
