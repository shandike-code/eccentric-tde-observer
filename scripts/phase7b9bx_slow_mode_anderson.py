"""Phase 7B9bx：执行最近两步 Picard 的受保护 Anderson(1) 外推。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "955b28b5fa51364fb976d2a51cce47f8bde8e8b9961322d916dbc86fae960376"
MIB = 1024**2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bx protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if (
            source_path.stat().st_size != int(source["size_bytes"])
            or _sha256(source_path) != source["sha256"]
        ):
            raise RuntimeError(f"frozen Phase 7B9bx source changed: {source['path']}")
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _open_states(
    configuration: dict[str, object], shape: tuple[int, int, int]
) -> tuple[np.memmap, np.memmap, np.memmap]:
    return tuple(
        np.memmap(
            ROOT / configuration[f"x{index}_state_path"],
            mode="r",
            dtype=np.float64,
            shape=shape,
        )
        for index in (9, 10, 11)
    )  # type: ignore[return-value]


def _block_flux(
    intensity: np.ndarray,
    mu: np.ndarray,
    weight: np.ndarray,
    frequency_width: np.ndarray,
) -> np.ndarray:
    left = mu < 0.0
    right = mu > 0.0
    flux = 2.0 * np.pi * (
        np.einsum(
            "m,fm->f",
            weight[left] * np.abs(mu[left]),
            intensity[:, left, 0],
        )
        + np.einsum(
            "m,fm->f",
            weight[right] * mu[right],
            intensity[:, right, -1],
        )
    )
    return frequency_width * flux


def _scan_direction(
    configuration: dict[str, object], shape: tuple[int, int, int]
) -> dict[str, object]:
    x9, x10, x11 = _open_states(configuration, shape)
    gram = np.zeros((2, 2), dtype=np.float64)
    difference_squared = 0.0
    candidate_positive_upper = np.inf
    mapped_positive_upper = np.inf
    minimum_basis = np.full(3, np.inf, dtype=np.float64)
    chunk = int(configuration["scan_frequency_chunk"])
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        a = np.asarray(x9[start:stop])
        b = np.asarray(x10[start:stop])
        c = np.asarray(x11[start:stop])
        f0 = b - a
        f1 = c - b
        delta = f1 - f0
        gram[0, 0] += float(np.sum(f0 * f0, dtype=np.float64))
        gram[0, 1] += float(np.sum(f0 * f1, dtype=np.float64))
        gram[1, 1] += float(np.sum(f1 * f1, dtype=np.float64))
        difference_squared += float(np.sum(delta * delta, dtype=np.float64))
        minimum_basis = np.minimum(
            minimum_basis,
            np.asarray([np.min(a), np.min(b), np.min(c)], dtype=np.float64),
        )
        # 中文：从最新状态向前外推；只缩短一个全局系数，不改任何单元值。
        negative = f0 < 0.0
        if np.any(negative):
            candidate_positive_upper = min(
                candidate_positive_upper,
                float(np.min(1.0 + b[negative] / (-f0[negative]))),
            )
        negative = f1 < 0.0
        if np.any(negative):
            mapped_positive_upper = min(
                mapped_positive_upper,
                float(np.min(1.0 + c[negative] / (-f1[negative]))),
            )
    gram[1, 0] = gram[0, 1]
    del x9, x10, x11
    if not np.all(np.isfinite(gram)) or difference_squared <= 0.0:
        raise ArithmeticError("Phase 7B9bx slow-direction norms are invalid")
    slope = gram[0, 1] - gram[0, 0]
    raw_fraction = -slope / difference_squared
    exact_positive_upper = min(candidate_positive_upper, mapped_positive_upper)
    maximum_fraction = float(configuration["maximum_forward_picard_fraction"])
    selected_upper = min(maximum_fraction, exact_positive_upper)
    if np.isfinite(exact_positive_upper) and exact_positive_upper <= maximum_fraction:
        selected_upper = float(np.nextafter(exact_positive_upper, 1.0))
    minimum_fraction = float(configuration["minimum_forward_picard_fraction"])
    selected = min(max(raw_fraction, minimum_fraction), selected_upper)
    return {
        "gram": gram,
        "difference_squared": difference_squared,
        "difference_ratio": difference_squared / gram[0, 0],
        "raw_forward_fraction": raw_fraction,
        "candidate_positive_upper": candidate_positive_upper,
        "mapped_positive_upper": mapped_positive_upper,
        "exact_positive_upper": exact_positive_upper,
        "selected_upper": selected_upper,
        "selected_forward_fraction": selected,
        "minimum_basis_intensities": minimum_basis,
    }


def _candidate_metrics(
    configuration: dict[str, object],
    shape: tuple[int, int, int],
    selected: float,
    active_edge: np.ndarray,
) -> dict[str, object]:
    x9, x10, x11 = _open_states(configuration, shape)
    mu, weight = gauss_legendre_split_mu_weights(shape[1], 0.0)
    width = np.diff(active_edge)
    maximum_change = 0.0
    maximum_scale = 0.0
    minimum_candidate = np.inf
    minimum_map = np.inf
    candidate_negative = 0
    mapped_negative = 0
    boundary_numerator = 0.0
    candidate_scale = 0.0
    mapped_scale = 0.0
    candidate_bolometric = 0.0
    mapped_bolometric = 0.0
    reports: list[dict[str, object]] = []
    block = int(configuration["diagnostic_frequency_block"])
    for start in range(0, shape[0], block):
        stop = min(start + block, shape[0])
        a = np.asarray(x9[start:stop])
        b = np.asarray(x10[start:stop])
        c = np.asarray(x11[start:stop])
        candidate = b + (selected - 1.0) * (b - a)
        predicted_map = c + (selected - 1.0) * (c - b)
        change = float(np.max(np.abs(predicted_map - candidate)))
        scale = max(
            float(np.max(np.abs(candidate))),
            float(np.max(np.abs(predicted_map))),
        )
        maximum_change = max(maximum_change, change)
        maximum_scale = max(maximum_scale, scale)
        minimum_candidate = min(minimum_candidate, float(np.min(candidate)))
        minimum_map = min(minimum_map, float(np.min(predicted_map)))
        candidate_negative += int(np.count_nonzero(candidate < 0.0))
        mapped_negative += int(np.count_nonzero(predicted_map < 0.0))
        candidate_flux = _block_flux(candidate, mu, weight, width[start:stop])
        mapped_flux = _block_flux(predicted_map, mu, weight, width[start:stop])
        boundary_numerator += float(np.sum(np.abs(mapped_flux - candidate_flux)))
        candidate_scale += float(np.sum(np.abs(candidate_flux)))
        mapped_scale += float(np.sum(np.abs(mapped_flux)))
        candidate_bolometric += float(np.sum(candidate_flux))
        mapped_bolometric += float(np.sum(mapped_flux))
        reports.append(
            {
                "block_index": len(reports),
                "core_group_start": start,
                "core_group_stop": stop,
                "block_relative_predicted_residual": (
                    change / scale if scale > 0.0 else change
                ),
            }
        )
    del x9, x10, x11
    residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    return {
        "predicted_global_original_operator_residual": residual,
        "predicted_boundary_spectrum_l1": boundary_numerator
        / max(candidate_scale, mapped_scale),
        "predicted_boundary_bolometric_fraction": abs(
            mapped_bolometric - candidate_bolometric
        )
        / max(abs(candidate_bolometric), abs(mapped_bolometric)),
        "minimum_candidate_intensity": minimum_candidate,
        "minimum_predicted_map_intensity": minimum_map,
        "candidate_negative_count": candidate_negative,
        "predicted_map_negative_count": mapped_negative,
        "reports": reports,
    }


def _write_candidate(
    configuration: dict[str, object],
    shape: tuple[int, int, int],
    selected: float,
) -> tuple[str, float]:
    x9, x10, _ = _open_states(configuration, shape)
    output_path = ROOT / configuration["candidate_output_path"]
    if output_path.stat().st_size != int(
        configuration["raw_float64_checkpoint_size_bytes"]
    ):
        raise RuntimeError("Phase 7B9bx named scratch checkpoint size changed")
    current_sha = _sha256(output_path)
    previous_sha = configuration["candidate_output_previous_sha256"]
    output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
    started = time.perf_counter()
    chunk = int(configuration["scan_frequency_chunk"])
    if current_sha != previous_sha:
        # 中文：若上次仅在摘要序列化处中断，逐块验证已写候选后恢复，绝不盲信暂存文件。
        for start in range(0, shape[0], chunk):
            stop = min(start + chunk, shape[0])
            a = np.asarray(x9[start:stop])
            b = np.asarray(x10[start:stop])
            expected = b + (selected - 1.0) * (b - a)
            if not np.array_equal(np.asarray(output[start:stop]), expected):
                raise RuntimeError(
                    "Phase 7B9bx changed scratch is not the frozen affine candidate"
                )
        del x9, x10, output
        return current_sha, time.perf_counter() - started
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        a = np.asarray(x9[start:stop])
        b = np.asarray(x10[start:stop])
        # 中文：写入单一全局仿射外推，不裁剪、不加 floor、不重归一化。
        output[start:stop] = b + (selected - 1.0) * (b - a)
    output.flush()
    del x9, x10, output
    return _sha256(output_path), time.perf_counter() - started


def _plot(
    path: Path,
    reports: list[dict[str, object]],
    x10_residual: float,
    candidate_residual: float,
) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    local = np.asarray(
        [row["block_relative_predicted_residual"] for row in reports]
    )
    figure, axis = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    axis.semilogy(block, local, "o-", ms=3)
    axis.axhline(x10_residual, color="0.45", ls=":", label="Latest Picard state")
    axis.axhline(
        candidate_residual,
        color="black",
        ls="--",
        label="Predicted global maximum norm",
    )
    axis.set(
        xlabel="Natural frequency block",
        ylabel="Block-relative predicted residual",
        title="Protected Anderson(1) slow-mode candidate",
    )
    axis.legend()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    started = time.perf_counter()
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = _shape(configuration)
    direction = _scan_direction(configuration, shape)
    selected = float(direction["selected_forward_fraction"])
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        active_edge = np.asarray(master["active_edge_hz"])
    candidate = _candidate_metrics(configuration, shape, selected, active_edge)
    x10_residual = float(configuration["x10_original_operator_residual"])
    ratio = float(candidate["predicted_global_original_operator_residual"]) / x10_residual
    coefficient_l1 = abs(1.0 - selected) + abs(selected)
    checks = {
        "basis_positive_pass": bool(
            np.all(np.asarray(direction["minimum_basis_intensities"]) >= 0.0)
        ),
        "resolved_slow_direction_pass": bool(
            direction["difference_ratio"]
            > gates["difference_norm_squared_to_x9_residual_norm_squared_above"]
        ),
        "forward_extrapolation_pass": bool(
            selected > gates["selected_forward_picard_fraction_strictly_above"]
        ),
        "coefficient_trust_pass": bool(
            coefficient_l1 < gates["coefficient_l1_norm_strictly_below"]
        ),
        "candidate_and_predicted_map_positive_pass": (
            candidate["candidate_negative_count"] == 0
            and candidate["predicted_map_negative_count"] == 0
            and candidate["minimum_candidate_intensity"]
            >= gates["minimum_candidate_and_predicted_map_intensity_at_least"]
            and candidate["minimum_predicted_map_intensity"]
            >= gates["minimum_candidate_and_predicted_map_intensity_at_least"]
        ),
        "predicted_maximum_norm_improvement_pass": bool(
            ratio < gates["predicted_global_residual_ratio_to_x10_below"]
        ),
        "boundary_pass": bool(
            candidate["predicted_boundary_spectrum_l1"]
            < gates["global_boundary_spectrum_l1_below"]
            and candidate["predicted_boundary_bolometric_fraction"]
            < gates["global_boundary_bolometric_fraction_below"]
        ),
    }
    passed_before_write = all(checks.values())
    candidate_sha = None
    write_wall = 0.0
    if passed_before_write:
        candidate_sha, write_wall = _write_candidate(configuration, shape, selected)
    checks["write_resources_pass"] = (
        passed_before_write and write_wall < gates["write_wall_time_strictly_below_s"]
    )
    passed = all(checks.values())
    figure_path = ROOT / configuration["figure_path"]
    _plot(
        figure_path,
        candidate["reports"],
        x10_residual,
        float(candidate["predicted_global_original_operator_residual"]),
    )
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mib = peak_rss / MIB if sys.platform == "darwin" else peak_rss * 1024 / MIB
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-informed]+[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "state_paths": {
            label: configuration[f"{label}_state_path"]
            for label in ("x9", "x10", "x11")
        },
        "state_sha256": {
            label: configuration[f"{label}_state_sha256"]
            for label in ("x9", "x10", "x11")
        },
        "residual_gram_matrix": np.asarray(direction["gram"]).tolist(),
        "difference_norm_squared": direction["difference_squared"],
        "difference_norm_squared_to_x9_residual_norm_squared": direction[
            "difference_ratio"
        ],
        "raw_forward_picard_fraction": direction["raw_forward_fraction"],
        "candidate_positive_upper_fraction": direction["candidate_positive_upper"],
        "mapped_positive_upper_fraction": direction["mapped_positive_upper"],
        "selected_upper_fraction": direction["selected_upper"],
        "selected_forward_picard_fraction": selected,
        "affine_coefficients_on_x9_x10": [1.0 - selected, selected],
        "coefficient_l1_norm": coefficient_l1,
        "x10_global_original_operator_residual": x10_residual,
        "predicted_global_original_operator_residual": candidate[
            "predicted_global_original_operator_residual"
        ],
        "predicted_residual_ratio_to_x10": ratio,
        "predicted_boundary_spectrum_l1": candidate[
            "predicted_boundary_spectrum_l1"
        ],
        "predicted_boundary_bolometric_fraction": candidate[
            "predicted_boundary_bolometric_fraction"
        ],
        "minimum_candidate_intensity": candidate["minimum_candidate_intensity"],
        "minimum_predicted_map_intensity": candidate[
            "minimum_predicted_map_intensity"
        ],
        "candidate_negative_count": candidate["candidate_negative_count"],
        "predicted_map_negative_count": candidate["predicted_map_negative_count"],
        "candidate_state_path": configuration["candidate_output_path"] if passed else None,
        "candidate_state_sha256": candidate_sha if passed else None,
        "write_wall_runtime_s": write_wall,
        "total_wall_runtime_s": time.perf_counter() - started,
        "peak_process_rss_mib": peak_rss_mib,
        "gate_checks": checks,
        "decision": {
            "protected_slow_mode_candidate_passed": passed,
            "candidate_written": passed,
            "fresh_original_operator_map_authorized": passed,
            "resume_phase7b9bt_authorized": not passed,
            "material_feedback_authorized": False,
        },
        "reports": candidate["reports"],
        "figures": [figure_path.name],
    }
    _write_json_atomic(ROOT / configuration["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9bx_preregistered_slow_mode_anderson.json",
    )
    args = parser.parse_args()
    run(args.protocol)


if __name__ == "__main__":
    main()
