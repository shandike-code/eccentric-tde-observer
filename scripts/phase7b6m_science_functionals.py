"""Phase 7B6m：只读审计第 13--14 次全频状态的科学泛函变化。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.atomic_continuum import EV_ERG
from eccentric_tde_observer.multiresolution_frequency import (
    _rate_coefficient_per_group,
)
from eccentric_tde_observer.atomic_continuum import (
    H_HE_GROUND_STATE_PHOTOIONIZATION_FITS,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S, PLANCK_ERG_S
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)

try:
    from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
    from scripts.phase7b6b_relaxed_fixed_point import _write_json_atomic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b5p_isolated_resource_profile import (  # type: ignore[no-redef]
        ru_maxrss_to_bytes,
    )
    from phase7b6b_relaxed_fixed_point import (  # type: ignore[no-redef]
        _write_json_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "a55666d0b4efe0c82516e1301bf14610697b39701e3bbf5bd522e407c9df0339"
)
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B6m protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B6m source changed: {source['path']}")
    return protocol


def _relative_change(first: float, second: float) -> float:
    scale = max(abs(first), abs(second))
    return abs(second - first) / scale if scale > 0.0 else abs(second - first)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    retained = protocol["retained_arrays"]
    configuration = protocol["configuration"]
    shape = tuple(int(value) for value in retained["shape"])
    state_path = ROOT / retained["iteration14_state"]["path"]
    residual_path = ROOT / retained["iteration13_residual"]["path"]
    expected_size = int(retained["size_bytes_each"])
    if state_path.stat().st_size != expected_size or residual_path.stat().st_size != expected_size:
        raise RuntimeError("Phase 7B6m retained array size changed")
    later_map = np.memmap(state_path, mode="r", dtype=np.float64, shape=shape)
    residual_map = np.memmap(residual_path, mode="r", dtype=np.float64, shape=shape)
    with np.load(
        ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    ) as master:
        frequency_edge = np.array(master["active_edge_hz"], copy=True)
    with np.load(ROOT / protocol["sources"]["phase7b4r_material"]["path"]) as material:
        phase = int(
            json.loads(
                (ROOT / protocol["sources"]["phase7b6j_protocol"]["path"]).read_text(
                    encoding="utf-8"
                )
            )["configuration"]["phase_index"]
        )
        following = (phase + 1) % int(material["density_g_cm3"].shape[0])
        half_width = material["cell_mass_g_cm2"] / material["density_g_cm3"][following]
    parent_width = np.concatenate((half_width, half_width[::-1]))
    depth_width = np.repeat(parent_width / 16.0, 16)
    if depth_width.shape != (shape[2],) or np.any(depth_width <= 0.0):
        raise ArithmeticError("Phase 7B6m reconstructed depth widths are invalid")
    frequency_width = np.diff(frequency_edge)
    if frequency_width.shape != (shape[0],) or np.any(frequency_width <= 0.0):
        raise ArithmeticError("Phase 7B6m frequency widths are invalid")
    mu, angular_weight = gauss_legendre_split_mu_weights(shape[1], 0.0)
    rate_coefficient = np.stack(
        [
            _rate_coefficient_per_group(
                frequency_edge,
                int(configuration["frequency_quadrature_order_per_group"]),
                fit,
            )
            for fit in H_HE_GROUND_STATE_PHOTOIONIZATION_FITS
        ]
    )
    chunk_groups = int(configuration["frequency_chunk_groups"])
    omega = float(retained["omega14"])
    state_digest = hashlib.sha256()
    residual_digest = hashlib.sha256()
    minimum_later = np.inf
    minimum_earlier = np.inf
    maximum_state_change = 0.0
    maximum_state_scale = 0.0
    maximum_mean_change = 0.0
    maximum_mean_scale = 0.0
    weighted_mean_l1_numerator = 0.0
    weighted_mean_l1_scale_earlier = 0.0
    weighted_mean_l1_scale_later = 0.0
    volume_spectrum_earlier = np.empty(shape[0], dtype=np.float64)
    volume_spectrum_later = np.empty(shape[0], dtype=np.float64)
    boundary_flux_earlier = np.empty(shape[0], dtype=np.float64)
    boundary_flux_later = np.empty(shape[0], dtype=np.float64)
    rates_earlier = np.zeros((3, shape[2]), dtype=np.float64)
    rates_later = np.zeros((3, shape[2]), dtype=np.float64)
    total_depth = float(np.sum(depth_width))
    started = time.perf_counter()
    for start in range(0, shape[0], chunk_groups):
        stop = min(start + chunk_groups, shape[0])
        later = np.asarray(later_map[start:stop])
        residual = np.asarray(residual_map[start:stop])
        state_digest.update(later.tobytes(order="C"))
        residual_digest.update(residual.tobytes(order="C"))
        earlier = later - omega * residual
        minimum_later = min(minimum_later, float(np.min(later)))
        minimum_earlier = min(minimum_earlier, float(np.min(earlier)))
        difference = later - earlier
        maximum_state_change = max(
            maximum_state_change, float(np.max(np.abs(difference)))
        )
        maximum_state_scale = max(
            maximum_state_scale,
            float(np.max(np.abs(later))),
            float(np.max(np.abs(earlier))),
        )
        mean_later = 0.5 * np.einsum("m,gmd->gd", angular_weight, later)
        mean_earlier = 0.5 * np.einsum("m,gmd->gd", angular_weight, earlier)
        mean_difference = mean_later - mean_earlier
        maximum_mean_change = max(
            maximum_mean_change, float(np.max(np.abs(mean_difference)))
        )
        maximum_mean_scale = max(
            maximum_mean_scale,
            float(np.max(np.abs(mean_later))),
            float(np.max(np.abs(mean_earlier))),
        )
        measure = frequency_width[start:stop, None] * depth_width[None, :]
        weighted_mean_l1_numerator += float(np.sum(measure * np.abs(mean_difference)))
        weighted_mean_l1_scale_earlier += float(np.sum(measure * np.abs(mean_earlier)))
        weighted_mean_l1_scale_later += float(np.sum(measure * np.abs(mean_later)))
        volume_spectrum_earlier[start:stop] = (
            np.sum(mean_earlier * depth_width[None, :], axis=1) / total_depth
        )
        volume_spectrum_later[start:stop] = (
            np.sum(mean_later * depth_width[None, :], axis=1) / total_depth
        )
        left = mu < 0.0
        right = mu > 0.0
        boundary_flux_earlier[start:stop] = 2.0 * np.pi * (
            np.einsum(
                "m,gm->g", angular_weight[left] * np.abs(mu[left]), earlier[:, left, 0]
            )
            + np.einsum(
                "m,gm->g", angular_weight[right] * mu[right], earlier[:, right, -1]
            )
        )
        boundary_flux_later[start:stop] = 2.0 * np.pi * (
            np.einsum(
                "m,gm->g", angular_weight[left] * np.abs(mu[left]), later[:, left, 0]
            )
            + np.einsum(
                "m,gm->g", angular_weight[right] * mu[right], later[:, right, -1]
            )
        )
        rates_earlier += rate_coefficient[:, start:stop] @ mean_earlier
        rates_later += rate_coefficient[:, start:stop] @ mean_later

    state_hash = state_digest.hexdigest()
    residual_hash = residual_digest.hexdigest()
    hash_passed = bool(
        state_hash == retained["iteration14_state"]["sha256"]
        and residual_hash == retained["iteration13_residual"]["sha256"]
    )
    state_update = (
        maximum_state_change / maximum_state_scale
        if maximum_state_scale > 0.0
        else maximum_state_change
    )
    mean_update = (
        maximum_mean_change / maximum_mean_scale
        if maximum_mean_scale > 0.0
        else maximum_mean_change
    )
    weighted_mean_l1 = weighted_mean_l1_numerator / max(
        weighted_mean_l1_scale_earlier, weighted_mean_l1_scale_later
    )
    volume_spectrum_l1 = float(
        np.sum(frequency_width * np.abs(volume_spectrum_later - volume_spectrum_earlier))
        / max(
            np.sum(frequency_width * np.abs(volume_spectrum_later)),
            np.sum(frequency_width * np.abs(volume_spectrum_earlier)),
        )
    )
    integrated_earlier = float(
        np.sum(frequency_width * volume_spectrum_earlier) * 4.0 * np.pi / LIGHT_SPEED_CM_S
    )
    integrated_later = float(
        np.sum(frequency_width * volume_spectrum_later) * 4.0 * np.pi / LIGHT_SPEED_CM_S
    )
    integrated_change = _relative_change(integrated_earlier, integrated_later)
    boundary_l1 = float(
        np.sum(frequency_width * np.abs(boundary_flux_later - boundary_flux_earlier))
        / max(
            np.sum(frequency_width * np.abs(boundary_flux_later)),
            np.sum(frequency_width * np.abs(boundary_flux_earlier)),
        )
    )
    boundary_bolometric_earlier = float(np.sum(frequency_width * boundary_flux_earlier))
    boundary_bolometric_later = float(np.sum(frequency_width * boundary_flux_later))
    boundary_bolometric_change = _relative_change(
        boundary_bolometric_earlier, boundary_bolometric_later
    )
    rate_profile_changes = []
    rate_volume_changes = []
    for species in range(3):
        profile_scale = max(
            float(np.max(np.abs(rates_earlier[species]))),
            float(np.max(np.abs(rates_later[species]))),
        )
        profile_change = float(
            np.max(np.abs(rates_later[species] - rates_earlier[species]))
        )
        rate_profile_changes.append(
            profile_change / profile_scale if profile_scale > 0.0 else profile_change
        )
        volume_earlier = float(
            np.sum(depth_width * rates_earlier[species]) / total_depth
        )
        volume_later = float(np.sum(depth_width * rates_later[species]) / total_depth)
        rate_volume_changes.append(_relative_change(volume_earlier, volume_later))

    metrics = {
        "maximum_global_state_update_fraction": state_update,
        "maximum_global_angular_mean_update_fraction": mean_update,
        "frequency_depth_weighted_angular_mean_l1": weighted_mean_l1,
        "volume_mean_spectrum_l1": volume_spectrum_l1,
        "integrated_radiation_energy_fraction": integrated_change,
        "boundary_cell_flux_spectrum_l1": boundary_l1,
        "boundary_cell_bolometric_flux_fraction": boundary_bolometric_change,
        "photoionization_depth_profile_global_fractions": rate_profile_changes,
        "volume_mean_photoionization_fractions": rate_volume_changes,
    }
    gates = protocol["gates"]
    decision = {
        "frozen_protocol_hash_passed": True,
        "source_hashes_passed": True,
        "array_hashes_and_sizes_exact": hash_passed,
        "both_states_nonnegative_and_finite": bool(
            minimum_earlier >= 0.0
            and minimum_later >= 0.0
            and all(
                np.all(np.isfinite(value))
                for value in (
                    volume_spectrum_earlier,
                    volume_spectrum_later,
                    boundary_flux_earlier,
                    boundary_flux_later,
                    rates_earlier,
                    rates_later,
                )
            )
        ),
        "state_and_mean_global_gates_passed": bool(
            state_update < gates["maximum_global_state_update_fraction_below"]
            and mean_update
            < gates["maximum_global_angular_mean_update_fraction_below"]
        ),
        "integrated_field_gates_passed": bool(
            weighted_mean_l1
            < gates["frequency_depth_weighted_angular_mean_l1_below"]
            and volume_spectrum_l1 < gates["volume_mean_spectrum_l1_below"]
            and integrated_change
            < gates["integrated_radiation_energy_fraction_below"]
        ),
        "boundary_proxy_gates_passed": bool(
            boundary_l1 < gates["boundary_cell_flux_spectrum_l1_below"]
            and boundary_bolometric_change
            < gates["boundary_cell_bolometric_flux_fraction_below"]
        ),
        "photoionization_proxy_gates_passed": bool(
            max(rate_profile_changes)
            < gates["each_photoionization_depth_profile_global_fraction_below"]
            and max(rate_volume_changes)
            < gates["each_volume_mean_photoionization_fraction_below"]
        ),
        "algebraic_fixed_point_at_1e10": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
    }
    decision["phase7b6m_gate_passed"] = all(
        decision[name]
        for name in (
            "frozen_protocol_hash_passed",
            "source_hashes_passed",
            "array_hashes_and_sizes_exact",
            "both_states_nonnegative_and_finite",
            "state_and_mean_global_gates_passed",
            "integrated_field_gates_passed",
            "boundary_proxy_gates_passed",
            "photoionization_proxy_gates_passed",
        )
    )
    decision["fixed_material_science_functional_convergence"] = bool(
        decision["phase7b6m_gate_passed"]
    )
    decision["single_bounded_matter_feedback_pilot_authorized"] = bool(
        decision["phase7b6m_gate_passed"]
    )
    peak_rss = ru_maxrss_to_bytes(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "state_sha256": state_hash,
        "residual_sha256": residual_hash,
        "minimum_iteration13_intensity": minimum_earlier,
        "minimum_iteration14_intensity": minimum_later,
        "metrics": metrics,
        "integrated_values": {
            "radiation_energy_proxy_iteration13": integrated_earlier,
            "radiation_energy_proxy_iteration14": integrated_later,
            "boundary_bolometric_proxy_iteration13": boundary_bolometric_earlier,
            "boundary_bolometric_proxy_iteration14": boundary_bolometric_later,
        },
        "runtime_s": time.perf_counter() - started,
        "peak_process_rss_mib": peak_rss / MIB,
        "decision": decision,
        "figures": ["phase7b6m_science_functionals.png"],
    }
    _write_json_atomic(OUTPUT / "phase7b6m_science_functionals_summary.json", report)
    _plot(
        OUTPUT / "phase7b6m_science_functionals.png",
        frequency_edge,
        depth_width,
        volume_spectrum_earlier,
        volume_spectrum_later,
        boundary_flux_earlier,
        boundary_flux_later,
        rates_earlier,
        rates_later,
        metrics,
    )
    return report


def _plot(
    path: Path,
    frequency_edge: np.ndarray,
    depth_width: np.ndarray,
    spectrum_earlier: np.ndarray,
    spectrum_later: np.ndarray,
    flux_earlier: np.ndarray,
    flux_later: np.ndarray,
    rates_earlier: np.ndarray,
    rates_later: np.ndarray,
    metrics: dict[str, object],
) -> None:
    centre = np.sqrt(frequency_edge[:-1] * frequency_edge[1:])
    energy_ev = PLANCK_ERG_S * centre / EV_ERG
    metric_values = [
        metrics["maximum_global_state_update_fraction"],
        metrics["maximum_global_angular_mean_update_fraction"],
        metrics["volume_mean_spectrum_l1"],
        metrics["boundary_cell_flux_spectrum_l1"],
        max(metrics["photoionization_depth_profile_global_fractions"]),
    ]
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].bar(
        ["State", "Mean intensity", "Volume spectrum", "Boundary proxy", "Photo-rate proxy"],
        metric_values,
        color=["#4c78a8", "#72b7b2", "#54a24b", "#f58518", "#e45756"],
    )
    axes[0, 0].axhline(1.0e-3, color="0.25", ls="--", label="Science gate")
    axes[0, 0].set_yscale("log")
    axes[0, 0].tick_params(axis="x", rotation=15)
    axes[0, 0].set(ylabel="Relative iteration change", title="(a) Preregistered metrics")
    axes[0, 0].legend(frameon=False)
    axes[0, 1].loglog(energy_ev, centre * spectrum_earlier, label="Iteration 13")
    axes[0, 1].loglog(energy_ev, centre * spectrum_later, ls="--", label="Iteration 14")
    axes[0, 1].set(
        xlabel="Photon energy (eV)",
        ylabel="nu J_nu (arbitrary units)",
        title="(b) Volume-mean spectrum",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].loglog(energy_ev, centre * flux_earlier, label="Iteration 13")
    axes[1, 0].loglog(energy_ev, centre * flux_later, ls="--", label="Iteration 14")
    axes[1, 0].set(
        xlabel="Photon energy (eV)",
        ylabel="nu F_nu proxy (arbitrary units)",
        title="(c) Boundary-cell flux proxy",
    )
    axes[1, 0].legend(frameon=False)
    mass_coordinate = np.cumsum(depth_width) / np.sum(depth_width)
    labels = ("H I", "He I", "He II")
    for species, label in enumerate(labels):
        scale = max(np.max(np.abs(rates_earlier[species])), np.max(np.abs(rates_later[species])))
        axes[1, 1].plot(
            mass_coordinate,
            np.abs(rates_later[species] - rates_earlier[species]) / scale,
            label=label,
        )
    axes[1, 1].set_yscale("log")
    axes[1, 1].set(
        xlabel="Normalized depth coordinate",
        ylabel="Absolute rate change / global scale",
        title="(d) Lab-frame photo-rate proxies",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b6m_preregistered_science_functionals.json",
    )
    args = parser.parse_args()
    report = run(args.protocol)
    print(json.dumps(report["decision"], indent=2))


if __name__ == "__main__":
    main()
