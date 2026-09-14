"""Phase 7B9de：按冻结编码方向构造一个 0.0625 物质候选。"""

from __future__ import annotations

import argparse
import hashlib
import json
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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "outputs/phase7b9de_preregistered_half_trial_material.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(path.stem + ".tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def validate_sources(protocol: dict[str, object]) -> None:
    for row in protocol["sources"].values():
        path = ROOT / row["path"]
        if path.stat().st_size != int(row["size_bytes"]) or sha256(path) != row["sha256"]:
            raise RuntimeError(f"frozen source changed: {row['path']}")


def run(protocol_path: Path, expected_protocol_sha256: str) -> dict[str, object]:
    if sha256(protocol_path) != expected_protocol_sha256:
        raise RuntimeError("Phase 7B9de protocol hash changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_sources(protocol)
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    with np.load(ROOT / protocol["sources"]["base_material"]["path"]) as base:
        phase = int(base["phase_index"])
        duration = float(base["step_duration_s"])
        density = np.array(base["density_g_cm3"], copy=True)
        temperature = np.array(base["temperature_k"], copy=True)
        hydrogen = np.array(base["hydrogen_fraction"], copy=True)
        helium = np.array(base["helium_fraction"], copy=True)
    with np.load(ROOT / protocol["sources"]["phase7b9g_direction"]["path"]) as artifact:
        direction = np.array(artifact["preconditioned_direction"], copy=True)
        base_residual = np.array(artifact["final_residual"], copy=True)
    with np.load(ROOT / protocol["sources"]["phase7b9i_trial"]["path"]) as failed:
        if (
            float(failed["relaxation"]) != float(cfg["failed_absolute_relaxation"])
            or not np.array_equal(direction, failed["finite_direction"])
        ):
            raise RuntimeError("failed material-trial direction changed")
    with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
        if (
            duration != float(old["step_duration_s"][phase])
            or not np.array_equal(density, old["density_g_cm3"][phase])
        ):
            raise RuntimeError("fixed physical time level changed")
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)

    codec = GroundStateLogSimplexCodec(temperature.size)
    encoded_base = np.asarray(codec.encode(temperature, hydrogen, helium))
    relaxation = float(cfg["candidate_absolute_relaxation"])
    encoded_candidate = encoded_base + relaxation * direction
    trust_passed = ground_state_material_trial_within_trust_region(
        codec,
        encoded_base,
        encoded_candidate,
        maximum_relative_temperature_change=float(
            gates["maximum_relative_temperature_change"]
        ),
        maximum_absolute_material_energy_increment_fraction=float(
            gates["maximum_absolute_material_energy_increment_fraction"]
        ),
        maximum_population_fraction_change=float(
            gates["maximum_population_fraction_change"]
        ),
    )
    base_state = codec.decode(encoded_base)
    candidate = codec.decode(encoded_candidate)
    relative_temperature_change = float(
        np.max(
            np.abs(candidate.temperature_k - base_state.temperature_k)
            / base_state.temperature_k
        )
    )
    relative_energy_change = float(
        np.max(
            np.abs(
                candidate.specific_material_energy_erg_g
                - base_state.specific_material_energy_erg_g
            )
            / base_state.specific_material_energy_erg_g
        )
    )
    population_change = max(
        float(np.max(np.abs(candidate.hydrogen_fraction - hydrogen))),
        float(np.max(np.abs(candidate.helium_fraction - helium))),
    )
    finite = all(
        np.all(np.isfinite(array))
        for array in (
            candidate.temperature_k,
            candidate.specific_material_energy_erg_g,
            candidate.hydrogen_fraction,
            candidate.helium_fraction,
        )
    )
    gate_checks = {
        "trust_region_pass": bool(trust_passed),
        "temperature_positive_pass": bool(np.all(candidate.temperature_k > 0.0)),
        "specific_material_energy_positive_pass": bool(
            np.all(candidate.specific_material_energy_erg_g > 0.0)
        ),
        "population_nonnegative_pass": bool(
            np.all(candidate.hydrogen_fraction >= 0.0)
            and np.all(candidate.helium_fraction >= 0.0)
        ),
        "hydrogen_simplex_pass": bool(
            np.max(np.abs(np.sum(candidate.hydrogen_fraction, axis=1) - 1.0))
            < float(gates["maximum_simplex_closure_absolute_error_below"])
        ),
        "helium_simplex_pass": bool(
            np.max(np.abs(np.sum(candidate.helium_fraction, axis=1) - 1.0))
            < float(gates["maximum_simplex_closure_absolute_error_below"])
        ),
        "all_arrays_finite_pass": finite,
        "encoded_definition_pass": bool(
            np.array_equal(encoded_candidate, encoded_base + relaxation * direction)
        ),
    }
    all_passed = all(gate_checks.values())
    if not all_passed:
        raise RuntimeError("Phase 7B9de half-trial material gates failed")

    candidate_path = ROOT / cfg["candidate_output"]
    write_npz_atomic(
        candidate_path,
        phase_index=np.array(phase),
        step_duration_s=np.array(duration),
        density_g_cm3=density,
        temperature_k=candidate.temperature_k,
        hydrogen_fraction=candidate.hydrogen_fraction,
        helium_fraction=candidate.helium_fraction,
        specific_material_energy_erg_g=candidate.specific_material_energy_erg_g,
        encoded_state=encoded_candidate,
        base_encoded_state=encoded_base,
        finite_direction=direction,
        base_residual=base_residual,
        relaxation=np.array(relaxation),
    )
    mass_centre = 0.5 * (mass_edge[:-1] + mass_edge[1:])
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.3), constrained_layout=True)
    axes[0].semilogy(mass_centre, temperature, label="Base")
    axes[0].semilogy(mass_centre, candidate.temperature_k, ls="--", label="Half trial")
    axes[0].set(
        xlabel="Mass fraction from surface",
        ylabel="Temperature (K)",
        title="(a) First dyadic material backtrack",
    )
    axes[0].legend(frameon=False)
    axes[1].axhline(0.0, color="0.7", lw=1.0)
    axes[1].plot(
        mass_centre,
        1.0e6 * (candidate.hydrogen_fraction[:, 1] - hydrogen[:, 1]),
        label="Half trial - base",
    )
    axes[1].set(
        xlabel="Mass fraction from surface",
        ylabel=r"H II fraction change ($10^{-6}$)",
        title="(b) Resolved population displacement",
    )
    axes[1].legend(frameon=False)
    axes[2].axis("off")
    axes[2].text(
        0.03,
        0.95,
        "(c) Frozen candidate gate\n\n"
        f"Absolute relaxation = {relaxation:.4f}\n"
        f"Maximum temperature change = {relative_temperature_change:.3e}\n"
        f"Maximum material-energy change = {relative_energy_change:.3e}\n"
        f"Maximum population change = {population_change:.3e}\n\n"
        "Radiation and formal feedback not evaluated.\n"
        "No clipping, floor, or renormalization.",
        transform=axes[2].transAxes,
        va="top",
        fontsize=10.0,
    )
    figure_path = ROOT / cfg["figure_output"]
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    report = {
        "phase": "7B9de first dyadic material backtrack candidate",
        "classification": "[A-preregistered]+[V-material-domain]+[O]",
        "protocol_sha256": expected_protocol_sha256,
        "candidate_absolute_relaxation": relaxation,
        "maximum_relative_temperature_change": relative_temperature_change,
        "maximum_relative_material_energy_change": relative_energy_change,
        "maximum_population_fraction_change": population_change,
        "encoded_candidate_displacement_l2": float(
            np.linalg.norm(encoded_candidate - encoded_base)
        ),
        "candidate_path": str(candidate_path.relative_to(ROOT)),
        "candidate_sha256": sha256(candidate_path),
        "gate_checks": gate_checks,
        "decision": {
            "material_candidate_gate_passed": all_passed,
            "candidate_full_frequency_radiation_authorized": all_passed,
            "candidate_radiation_evaluated": False,
            "candidate_formal_feedback_evaluated": False,
            "candidate_accepted_as_nonlinear_step": False,
            "static_approximation_rejected": False,
            "dynamic_nlte_solution_accepted": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
        "figures": [figure_path.name],
    }
    write_json_atomic(ROOT / cfg["summary_output"], report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.protocol, args.expected_protocol_sha256), indent=2))


if __name__ == "__main__":
    main()
