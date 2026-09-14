"""Phase 7B9bh：固定物质辐射场的正性约束仿射 Krylov 最小残差。"""

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
from scipy.optimize import minimize

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "5210744bfabcb4bee1af256797ae00890e6bf45644343e76783e000f526bc2e4"
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
        raise RuntimeError("frozen Phase 7B9bh protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if (
            source_path.stat().st_size != int(source["size_bytes"])
            or _sha256(source_path) != source["sha256"]
        ):
            raise RuntimeError(f"frozen Phase 7B9bh source changed: {source['path']}")
    return protocol


def _shape(configuration: dict[str, object]) -> tuple[int, int, int]:
    return (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )


def _open_basis(
    configuration: dict[str, object], shape: tuple[int, int, int]
) -> tuple[list[np.memmap], list[np.memmap]]:
    states = [
        np.memmap(ROOT / row["state_path"], mode="r", dtype=np.float64, shape=shape)
        for row in configuration["basis"]
    ]
    mapped = [
        np.memmap(ROOT / row["mapped_path"], mode="r", dtype=np.float64, shape=shape)
        for row in configuration["basis"]
    ]
    return states, mapped


def _gram_and_endpoint_metrics(
    configuration: dict[str, object], shape: tuple[int, int, int]
) -> dict[str, object]:
    states, mapped = _open_basis(configuration, shape)
    count = len(states)
    gram = np.zeros((count, count), dtype=np.float64)
    maximum_change = np.zeros(count, dtype=np.float64)
    maximum_scale = np.zeros(count, dtype=np.float64)
    minimum_state = np.full(count, np.inf, dtype=np.float64)
    minimum_mapped = np.full(count, np.inf, dtype=np.float64)
    chunk = int(configuration["scan_frequency_chunk"])
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        state_block = [np.asarray(array[start:stop]) for array in states]
        mapped_block = [np.asarray(array[start:stop]) for array in mapped]
        residual = [second - first for first, second in zip(state_block, mapped_block)]
        for index in range(count):
            maximum_change[index] = max(
                maximum_change[index], float(np.max(np.abs(residual[index])))
            )
            maximum_scale[index] = max(
                maximum_scale[index],
                float(np.max(np.abs(state_block[index]))),
                float(np.max(np.abs(mapped_block[index]))),
            )
            minimum_state[index] = min(
                minimum_state[index], float(np.min(state_block[index]))
            )
            minimum_mapped[index] = min(
                minimum_mapped[index], float(np.min(mapped_block[index]))
            )
        for left in range(count):
            for right in range(left, count):
                value = float(
                    np.sum(residual[left] * residual[right], dtype=np.float64)
                )
                gram[left, right] += value
                if left != right:
                    gram[right, left] += value
    del states, mapped
    residuals = np.divide(
        maximum_change,
        maximum_scale,
        out=np.array(maximum_change, copy=True),
        where=maximum_scale > 0.0,
    )
    return {
        "gram": gram,
        "gram_condition_number": float(np.linalg.cond(gram)),
        "basis_global_residuals": residuals,
        "minimum_basis_state_intensities": minimum_state,
        "minimum_basis_mapped_intensities": minimum_mapped,
    }


def _raw_coefficients(gram: np.ndarray) -> np.ndarray:
    count = gram.shape[0]
    kkt = np.zeros((count + 1, count + 1), dtype=np.float64)
    kkt[:count, :count] = 2.0 * gram
    kkt[:count, count] = 1.0
    kkt[count, :count] = 1.0
    right = np.zeros(count + 1, dtype=np.float64)
    right[-1] = 1.0
    return np.linalg.solve(kkt, right)[:count]


def _affine_block(alpha: np.ndarray, arrays: list[np.ndarray]) -> np.ndarray:
    result = alpha[0] * arrays[0]
    for index in range(1, len(arrays)):
        result = result + alpha[index] * arrays[index]
    return result


def _most_violated_direction(
    candidate: np.ndarray, arrays: list[np.ndarray]
) -> np.ndarray | None:
    negative = candidate < 0.0
    if not np.any(negative):
        return None
    denominator = np.maximum.reduce(arrays)
    relative = np.divide(
        candidate,
        denominator,
        out=np.zeros_like(candidate),
        where=denominator > 0.0,
    )
    index = np.unravel_index(int(np.argmin(relative)), relative.shape)
    vector = np.asarray([array[index] for array in arrays], dtype=np.float64)
    scale = float(np.max(vector))
    if scale <= 0.0:
        raise ArithmeticError("negative affine value has no positive basis scale")
    return vector / scale


def _constrain_coefficients(
    configuration: dict[str, object],
    shape: tuple[int, int, int],
    gram: np.ndarray,
    raw: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, object]], dict[str, object]]:
    states, mapped = _open_basis(configuration, shape)
    coefficient = np.array(raw, copy=True)
    constraints: list[np.ndarray] = []
    history: list[dict[str, object]] = []
    chunk = int(configuration["scan_frequency_chunk"])
    final = {
        "candidate_negative_count": -1,
        "mapped_negative_count": -1,
        "minimum_candidate_intensity": float("nan"),
        "minimum_mapped_intensity": float("nan"),
    }
    for iteration in range(int(configuration["maximum_cutting_plane_iterations"])):
        started = time.perf_counter()
        added: list[np.ndarray] = []
        candidate_negative = 0
        mapped_negative = 0
        minimum_candidate = float("inf")
        minimum_map = float("inf")
        for start in range(0, shape[0], chunk):
            stop = min(start + chunk, shape[0])
            state_block = [np.asarray(array[start:stop]) for array in states]
            mapped_block = [np.asarray(array[start:stop]) for array in mapped]
            candidate = _affine_block(coefficient, state_block)
            candidate_map = _affine_block(coefficient, mapped_block)
            candidate_negative += int(np.count_nonzero(candidate < 0.0))
            mapped_negative += int(np.count_nonzero(candidate_map < 0.0))
            minimum_candidate = min(minimum_candidate, float(np.min(candidate)))
            minimum_map = min(minimum_map, float(np.min(candidate_map)))
            direction = _most_violated_direction(candidate, state_block)
            if direction is not None:
                added.append(direction)
            direction = _most_violated_direction(candidate_map, mapped_block)
            if direction is not None:
                added.append(direction)
        final = {
            "candidate_negative_count": candidate_negative,
            "mapped_negative_count": mapped_negative,
            "minimum_candidate_intensity": minimum_candidate,
            "minimum_mapped_intensity": minimum_map,
        }
        row: dict[str, object] = {
            "iteration": iteration,
            "coefficients": coefficient.tolist(),
            **final,
            "new_chunk_constraints": len(added),
            "scan_wall_runtime_s": time.perf_counter() - started,
        }
        history.append(row)
        if candidate_negative == 0 and mapped_negative == 0:
            break
        constraints.extend(added)
        unique: list[np.ndarray] = []
        tolerance = float(configuration["constraint_direction_duplicate_tolerance"])
        for vector in constraints:
            if not any(np.max(np.abs(vector - prior)) < tolerance for prior in unique):
                unique.append(vector)
        constraints = unique
        matrix = np.asarray(constraints)
        count = coefficient.size
        result = minimize(
            lambda value: float(value @ gram @ value),
            coefficient,
            jac=lambda value: 2.0 * gram @ value,
            method="SLSQP",
            constraints=[
                {
                    "type": "eq",
                    "fun": lambda value: np.sum(value) - 1.0,
                    "jac": lambda value: np.ones(count),
                },
                {
                    "type": "ineq",
                    "fun": lambda value, matrix=matrix: matrix @ value,
                    "jac": lambda value, matrix=matrix: matrix,
                },
            ],
            options={
                "ftol": float(configuration["slsqp_function_tolerance"]),
                "maxiter": int(configuration["slsqp_maximum_iterations"]),
            },
        )
        if not result.success:
            raise RuntimeError(f"Phase 7B9bh constrained solve failed: {result.message}")
        coefficient = np.asarray(result.x, dtype=np.float64)
        row["constraint_count_after_solve"] = len(constraints)
        row["next_coefficients"] = coefficient.tolist()
    del states, mapped
    return coefficient, history, final


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


def _candidate_metrics(
    configuration: dict[str, object],
    shape: tuple[int, int, int],
    coefficient: np.ndarray,
    active_edge: np.ndarray,
) -> dict[str, object]:
    states, mapped = _open_basis(configuration, shape)
    mu, weight = gauss_legendre_split_mu_weights(shape[1], 0.0)
    width = np.diff(active_edge)
    maximum_change = 0.0
    maximum_scale = 0.0
    minimum_candidate = float("inf")
    minimum_map = float("inf")
    negative_candidate = 0
    negative_map = 0
    boundary_numerator = 0.0
    candidate_scale = 0.0
    mapped_scale = 0.0
    candidate_bolometric = 0.0
    mapped_bolometric = 0.0
    reports: list[dict[str, object]] = []
    block = int(configuration["diagnostic_frequency_block"])
    for start in range(0, shape[0], block):
        stop = min(start + block, shape[0])
        state_block = [np.asarray(array[start:stop]) for array in states]
        mapped_block = [np.asarray(array[start:stop]) for array in mapped]
        candidate = _affine_block(coefficient, state_block)
        candidate_map = _affine_block(coefficient, mapped_block)
        change = float(np.max(np.abs(candidate_map - candidate)))
        scale = max(float(np.max(np.abs(candidate))), float(np.max(np.abs(candidate_map))))
        maximum_change = max(maximum_change, change)
        maximum_scale = max(maximum_scale, scale)
        minimum_candidate = min(minimum_candidate, float(np.min(candidate)))
        minimum_map = min(minimum_map, float(np.min(candidate_map)))
        negative_candidate += int(np.count_nonzero(candidate < 0.0))
        negative_map += int(np.count_nonzero(candidate_map < 0.0))
        candidate_flux = _block_flux(candidate, mu, weight, width[start:stop])
        mapped_flux = _block_flux(candidate_map, mu, weight, width[start:stop])
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
                "block_relative_candidate_residual": change / scale if scale > 0.0 else change,
            }
        )
    del states, mapped
    residual = maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
    return {
        "global_original_operator_residual": residual,
        "global_boundary_spectrum_l1": boundary_numerator
        / max(candidate_scale, mapped_scale),
        "global_boundary_bolometric_fraction": abs(
            mapped_bolometric - candidate_bolometric
        )
        / max(abs(candidate_bolometric), abs(mapped_bolometric)),
        "minimum_candidate_intensity": minimum_candidate,
        "minimum_mapped_candidate_intensity": minimum_map,
        "candidate_negative_count": negative_candidate,
        "mapped_candidate_negative_count": negative_map,
        "reports": reports,
    }


def _write_candidate_pair(
    configuration: dict[str, object],
    shape: tuple[int, int, int],
    coefficient: np.ndarray,
) -> tuple[str, str, float]:
    states, mapped = _open_basis(configuration, shape)
    candidate_path = ROOT / configuration["candidate_output_path"]
    mapped_path = ROOT / configuration["mapped_candidate_output_path"]
    expected_size = int(configuration["raw_float64_checkpoint_size_bytes"])
    if (
        candidate_path.stat().st_size != expected_size
        or mapped_path.stat().st_size != expected_size
        or _sha256(candidate_path) != configuration["candidate_output_previous_sha256"]
        or _sha256(mapped_path) != configuration["mapped_output_previous_sha256"]
    ):
        raise RuntimeError("Phase 7B9bh named scratch output changed")
    candidate_output = np.memmap(
        candidate_path, mode="r+", dtype=np.float64, shape=shape
    )
    mapped_output = np.memmap(mapped_path, mode="r+", dtype=np.float64, shape=shape)
    started = time.perf_counter()
    chunk = int(configuration["scan_frequency_chunk"])
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        state_block = [np.asarray(array[start:stop]) for array in states]
        mapped_block = [np.asarray(array[start:stop]) for array in mapped]
        # 固定物质算子是仿射的，因此同一组系数同时作用于状态及其正式映射。
        candidate_output[start:stop] = _affine_block(coefficient, state_block)
        mapped_output[start:stop] = _affine_block(coefficient, mapped_block)
    candidate_output.flush()
    mapped_output.flush()
    del states, mapped, candidate_output, mapped_output
    wall = time.perf_counter() - started
    return _sha256(candidate_path), _sha256(mapped_path), wall


def _plot(path: Path, reports: list[dict[str, object]], residual: float) -> None:
    block = np.asarray([row["block_index"] for row in reports])
    local = np.asarray([row["block_relative_candidate_residual"] for row in reports])
    figure, axis = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    axis.semilogy(block, local, "o-", ms=3)
    axis.axhline(residual, color="black", ls="--", lw=1, label="Global max-norm")
    axis.set(
        xlabel="Natural frequency block",
        ylabel="Block-relative affine residual",
        title="Positive affine Krylov candidate",
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
    metrics = _gram_and_endpoint_metrics(configuration, shape)
    gram = metrics["gram"]
    raw = _raw_coefficients(gram)
    constrained, history, positivity = _constrain_coefficients(
        configuration, shape, gram, raw
    )
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        active_edge = np.asarray(master["active_edge_hz"])
    candidate = _candidate_metrics(configuration, shape, constrained, active_edge)
    basis_residuals = np.asarray(metrics["basis_global_residuals"])
    best_basis = float(np.min(basis_residuals))
    ratio = float(candidate["global_original_operator_residual"]) / best_basis
    checks = {
        "gram_condition_pass": metrics["gram_condition_number"]
        < gates["gram_condition_number_below"],
        "basis_positive_pass": bool(
            np.all(metrics["minimum_basis_state_intensities"] >= 0.0)
            and np.all(metrics["minimum_basis_mapped_intensities"] >= 0.0)
        ),
        "finite_coefficients_pass": bool(np.all(np.isfinite(constrained))),
        "coefficient_sum_pass": abs(float(np.sum(constrained)) - 1.0)
        < gates["coefficient_sum_absolute_error_below"],
        "candidate_and_map_positive_pass": (
            candidate["candidate_negative_count"] == 0
            and candidate["mapped_candidate_negative_count"] == 0
            and positivity["candidate_negative_count"] == 0
            and positivity["mapped_negative_count"] == 0
        ),
        "maximum_norm_improvement_pass": ratio
        < gates["candidate_residual_ratio_to_best_basis_below"],
        "boundary_pass": candidate["global_boundary_spectrum_l1"]
        < gates["global_boundary_spectrum_l1_below"]
        and candidate["global_boundary_bolometric_fraction"]
        < gates["global_boundary_bolometric_fraction_below"],
    }
    passed_before_write = all(checks.values())
    candidate_sha = None
    mapped_sha = None
    write_wall = 0.0
    if passed_before_write:
        candidate_sha, mapped_sha, write_wall = _write_candidate_pair(
            configuration, shape, constrained
        )
    checks["write_resources_pass"] = (
        passed_before_write and write_wall < gates["write_wall_time_strictly_below_s"]
    )
    passed = all(checks.values())
    target = float(gates["global_original_operator_residual_below"])
    figure_path = ROOT / configuration["figure_path"]
    _plot(
        figure_path,
        candidate["reports"],
        float(candidate["global_original_operator_residual"]),
    )
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        peak_rss_mib = peak_rss / MIB
    else:
        peak_rss_mib = peak_rss * 1024 / MIB
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-informed]+[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "basis": configuration["basis"],
        "gram_matrix": gram.tolist(),
        "gram_condition_number": metrics["gram_condition_number"],
        "basis_global_original_operator_residuals": basis_residuals.tolist(),
        "raw_affine_coefficients": raw.tolist(),
        "constrained_affine_coefficients": constrained.tolist(),
        "coefficient_sum_absolute_error": abs(float(np.sum(constrained)) - 1.0),
        "raw_predicted_unweighted_l2_residual_squared": float(raw @ gram @ raw),
        "constrained_predicted_unweighted_l2_residual_squared": float(
            constrained @ gram @ constrained
        ),
        "candidate_global_original_operator_residual": candidate[
            "global_original_operator_residual"
        ],
        "candidate_residual_ratio_to_best_basis": ratio,
        "candidate_boundary_spectrum_l1": candidate[
            "global_boundary_spectrum_l1"
        ],
        "candidate_boundary_bolometric_fraction": candidate[
            "global_boundary_bolometric_fraction"
        ],
        "minimum_candidate_intensity": candidate["minimum_candidate_intensity"],
        "minimum_mapped_candidate_intensity": candidate[
            "minimum_mapped_candidate_intensity"
        ],
        "candidate_negative_count": candidate["candidate_negative_count"],
        "mapped_candidate_negative_count": candidate[
            "mapped_candidate_negative_count"
        ],
        "cutting_plane_history": history,
        "candidate_state_path": configuration["candidate_output_path"]
        if passed_before_write
        else None,
        "candidate_state_sha256": candidate_sha,
        "mapped_candidate_state_path": configuration["mapped_candidate_output_path"]
        if passed_before_write
        else None,
        "mapped_candidate_state_sha256": mapped_sha,
        "write_wall_runtime_s": write_wall,
        "total_wall_runtime_s": time.perf_counter() - started,
        "peak_process_rss_mib": peak_rss_mib,
        "gate_checks": checks,
        "decision": {
            "positive_affine_krylov_candidate_passed": passed,
            "candidate_pair_written": passed_before_write,
            "fixed_matter_target_reached_algebraically": passed
            and float(candidate["global_original_operator_residual"]) < target,
            "fresh_original_operator_self_audit_authorized": passed
            and float(candidate["global_original_operator_residual"]) < target,
            "continue_positive_affine_krylov_authorized": passed
            and float(candidate["global_original_operator_residual"]) >= target,
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
        default=OUTPUT / "phase7b9bh_preregistered_positive_affine_krylov.json",
    )
    args = parser.parse_args()
    run(args.protocol)


if __name__ == "__main__":
    main()
