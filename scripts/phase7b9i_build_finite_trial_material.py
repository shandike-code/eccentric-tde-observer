"""Phase 7B9i：构造不冒充 Jv 的 0.125 有限准 Newton 物质试步。"""

from __future__ import annotations

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


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def run() -> dict[str, object]:
    decision_path = OUTPUT / "phase7b9g_jv_fidelity_decision_summary.json"
    direction_path = OUTPUT / "phase7b9g_jv_fidelity_decision.npz"
    current_path = OUTPUT / "phase7b7h_second_material_iterate.npz"
    old_path = OUTPUT / "phase7b4r_depth128_phase2048.npz"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if (
        decision["decision"]["finite_protected_quasi_newton_trial_authorized"]
        is not True
        or decision["decision"]["finite_trial_may_be_called_jv"] is not False
        or float(decision["largest_physical_trust_relaxation"]) != 0.125
    ):
        raise RuntimeError("Phase 7B9i requires the passed finite-trial decision")
    with np.load(current_path) as current:
        phase = int(current["phase_index"])
        duration = float(current["step_duration_s"])
        density = np.array(current["density_g_cm3"], copy=True)
        temperature = np.array(current["temperature_k"], copy=True)
        hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        helium = np.array(current["helium_fraction"], copy=True)
    with np.load(old_path) as old:
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
        if (
            duration != float(old["step_duration_s"][phase])
            or not np.array_equal(density, old["density_g_cm3"][phase])
        ):
            raise RuntimeError("Phase 7B9i fixed physical time level changed")
    with np.load(direction_path) as artifact:
        direction = np.array(artifact["preconditioned_direction"], copy=True)
        base_residual = np.array(artifact["final_residual"], copy=True)
    codec = GroundStateLogSimplexCodec(128)
    encoded_current = np.asarray(codec.encode(temperature, hydrogen, helium))
    relaxation = 0.125
    encoded_trial = encoded_current + relaxation * direction
    trust_passed = ground_state_material_trial_within_trust_region(
        codec,
        encoded_current,
        encoded_trial,
        maximum_relative_temperature_change=0.5,
        maximum_absolute_material_energy_increment_fraction=0.25,
        maximum_population_fraction_change=0.05,
    )
    if not trust_passed:
        raise RuntimeError("Phase 7B9i frozen finite trial left the trust region")
    current_state = codec.decode(encoded_current)
    trial_state = codec.decode(encoded_trial)
    temperature_change = float(
        np.max(
            np.abs(trial_state.temperature_k - current_state.temperature_k)
            / current_state.temperature_k
        )
    )
    energy_change = float(
        np.max(
            np.abs(
                trial_state.specific_material_energy_erg_g
                - current_state.specific_material_energy_erg_g
            )
            / current_state.specific_material_energy_erg_g
        )
    )
    population_change = max(
        float(
            np.max(
                np.abs(
                    trial_state.hydrogen_fraction
                    - current_state.hydrogen_fraction
                )
            )
        ),
        float(
            np.max(
                np.abs(trial_state.helium_fraction - current_state.helium_fraction)
            )
        ),
    )
    trial_path = OUTPUT / "phase7b9i_finite_trial_material_state.npz"
    _write_npz_atomic(
        trial_path,
        phase_index=np.array(phase),
        step_duration_s=np.array(duration),
        density_g_cm3=density,
        temperature_k=trial_state.temperature_k,
        hydrogen_fraction=trial_state.hydrogen_fraction,
        helium_fraction=trial_state.helium_fraction,
        specific_material_energy_erg_g=trial_state.specific_material_energy_erg_g,
        encoded_state=encoded_trial,
        base_encoded_state=encoded_current,
        finite_direction=direction,
        base_residual=base_residual,
        relaxation=np.array(relaxation),
    )
    mass_centre = 0.5 * (mass_edge[:-1] + mass_edge[1:])
    figure, axes = plt.subplots(1, 3, figsize=(13.0, 4.3), constrained_layout=True)
    axes[0].semilogy(mass_centre, temperature, label="Base")
    axes[0].semilogy(mass_centre, trial_state.temperature_k, ls="--", label="Trial")
    axes[0].set(
        xlabel="Mass fraction from surface",
        ylabel="Temperature (K)",
        title="(a) Finite quasi-Newton temperature trial",
    )
    axes[0].legend(frameon=False)
    axes[1].plot(mass_centre, hydrogen[:, 1], label="Base H II")
    axes[1].plot(
        mass_centre, trial_state.hydrogen_fraction[:, 1], ls="--", label="Trial H II"
    )
    axes[1].set(
        xlabel="Mass fraction from surface",
        ylabel="Ion fraction",
        title="(b) Hydrogen population response",
    )
    axes[1].legend(frameon=False)
    axes[2].axis("off")
    axes[2].text(
        0.03,
        0.95,
        "(c) Frozen trial and trust region\n\n"
        f"Finite relaxation = {relaxation:.3f}\n"
        f"Maximum temperature change = {temperature_change:.3e}\n"
        f"Maximum material-energy change = {energy_change:.3e}\n"
        f"Maximum population change = {population_change:.3e}\n\n"
        "This is a finite residual trial, not a Jv.\n"
        "No clipping, floor, or renormalization.",
        transform=axes[2].transAxes,
        va="top",
        fontsize=10.0,
    )
    figure_path = OUTPUT / "phase7b9i_finite_trial_material.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    report = {
        "phase": "7B9i finite protected quasi-Newton material trial",
        "classification": "[A-preregistered-by-7B9g]+[V]+[O]",
        "sources": {
            "phase7b9g_decision": {
                "path": str(decision_path.relative_to(ROOT)),
                "sha256": _sha256(decision_path),
            },
            "phase7b9g_direction": {
                "path": str(direction_path.relative_to(ROOT)),
                "sha256": _sha256(direction_path),
            },
            "current_material": {
                "path": str(current_path.relative_to(ROOT)),
                "sha256": _sha256(current_path),
            },
        },
        "relaxation": relaxation,
        "maximum_relative_temperature_change": temperature_change,
        "maximum_relative_material_energy_change": energy_change,
        "maximum_population_fraction_change": population_change,
        "encoded_trial_displacement_l2": float(
            np.linalg.norm(encoded_trial - encoded_current)
        ),
        "trial_material_path": str(trial_path.relative_to(ROOT)),
        "trial_material_sha256": _sha256(trial_path),
        "decision": {
            "physical_trust_region_passed": trust_passed,
            "finite_trial_may_be_called_jv": False,
            "trial_radiation_evaluated": False,
            "trial_true_residual_evaluated": False,
            "accepted_as_nonlinear_step": False,
            "phase7b9i_material_gate_passed": trust_passed,
            "trial_full_frequency_radiation_authorized": trust_passed,
        },
        "figures": [figure_path.name],
    }
    summary_path = OUTPUT / "phase7b9i_finite_trial_material_summary.json"
    _write_json_atomic(summary_path, report)
    return report


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
