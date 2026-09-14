"""Phase 7B7c：定位冻结辐射物质响应越出信赖域的时间与深度。"""

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

from eccentric_tde_observer.radiation_matter_feedback import (
    ground_state_material_specific_energy_erg_g,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "338e514cf65b6e4677c5f9225b07c68b468733bcf5e7e08ea92e1c36d2e523c6"
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


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B7c protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B7c source changed: {source['path']}")
    return protocol


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    response_time: np.ndarray,
    duration: float,
    energy_fraction: np.ndarray,
    cumulative_mass: np.ndarray,
    cumulative_power: np.ndarray,
    absorbed: np.ndarray,
    emitted: np.ndarray,
    heating: np.ndarray,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.2), constrained_layout=True)
    axes[0, 0].semilogy(mass_centre, response_time, color="#4c78a8")
    axes[0, 0].axhline(duration, color="0.25", ls="--", label="Actual phase step")
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Ten-percent material-energy time (s)",
        title="(a) Local response time",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(mass_centre, energy_fraction, color="#e45756")
    axes[0, 1].axhline(0.1, color="0.25", ls="--", label="Trust bound")
    axes[0, 1].axhline(-0.1, color="0.25", ls="--")
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Full-step energy increment fraction",
        title="(b) Depth of trust-region failure",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].plot(mass_centre, cumulative_power, label="Absolute net heating")
    axes[1, 0].plot(mass_centre, cumulative_mass, ls="--", label="Column mass")
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Cumulative fraction",
        title="(c) Surface concentration of feedback",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].semilogy(mass_centre, absorbed, label="Absorbed power")
    axes[1, 1].semilogy(mass_centre, emitted, ls="--", label="Emitted power")
    axes[1, 1].semilogy(mass_centre, np.abs(heating), ls=":", label="|Net heating|")
    axes[1, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Power density (erg s$^{-1}$ cm$^{-3}$)",
        title="(d) Absorption-emission cancellation",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    started = time.perf_counter()
    with np.load(ROOT / protocol["sources"]["feedback_coefficients"]["path"]) as coefficient:
        phase = int(coefficient["phase_index"])
        duration = float(coefficient["step_duration_s"])
        absorbed = np.array(coefficient["half_absorbed_power_erg_s_cm3"], copy=True)
        emitted = np.array(coefficient["half_emitted_power_erg_s_cm3"], copy=True)
        heating = np.array(
            coefficient["half_rate_material_heating_erg_s_cm3"], copy=True
        )
    with np.load(ROOT / protocol["sources"]["phase7b4r_material"]["path"]) as material:
        density = np.array(material["density_g_cm3"][phase], copy=True)
        temperature = np.array(material["temperature_k"][phase], copy=True)
        hydrogen = np.array(material["hydrogen_fraction"][phase], copy=True)
        helium = np.array(material["helium_fraction"][phase], copy=True)
        cell_mass = np.array(material["cell_mass_g_cm2"], copy=True)
        mass_edge = np.array(material["mass_fraction_edges"], copy=True)
    initial_energy = ground_state_material_specific_energy_erg_g(
        temperature, hydrogen, helium
    )
    response_fraction = float(protocol["configuration"]["response_fraction"])
    nonzero = np.abs(heating) > 0.0
    response_time = np.full(heating.shape, np.inf)
    response_time[nonzero] = (
        response_fraction
        * initial_energy[nonzero]
        * density[nonzero]
        / np.abs(heating[nonzero])
    )
    energy_fraction = duration * heating / (density * initial_energy)
    cell_volume_per_area = cell_mass / density
    absolute_power = np.abs(heating) * cell_volume_per_area
    absolute_power_cumulative = np.cumsum(absolute_power)
    mass_cumulative = np.cumsum(cell_mass)
    # 中文：累计分数的分母采用同一累计序列末值，避免不同求和次序造成 1+ulp。
    cumulative_power = absolute_power_cumulative / absolute_power_cumulative[-1]
    cumulative_mass = mass_cumulative / mass_cumulative[-1]
    mass_centre = 0.5 * (mass_edge[:-1] + mass_edge[1:])
    heating_identity_residual = float(
        np.max(np.abs(heating - (absorbed - emitted)))
        / max(float(np.max(absorbed)), float(np.max(emitted)))
    )
    maximum_energy_fraction = float(np.max(np.abs(energy_fraction)))
    minimum_response_time = float(np.min(response_time))
    upstream = json.loads(
        (OUTPUT / "phase7b7b_material_response_summary.json").read_text(
            encoding="utf-8"
        )
    )
    reproduced_energy_error = abs(
        maximum_energy_fraction
        - upstream["maximum_absolute_local_material_energy_increment_fraction"]
    ) / upstream["maximum_absolute_local_material_energy_increment_fraction"]
    reproduced_time_error = abs(
        minimum_response_time
        - upstream["ten_percent_material_energy_response_time_s"]
    ) / upstream["ten_percent_material_energy_response_time_s"]
    integrated_absorbed = float(np.sum(absorbed * cell_volume_per_area))
    integrated_emitted = float(np.sum(emitted * cell_volume_per_area))
    integrated_net = float(np.sum(heating * cell_volume_per_area))
    net_cancellation_fraction = abs(integrated_net) / max(
        abs(integrated_absorbed), abs(integrated_emitted)
    )
    rapid = response_time < duration
    very_rapid = response_time < duration / 10.0
    gates = protocol["gates"]
    wall_runtime = time.perf_counter() - started
    decision = {
        "frozen_protocol_and_source_hashes_passed": True,
        "heating_identity_passed": heating_identity_residual
        < gates[
            "heating_equals_absorbed_minus_emitted_global_scaled_residual_below"
        ],
        "failed_response_metrics_reproduced": bool(
            reproduced_energy_error
            < gates[
                "reproduced_maximum_energy_increment_fraction_relative_error_below"
            ]
            and reproduced_time_error
            < gates["reproduced_ten_percent_time_relative_error_below"]
        ),
        "timescale_and_fraction_arrays_valid": bool(
            np.all(np.isfinite(response_time[nonzero]))
            and np.all(response_time[nonzero] > 0.0)
            and np.all((cumulative_power >= 0.0) & (cumulative_power <= 1.0))
            and np.all((cumulative_mass >= 0.0) & (cumulative_mass <= 1.0))
        ),
        "runtime_gate_passed": wall_runtime < gates["wall_time_strictly_below_s"],
        "shortened_frozen_radiation_update_authorized": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b7c_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_and_source_hashes_passed",
            "heating_identity_passed",
            "failed_response_metrics_reproduced",
            "timescale_and_fraction_arrays_valid",
            "runtime_gate_passed",
        )
    )
    decision["one_trust_region_coupled_pilot_design_authorized"] = bool(
        decision["phase7b7c_gate_passed"]
    )
    figure_path = OUTPUT / "phase7b7c_timescale_diagnosis.png"
    _plot(
        figure_path,
        mass_centre,
        response_time,
        duration,
        energy_fraction,
        cumulative_mass,
        cumulative_power,
        absorbed,
        emitted,
        heating,
    )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "actual_step_duration_s": duration,
        "minimum_ten_percent_material_energy_response_time_s": minimum_response_time,
        "limiting_half_column_cell": int(np.argmin(response_time)),
        "limiting_mass_fraction_from_surface": float(
            mass_centre[np.argmin(response_time)]
        ),
        "minimum_energy_trust_substep_count_lower_bound": int(
            np.ceil(duration / minimum_response_time)
        ),
        "mass_fraction_with_ten_percent_response_faster_than_phase_step": float(
            np.sum(cell_mass[rapid]) / np.sum(cell_mass)
        ),
        "mass_fraction_with_ten_percent_response_faster_than_one_tenth_phase_step": float(
            np.sum(cell_mass[very_rapid]) / np.sum(cell_mass)
        ),
        "heating_identity_global_scaled_residual": heating_identity_residual,
        "integrated_absorbed_power_erg_s_cm2": integrated_absorbed,
        "integrated_emitted_power_erg_s_cm2": integrated_emitted,
        "integrated_net_material_heating_erg_s_cm2": integrated_net,
        "net_heating_to_absorbed_or_emitted_fraction": net_cancellation_fraction,
        "maximum_energy_fraction_reproduction_relative_error": reproduced_energy_error,
        "minimum_response_time_reproduction_relative_error": reproduced_time_error,
        "wall_runtime_s": wall_runtime,
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b7c_timescale_diagnosis_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b7c_preregistered_timescale_diagnosis.json",
    )
    args = parser.parse_args()
    summary = run(args.protocol)
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
