"""Phase 7B9a：物理域矩阵自由 Newton--Krylov 组件门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.coupled_material_newton_krylov import (
    EncodedMaterialFixedPointResidual,
    GroundStateLogSimplexCodec,
    GroundStateMaterialState,
    ground_state_material_trial_within_trust_region,
    solve_matrix_free_newton_krylov,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)
from eccentric_tde_observer.source import PhysicalDomainError


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "c80f6db19ae067ac5b7b320f0de4e4de04acbe9ec3c296f1b63942b64958fb36"
)


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


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B9a protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B9a source changed: {source['path']}")
    return protocol


def _state_from_response(response) -> GroundStateMaterialState:
    return GroundStateMaterialState(
        temperature_k=np.asarray(response.temperature_k),
        hydrogen_fraction=np.asarray(response.hydrogen_fraction),
        helium_fraction=np.asarray(response.helium_fraction),
        specific_material_energy_erg_g=np.asarray(
            response.recovered_specific_material_energy_erg_g
        ),
    )


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    component_residual: np.ndarray,
    actual_history: np.ndarray,
    manufactured_history: np.ndarray,
    actual_relaxations: np.ndarray,
    diagnostics: dict[str, float],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    labels = (
        "Log thermal energy",
        "Log H II/H I",
        "Log He II/He I",
        "Log He III/He I",
    )
    for index, label in enumerate(labels):
        axes[0, 0].plot(mass_centre, component_residual[:, index], label=label)
    axes[0, 0].axhline(0.0, color="0.25", ls=":")
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Encoded fixed-point residual",
        title="(a) Actual 128-cell four-variable residual",
    )
    axes[0, 0].legend(frameon=False, fontsize=8.5)
    axes[0, 1].semilogy(np.arange(actual_history.size), actual_history, marker="o")
    axes[0, 1].axhline(1.0e-9, color="0.25", ls=":", label="Component gate")
    axes[0, 1].set(
        xlabel="Newton iteration",
        ylabel="Encoded residual L2 norm",
        title="(b) Actual frozen-feedback solve",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].semilogy(
        np.arange(manufactured_history.size), manufactured_history, marker="o"
    )
    axes[1, 0].axhline(1.0e-9, color="0.25", ls=":", label="Manufactured gate")
    axes[1, 0].set(
        xlabel="Newton iteration",
        ylabel="Residual L2 norm",
        title="(c) Manufactured nonlocal coupling",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.04,
        0.95,
        "(d) Component scope and cost\n\n"
        f"Encoded unknown count = {int(diagnostics['unknowns'])}\n"
        f"Codec temperature error = {diagnostics['temperature_roundtrip']:.3e}\n"
        f"Codec population error = {diagnostics['population_roundtrip']:.3e}\n"
        f"Actual Newton iterations = {int(diagnostics['actual_iterations'])}\n"
        f"Actual minimum relaxation = {float(np.min(actual_relaxations)):.3e}\n"
        f"Measured full residual cost = {diagnostics['full_residual_cost_s']:.1f} s\n\n"
        "New full-frequency residual: false\n"
        "Dynamic NLTE solution claimed: false",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.3,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    started = time.perf_counter()
    with np.load(ROOT / protocol["sources"]["current_material_state"]["path"]) as state_file:
        phase = int(state_file["phase_index"])
        duration = float(state_file["step_duration_s"])
        density = np.array(state_file["density_g_cm3"], copy=True)
        temperature = np.array(state_file["temperature_k"], copy=True)
        hydrogen = np.array(state_file["hydrogen_fraction"], copy=True)
        helium = np.array(state_file["helium_fraction"], copy=True)
    with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
        old_density = np.array(old["density_g_cm3"][phase], copy=True)
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
        if duration != float(old["step_duration_s"][phase]) or not np.array_equal(
            density, old_density
        ):
            raise RuntimeError("Phase 7B9a fixed physical time level changed")
    with np.load(ROOT / protocol["sources"]["current_assembled_feedback"]["path"]) as rates:
        photoionization = np.array(rates["half_photoionization_s1"], copy=True)
        recombination = np.array(rates["half_total_recombination_cm3_s"], copy=True)
        heating = np.array(rates["half_atomic_rate_heating_erg_s_cm3"], copy=True)
    candidate = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        photoionization,
        recombination,
        heating,
    )
    codec = GroundStateLogSimplexCodec(int(configuration["cell_count"]))
    encoded = np.asarray(codec.encode(temperature, hydrogen, helium))
    decoded = codec.decode(encoded)
    temperature_roundtrip = float(
        np.max(np.abs(decoded.temperature_k - temperature) / temperature)
    )
    population_roundtrip = max(
        float(np.max(np.abs(decoded.hydrogen_fraction - hydrogen))),
        float(np.max(np.abs(decoded.helium_fraction - helium))),
    )
    energy_roundtrip = float(
        np.max(
            np.abs(
                decoded.specific_material_energy_erg_g
                - state_file_energy(temperature, hydrogen, helium)
            )
            / state_file_energy(temperature, hydrogen, helium)
        )
    )
    target_state = _state_from_response(candidate)
    actual_residual_operator = EncodedMaterialFixedPointResidual(
        codec, lambda _state: target_state
    )
    actual_initial_residual = np.asarray(actual_residual_operator(encoded))
    actual_component_residual = actual_initial_residual.reshape(-1, 4)
    trust = lambda current, trial: ground_state_material_trial_within_trust_region(
        codec,
        current,
        trial,
        maximum_relative_temperature_change=float(
            configuration["maximum_relative_temperature_change_per_step"]
        ),
        maximum_absolute_material_energy_increment_fraction=float(
            configuration[
                "maximum_absolute_material_energy_increment_fraction_per_step"
            ]
        ),
        maximum_population_fraction_change=float(
            configuration["maximum_population_fraction_change_per_step"]
        ),
    )
    actual_solution = solve_matrix_free_newton_krylov(
        actual_residual_operator,
        encoded,
        residual_norm_tolerance=float(
            gates["actual_frozen_feedback_newton_residual_norm_below"]
        ),
        maximum_newton_iterations=int(configuration["maximum_newton_iterations"]),
        gmres_relative_tolerance=float(configuration["gmres_relative_tolerance"]),
        maximum_gmres_iterations=int(configuration["maximum_gmres_iterations"]),
        jacobian_relative_step=float(
            configuration["finite_difference_jacobian_relative_step"]
        ),
        armijo_coefficient=float(configuration["armijo_coefficient"]),
        maximum_backtracking_steps=int(configuration["maximum_backtracking_steps"]),
        trial_acceptance=trust,
    )
    actual_final_state = codec.decode(actual_solution.state)
    actual_temperature_difference = float(
        np.max(
            np.abs(actual_final_state.temperature_k - target_state.temperature_k)
            / target_state.temperature_k
        )
    )
    actual_population_difference = max(
        float(
            np.max(
                np.abs(
                    actual_final_state.hydrogen_fraction
                    - target_state.hydrogen_fraction
                )
            )
        ),
        float(
            np.max(
                np.abs(
                    actual_final_state.helium_fraction
                    - target_state.helium_fraction
                )
            )
        ),
    )
    # 中文：真实 7B8f 冻结场的完整候选无正热能解，必须原样记录拒绝。
    failed_candidate_rejected = False
    try:
        with np.load(
            ROOT / protocol["sources"]["failed_backtracked_feedback"]["path"]
        ) as failed_rates:
            frozen_radiation_material_response(
                density,
                old_temperature,
                old_hydrogen,
                old_helium,
                duration,
                failed_rates["half_photoionization_s1"],
                failed_rates["half_total_recombination_cm3_s"],
                failed_rates["half_atomic_rate_heating_erg_s_cm3"],
            )
    except PhysicalDomainError as error:
        failed_candidate_rejected = "no positive gas heat" in str(error)
    manufactured_size = 32
    index = np.arange(manufactured_size)
    root = 0.15 * np.sin(2.0 * np.pi * index / manufactured_size)
    matrix = 2.5 * np.eye(manufactured_size)
    matrix += -0.4 * np.roll(np.eye(manufactured_size), 1, axis=1)
    matrix += -0.35 * np.roll(np.eye(manufactured_size), -1, axis=1)
    matrix += 0.02 * np.ones((manufactured_size, manufactured_size))

    def manufactured_residual(value: np.ndarray) -> np.ndarray:
        offset = value - root
        return matrix @ offset + 0.02 * offset**3

    manufactured_solution = solve_matrix_free_newton_krylov(
        manufactured_residual,
        root + 0.4 * np.cos(4.0 * np.pi * index / manufactured_size),
        residual_norm_tolerance=float(
            gates["manufactured_nonlocal_residual_norm_below"]
        ),
        maximum_newton_iterations=12,
        gmres_relative_tolerance=float(configuration["gmres_relative_tolerance"]),
        maximum_gmres_iterations=int(configuration["maximum_gmres_iterations"]),
        jacobian_relative_step=float(
            configuration["finite_difference_jacobian_relative_step"]
        ),
        armijo_coefficient=float(configuration["armijo_coefficient"]),
        maximum_backtracking_steps=int(configuration["maximum_backtracking_steps"]),
    )
    manufactured_state_error = float(np.max(np.abs(manufactured_solution.state - root)))
    relaxations = np.concatenate(
        (
            np.asarray(actual_solution.accepted_relaxations),
            np.asarray(manufactured_solution.accepted_relaxations),
        )
    )
    with open(
        ROOT / protocol["sources"]["phase7b8f_summary"]["path"],
        encoding="utf-8",
    ) as stream:
        phase7b8f_summary = json.load(stream)
    with open(
        OUTPUT / "phase7b8e_backtracked_radiation_map_summary.json",
        encoding="utf-8",
    ) as stream:
        phase7b8e_summary = json.load(stream)
    full_residual_cost = float(phase7b8e_summary["total_wall_runtime_s"]) + float(
        phase7b8f_summary["total_wall_runtime_s"]
    )
    wall_runtime = time.perf_counter() - started
    decision = {
        "frozen_protocol_sources_and_time_base_passed": True,
        "codec_roundtrip_passed": bool(
            temperature_roundtrip
            < gates["codec_maximum_relative_temperature_roundtrip_below"]
            and population_roundtrip
            < gates["codec_maximum_population_roundtrip_below"]
            and energy_roundtrip
            < gates["codec_maximum_relative_energy_roundtrip_below"]
        ),
        "actual_four_variable_residual_valid": bool(
            np.all(np.isfinite(actual_component_residual))
        ),
        "actual_frozen_feedback_newton_passed": bool(
            actual_solution.converged
            and float(actual_solution.residual_norm_history[-1])
            < gates["actual_frozen_feedback_newton_residual_norm_below"]
            and actual_temperature_difference
            < gates["actual_frozen_feedback_maximum_temperature_difference_below"]
            and actual_population_difference
            < gates["actual_frozen_feedback_maximum_population_difference_below"]
        ),
        "failed_backtracked_candidate_physical_rejection_preserved": bool(
            failed_candidate_rejected
        ),
        "manufactured_nonlocal_newton_passed": bool(
            manufactured_solution.converged
            and float(manufactured_solution.residual_norm_history[-1])
            < gates["manufactured_nonlocal_residual_norm_below"]
            and manufactured_state_error
            < gates["manufactured_nonlocal_state_error_below"]
        ),
        "accepted_relaxations_valid": bool(
            relaxations.size > 0
            and np.all(relaxations > 0.0)
            and np.all(relaxations <= 1.0)
        ),
        "runtime_gate_passed": wall_runtime < gates["wall_time_strictly_below_s"],
        "new_full_frequency_residual_evaluated": False,
        "accepted_as_dynamic_NLTE_solution": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b9a_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_and_time_base_passed",
            "codec_roundtrip_passed",
            "actual_four_variable_residual_valid",
            "actual_frozen_feedback_newton_passed",
            "failed_backtracked_candidate_physical_rejection_preserved",
            "manufactured_nonlocal_newton_passed",
            "accepted_relaxations_valid",
            "runtime_gate_passed",
        )
    )
    decision["recoverable_full_frequency_residual_interface_design_authorized"] = bool(
        decision["phase7b9a_gate_passed"]
    )
    artifact_path = OUTPUT / "phase7b9a_newton_krylov_component.npz"
    _write_npz_atomic(
        artifact_path,
        mass_fraction_centre=0.5 * (mass_edge[:-1] + mass_edge[1:]),
        actual_initial_encoded_residual=actual_component_residual,
        actual_residual_norm_history=np.asarray(actual_solution.residual_norm_history),
        actual_accepted_relaxations=np.asarray(actual_solution.accepted_relaxations),
        manufactured_residual_norm_history=np.asarray(
            manufactured_solution.residual_norm_history
        ),
        manufactured_accepted_relaxations=np.asarray(
            manufactured_solution.accepted_relaxations
        ),
    )
    diagnostics = {
        "unknowns": float(codec.vector_size),
        "temperature_roundtrip": temperature_roundtrip,
        "population_roundtrip": population_roundtrip,
        "actual_iterations": float(actual_solution.nonlinear_iteration_count),
        "full_residual_cost_s": full_residual_cost,
    }
    figure_path = OUTPUT / "phase7b9a_newton_krylov_component.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        actual_component_residual,
        np.asarray(actual_solution.residual_norm_history),
        np.asarray(manufactured_solution.residual_norm_history),
        np.asarray(actual_solution.accepted_relaxations),
        diagnostics,
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "encoded_unknown_count": codec.vector_size,
        "codec_maximum_relative_temperature_roundtrip": temperature_roundtrip,
        "codec_maximum_population_roundtrip": population_roundtrip,
        "codec_maximum_relative_energy_roundtrip": energy_roundtrip,
        "actual_initial_maximum_component_residuals": {
            "log_thermal_energy": float(np.max(np.abs(actual_component_residual[:, 0]))),
            "log_h_ii_over_h_i": float(np.max(np.abs(actual_component_residual[:, 1]))),
            "log_he_ii_over_he_i": float(np.max(np.abs(actual_component_residual[:, 2]))),
            "log_he_iii_over_he_i": float(np.max(np.abs(actual_component_residual[:, 3]))),
        },
        "actual_frozen_feedback_newton_iterations": actual_solution.nonlinear_iteration_count,
        "actual_frozen_feedback_gmres_iterations": int(
            np.sum(actual_solution.gmres_iteration_counts)
        ),
        "actual_frozen_feedback_jv_evaluations": actual_solution.jacobian_vector_evaluation_count,
        "actual_frozen_feedback_final_residual_norm": float(
            actual_solution.residual_norm_history[-1]
        ),
        "actual_frozen_feedback_minimum_relaxation": float(
            np.min(actual_solution.accepted_relaxations)
        ),
        "actual_frozen_feedback_maximum_temperature_difference": actual_temperature_difference,
        "actual_frozen_feedback_maximum_population_difference": actual_population_difference,
        "failed_backtracked_candidate_physical_rejection_preserved": failed_candidate_rejected,
        "manufactured_nonlocal_newton_iterations": manufactured_solution.nonlinear_iteration_count,
        "manufactured_nonlocal_jv_evaluations": manufactured_solution.jacobian_vector_evaluation_count,
        "manufactured_nonlocal_final_residual_norm": float(
            manufactured_solution.residual_norm_history[-1]
        ),
        "manufactured_nonlocal_maximum_state_error": manufactured_state_error,
        "measured_one_full_frequency_residual_evaluation_cost_s": full_residual_cost,
        "wall_runtime_s": wall_runtime,
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "artifact_sha256": _sha256(artifact_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b9a_newton_krylov_component_summary.json", report)
    return report


def state_file_energy(
    temperature: np.ndarray,
    hydrogen: np.ndarray,
    helium: np.ndarray,
) -> np.ndarray:
    from eccentric_tde_observer.radiation_matter_feedback import (
        ground_state_material_specific_energy_erg_g,
    )

    return np.asarray(
        ground_state_material_specific_energy_erg_g(
            temperature, hydrogen, helium
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9a_preregistered_newton_krylov_component.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
