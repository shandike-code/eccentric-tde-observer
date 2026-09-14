"""Phase 7B8d：由两个全频反馈端点选择受保护回溯物质态。"""

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

from eccentric_tde_observer.coupled_material_line_search import (
    protected_residual_line_search_material_step,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    ground_state_material_specific_energy_erg_g,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "8443043bdf3c51279ad6d29ed4ff7b5113fff8575096bf2ed82174ee938b8399"
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
        raise RuntimeError(f"frozen Phase 7B8d protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B8d source changed: {source['path']}")
    return protocol


def _signed_residual(
    old_energy: np.ndarray,
    state_energy: np.ndarray,
    duration: float,
    heating: np.ndarray,
    density: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    increment = duration * heating / density
    residual = state_energy - old_energy - increment
    scale = np.maximum.reduce((np.abs(state_energy), np.abs(old_energy), np.abs(increment)))
    if np.any(scale <= 0.0):
        raise ArithmeticError("Phase 7B8d residual scale is non-positive")
    return residual, scale


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    current_temperature: np.ndarray,
    endpoint_temperature: np.ndarray,
    selected_temperature: np.ndarray,
    current_relative: np.ndarray,
    endpoint_relative: np.ndarray,
    predicted_relative: np.ndarray,
    candidates: np.ndarray,
    candidate_weighted: np.ndarray,
    selected_relaxation: float,
    diagnostics: dict[str, float],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].semilogy(mass_centre, current_temperature, label="Second Picard iterate")
    axes[0, 0].semilogy(mass_centre, endpoint_temperature, label="Rejected full secant endpoint")
    axes[0, 0].semilogy(mass_centre, selected_temperature, ls="--", label="Selected backtracked trial")
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Temperature (K)",
        title="(a) Feedback-informed material backtracking",
    )
    axes[0, 0].legend(frameon=False, fontsize=9)
    axes[0, 1].semilogy(mass_centre, current_relative, label="Current true residual")
    axes[0, 1].semilogy(mass_centre, endpoint_relative, label="Rejected endpoint true residual")
    axes[0, 1].semilogy(mass_centre, predicted_relative, ls="--", label="Affine prediction at selected step")
    axes[0, 1].axhline(1.0e-3, color="0.25", ls=":", label="Fixed-point target")
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Cellwise fixed-time-level residual",
        title="(b) Endpoint-informed residual prediction",
    )
    axes[0, 1].legend(frameon=False, fontsize=9)
    axes[1, 0].plot(candidates, candidate_weighted, marker="o")
    axes[1, 0].axvline(selected_relaxation, color="C3", ls="--", label="Selected step")
    axes[1, 0].set(
        xlabel="Backtracking relaxation",
        ylabel="Affine-predicted mass-weighted residual",
        title="(c) Preregistered discrete candidates",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.05,
        0.92,
        "(d) Prediction and scope\n\n"
        f"Selected relaxation = {selected_relaxation:.6f}\n"
        f"Predicted weighted contraction = {diagnostics['weighted']:.6f}\n"
        f"Predicted limiting-cell contraction = {diagnostics['limiting']:.6f}\n"
        f"Predicted maximum-cell contraction = {diagnostics['maximum']:.6f}\n\n"
        "New radiation map performed: false\n"
        "Coupled fixed point claimed: false",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=11,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    started = time.perf_counter()
    with np.load(ROOT / protocol["sources"]["current_material_iterate"]["path"]) as current:
        phase = int(current["phase_index"])
        duration = float(current["step_duration_s"])
        density = np.array(current["density_g_cm3"], copy=True)
        current_temperature = np.array(current["temperature_k"], copy=True)
        current_hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        current_helium = np.array(current["helium_fraction"], copy=True)
    with np.load(ROOT / protocol["sources"]["secant_material_endpoint"]["path"]) as endpoint:
        if (
            int(endpoint["phase_index"]) != phase
            or float(endpoint["step_duration_s"]) != duration
            or not np.array_equal(endpoint["density_g_cm3"], density)
        ):
            raise RuntimeError("Phase 7B8d endpoint time base changed")
        endpoint_temperature = np.array(endpoint["temperature_k"], copy=True)
        endpoint_hydrogen = np.array(endpoint["hydrogen_fraction"], copy=True)
        endpoint_helium = np.array(endpoint["helium_fraction"], copy=True)
    with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
        old_energy = np.asarray(
            ground_state_material_specific_energy_erg_g(
                old["temperature_k"][phase],
                old["hydrogen_fraction"][phase],
                old["helium_fraction"][phase],
            )
        )
        cell_mass = np.array(old["cell_mass_g_cm2"], copy=True)
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
        if duration != float(old["step_duration_s"][phase]):
            raise RuntimeError("Phase 7B8d physical duration changed")
    current_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            current_temperature, current_hydrogen, current_helium
        )
    )
    endpoint_energy = np.asarray(
        ground_state_material_specific_energy_erg_g(
            endpoint_temperature, endpoint_hydrogen, endpoint_helium
        )
    )
    with np.load(ROOT / protocol["sources"]["current_assembled_feedback"]["path"]) as rates:
        current_heating = np.array(rates["parent_atomic_rate_heating_erg_s_cm3"][:128], copy=True)
    with np.load(ROOT / protocol["sources"]["secant_assembled_feedback"]["path"]) as rates:
        endpoint_heating = np.array(rates["parent_atomic_rate_heating_erg_s_cm3"][:128], copy=True)
    current_residual, current_scale = _signed_residual(
        old_energy, current_energy, duration, current_heating, density
    )
    endpoint_residual, endpoint_scale = _signed_residual(
        old_energy, endpoint_energy, duration, endpoint_heating, density
    )
    candidates = tuple(float(value) for value in configuration["candidate_relaxations"])
    step = protected_residual_line_search_material_step(
        current_temperature,
        current_hydrogen,
        current_helium,
        endpoint_temperature,
        endpoint_hydrogen,
        endpoint_helium,
        current_residual,
        endpoint_residual,
        current_scale,
        endpoint_scale,
        cell_mass,
        candidate_relaxations=candidates,
        maximum_predicted_mass_weighted_contraction=float(
            gates["maximum_predicted_mass_weighted_contraction_below"]
        ),
        maximum_predicted_limiting_cell_contraction=float(
            gates["maximum_predicted_limiting_cell_contraction_below"]
        ),
        maximum_predicted_maximum_cell_contraction=float(
            gates["maximum_predicted_maximum_cell_contraction_below"]
        ),
    )
    temperature_change = float(
        np.max(np.abs(step.temperature_k - current_temperature) / current_temperature)
    )
    energy_change = float(
        np.max(np.abs(step.specific_material_energy_erg_g - current_energy) / current_energy)
    )
    population_change = max(
        float(np.max(np.abs(step.hydrogen_fraction - current_hydrogen))),
        float(np.max(np.abs(step.helium_fraction - current_helium))),
    )
    wall_runtime = time.perf_counter() - started
    decision = {
        "frozen_protocol_sources_and_time_base_passed": True,
        "affine_residual_prediction_gates_passed": bool(
            current_temperature.size == gates["cell_count_exactly"]
            and step.predicted_mass_weighted_contraction
            < gates["maximum_predicted_mass_weighted_contraction_below"]
            and step.predicted_limiting_cell_contraction
            < gates["maximum_predicted_limiting_cell_contraction_below"]
            and step.predicted_maximum_cell_contraction
            < gates["maximum_predicted_maximum_cell_contraction_below"]
        ),
        "material_domain_and_conservation_passed": bool(
            temperature_change <= gates["maximum_relative_temperature_change_at_most"]
            and energy_change
            <= gates["maximum_absolute_material_energy_increment_fraction_at_most"]
            and population_change <= gates["maximum_population_fraction_change_at_most"]
            and step.maximum_relative_energy_residual
            < gates["maximum_relative_energy_residual_below"]
            and step.maximum_particle_conservation_residual
            < gates["maximum_particle_conservation_residual_below"]
            and step.minimum_population_fraction
            >= gates["minimum_population_fraction_at_least"]
        ),
        "runtime_gate_passed": wall_runtime < gates["wall_time_strictly_below_s"],
        "physical_step_duration_changed": False,
        "physical_step_accumulated_again": False,
        "radiation_validation_map_performed": False,
        "accepted_as_coupled_fixed_point": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b8d_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_sources_and_time_base_passed",
            "affine_residual_prediction_gates_passed",
            "material_domain_and_conservation_passed",
            "runtime_gate_passed",
        )
    )
    decision["one_full_frequency_radiation_validation_map_authorized"] = bool(
        decision["phase7b8d_gate_passed"]
    )
    state_path = OUTPUT / "phase7b8d_feedback_line_search_material_trial.npz"
    _write_npz_atomic(
        state_path,
        phase_index=np.array(phase),
        nonlinear_iteration_index=np.array(3),
        step_duration_s=np.array(duration),
        physical_step_duration_changed=np.array(False),
        physical_step_accumulated_again=np.array(False),
        solver_method=np.array("protected feedback-informed residual line search"),
        solver_relaxation=np.array(step.relaxation),
        density_g_cm3=density,
        temperature_k=np.asarray(step.temperature_k),
        hydrogen_fraction=np.asarray(step.hydrogen_fraction),
        helium_fraction=np.asarray(step.helium_fraction),
        specific_material_energy_erg_g=np.asarray(step.specific_material_energy_erg_g),
        predicted_signed_residual_erg_g=np.asarray(step.predicted_signed_residual_erg_g),
        predicted_residual_scale_erg_g=np.asarray(step.predicted_residual_scale_erg_g),
    )
    current_relative = np.abs(current_residual) / current_scale
    endpoint_relative = np.abs(endpoint_residual) / endpoint_scale
    predicted_relative = np.abs(step.predicted_signed_residual_erg_g) / step.predicted_residual_scale_erg_g
    candidate_weighted = []
    for relaxation in candidates:
        residual = current_residual + relaxation * (endpoint_residual - current_residual)
        scale = current_scale + relaxation * (endpoint_scale - current_scale)
        candidate_weighted.append(
            float(np.sum(cell_mass * np.abs(residual))) / float(np.sum(cell_mass * scale))
        )
    figure_path = OUTPUT / "phase7b8d_feedback_line_search.png"
    diagnostics = {
        "weighted": step.predicted_mass_weighted_contraction,
        "limiting": step.predicted_limiting_cell_contraction,
        "maximum": step.predicted_maximum_cell_contraction,
    }
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        current_temperature,
        endpoint_temperature,
        np.asarray(step.temperature_k),
        current_relative,
        endpoint_relative,
        predicted_relative,
        np.asarray(candidates),
        np.asarray(candidate_weighted),
        step.relaxation,
        diagnostics,
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "physical_step_duration_s": duration,
        "candidate_relaxations": list(candidates),
        "selected_relaxation": step.relaxation,
        "current_mass_weighted_fixed_point_residual": step.current_mass_weighted_residual,
        "predicted_mass_weighted_fixed_point_residual": step.predicted_mass_weighted_residual,
        "predicted_mass_weighted_contraction_fraction": step.predicted_mass_weighted_contraction,
        "current_maximum_cell_fixed_point_residual": step.current_maximum_cell_residual,
        "predicted_maximum_cell_fixed_point_residual": step.predicted_maximum_cell_residual,
        "predicted_maximum_cell_contraction_fraction": step.predicted_maximum_cell_contraction,
        "current_limiting_cell": step.current_limiting_cell,
        "predicted_limiting_cell_contraction_fraction": step.predicted_limiting_cell_contraction,
        "maximum_relative_temperature_change": temperature_change,
        "maximum_absolute_material_energy_increment_fraction": energy_change,
        "maximum_population_fraction_change": population_change,
        "maximum_relative_material_energy_residual": step.maximum_relative_energy_residual,
        "maximum_particle_conservation_residual": step.maximum_particle_conservation_residual,
        "minimum_population_fraction": step.minimum_population_fraction,
        "wall_runtime_s": wall_runtime,
        "state_path": str(state_path.relative_to(ROOT)),
        "state_sha256": _sha256(state_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b8d_feedback_line_search_summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b8d_preregistered_feedback_line_search.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
