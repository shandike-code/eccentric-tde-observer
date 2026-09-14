"""Phase 7B9di：双缓冲、两遍 dry-map 的精确 Anderson(1) 尾段预案。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as sequence
    from scripts import phase7b9_protocol_builders as frozen
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as sequence  # type: ignore[no-redef]
    import phase7b9_protocol_builders as frozen  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9di_streaming_anderson_tail.py"
ORCHESTRATOR_RELATIVE_PATH = (
    "scripts/phase7b9di_streaming_anderson_orchestrator.py"
)
PREREGISTER_BUILDER_RELATIVE_PATH = (
    "scripts/phase7b9di_preregister_streaming_anderson_tail.py"
)
DRY_PASS_PARENT_RELATIVE_PATH = "scripts/phase7b9_streaming_dry_pass_parent.py"
SCAN_FREQUENCY_CHUNK = 16
DIAGNOSTIC_FREQUENCY_BLOCK = 128
MIB = 1024**2


@dataclass(frozen=True)
class StreamingAndersonTailSpec:
    phase: str
    phase_index: int
    classification: str
    di_protocol_path: str
    di_manifest_path: str
    di_summary_path: str
    worker_path: str
    coefficient_report_directory: str
    evaluation_report_directory: str
    coefficient_manifest_path: str
    evaluation_manifest_path: str
    candidate_summary_path: str
    candidate_figure_path: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _small_source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if path.suffix == ".dat":
        raise RuntimeError("streaming Anderson builder refuses to read/hash .dat")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _validate_exhausted_tail(
    root: Path, spec: StreamingAndersonTailSpec
) -> tuple[dict[str, object], list[dict[str, object]]]:
    protocol = _read(root, spec.di_protocol_path)
    manifest = _read(root, spec.di_manifest_path)
    summary = _read(root, spec.di_summary_path)
    protocol_hash = _sha256(root / spec.di_protocol_path)
    records = manifest.get("iterations", [])
    decision = summary.get("decision", {})
    cfg = protocol.get("configuration", {})
    gates = protocol.get("gates", {})
    if (
        manifest.get("protocol_sha256") != protocol_hash
        or summary.get("protocol_sha256") != protocol_hash
        or manifest.get("status") != "maximum_maps_exhausted"
        or summary.get("status") != "maximum_maps_exhausted"
        or summary.get("iterations") != records
        or summary.get("completed_picard_maps") != len(records)
        or len(records) != 24
        or int(cfg.get("maximum_picard_maps", -1)) != 24
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or gates.get("each_full_map_wall_time_strictly_below_s") != 1800.0
        or decision.get("positive_picard_sequence_converged") is not False
        or decision.get("material_feedback_authorized") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
    ):
        raise RuntimeError("streaming Anderson requires exhausted 7B9di lineage")
    for index, record in enumerate(records):
        if (
            int(record.get("iteration", -1)) != index
            or record.get("progression_passed") is not True
            or record.get("convergence_passed") is not False
            or not all(record.get("progression_gate_checks", {}).values())
        ):
            raise RuntimeError("7B9di tail contains a failed progression map")
        if index and (
            record.get("input_state_path")
            != records[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != records[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("7B9di tail map chain changed")
    final = records[-1]
    if (
        float(final["global_original_operator_residual"])
        < float(gates["global_original_operator_residual_below"])
        and float(final["boundary_spectrum_l1"])
        < float(gates["global_boundary_spectrum_l1_below"])
        and float(final["boundary_bolometric_fraction"])
        < float(gates["global_boundary_bolometric_fraction_below"])
    ):
        raise RuntimeError("7B9di tail should have paused as converged")
    return protocol, records


def build_streaming_anderson_tail_protocol(
    root: Path, spec: StreamingAndersonTailSpec
) -> dict[str, object]:
    """Build a no-third-state plan; full-state bytes remain runtime claims only."""
    di, records = _validate_exhausted_tail(root, spec)
    if spec.worker_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("streaming Anderson worker path changed")
    final = records[-1]
    x23 = {
        "path": final["input_state_path"],
        "sha256": final["input_state_sha256"],
    }
    x24 = {
        "path": final["mapped_state_path"],
        "sha256": final["mapped_state_sha256"],
    }
    if x23["path"] == x24["path"]:
        raise RuntimeError("streaming Anderson requires two distinct buffers")
    size = int(di["configuration"]["raw_float64_checkpoint_size_bytes"])
    sources: dict[str, object] = {
        "exhausted_tail_protocol": _small_source(root, spec.di_protocol_path),
        "exhausted_tail_manifest": _small_source(root, spec.di_manifest_path),
        "exhausted_tail_summary": _small_source(root, spec.di_summary_path),
        "streaming_anderson_worker": _small_source(root, spec.worker_path),
        "streaming_anderson_orchestrator": _small_source(
            root, ORCHESTRATOR_RELATIVE_PATH
        ),
        "streaming_anderson_preregister_builder": _small_source(
            root, PREREGISTER_BUILDER_RELATIVE_PATH
        ),
        "streaming_anderson_dry_pass_parent": _small_source(
            root, DRY_PASS_PARENT_RELATIVE_PATH
        ),
    }
    for name, claim in di["sources"].items():
        if name in sources:
            raise RuntimeError(f"streaming Anderson source-key collision: {name}")
        current = _small_source(root, str(claim["path"]))
        if current != claim:
            raise RuntimeError(f"7B9di source changed: {claim['path']}")
        sources[name] = current
    algebraic = frozen.protected_anderson_tail_gates()
    algebraic.update(
        {
            "predicted_boundary_spectrum_ratio_to_x24_below": 1.0,
            "predicted_boundary_bolometric_ratio_to_x24_below": 1.0,
            "pass1_pass2_each_mapped_block_sha256_must_match": True,
            "pass1_pass2_block_ownership_exactly_once": True,
            "each_dry_process_peak_rss_strictly_below_mib": 6144.0,
            "each_dry_worker_wall_time_strictly_below_s": 60.0,
            "each_dry_full_map_wall_time_strictly_below_s": 1800.0,
        }
    )
    fresh = frozen.memory_safe_candidate_map_gates()
    fresh["each_worker_wall_time_strictly_below_s"] = 60.0
    work_root = Path(spec.coefficient_manifest_path).parent
    fresh_summary = Path(spec.candidate_summary_path).with_name(
        f"{Path(spec.candidate_summary_path).stem}_fresh_map.json"
    )
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {
            "x23_retained_until_all_algebraic_gates_pass": {
                **x23,
                "size_bytes": size,
            },
            "x24_retained_through_both_dry_maps": {
                **x24,
                "size_bytes": size,
            },
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "scan_frequency_chunk": SCAN_FREQUENCY_CHUNK,
            "diagnostic_frequency_block": DIAGNOSTIC_FREQUENCY_BLOCK,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "maximum_concurrent_processes": 2,
            "diagnostic_fixed_iteration_count": di["configuration"][
                "diagnostic_fixed_iteration_count"
            ],
            "spatial_scheme": di["configuration"]["spatial_scheme"],
            "source_map_only": di["configuration"]["source_map_only"],
            "x23_state_path": x23["path"],
            "x23_state_sha256": x23["sha256"],
            "x24_state_path": x24["path"],
            "x24_state_sha256": x24["sha256"],
            "x23_global_original_operator_residual": final[
                "global_original_operator_residual"
            ],
            "x23_boundary_spectrum_l1": final["boundary_spectrum_l1"],
            "x23_boundary_bolometric_fraction": final[
                "boundary_bolometric_fraction"
            ],
            "raw_float64_checkpoint_size_bytes": size,
            "coefficient_report_directory": spec.coefficient_report_directory,
            "evaluation_report_directory": spec.evaluation_report_directory,
            "coefficient_manifest_path": spec.coefficient_manifest_path,
            "evaluation_manifest_path": spec.evaluation_manifest_path,
            "candidate_summary_path": spec.candidate_summary_path,
            "candidate_figure_path": spec.candidate_figure_path,
            "runner_path": spec.worker_path,
            "orchestrator_path": ORCHESTRATOR_RELATIVE_PATH,
            "dry_pass_parent_path": DRY_PASS_PARENT_RELATIVE_PATH,
            "candidate_commit_manifest_path": str(
                work_root / "candidate_commit_manifest.json"
            ),
            "candidate_transient_backup_path": str(
                work_root / "candidate_transient_active_block.backup"
            ),
            "fresh_map_manifest_path": str(work_root / "fresh_map_manifest.json"),
            "fresh_map_report_directory": str(work_root / "fresh_map_reports"),
            "fresh_map_summary_path": str(fresh_summary),
            "candidate_output_path": x23["path"],
            "fresh_map_output_path": x24["path"],
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "kkt_regularization": False,
            "matter_feedback": False,
        },
        "coefficient_formula": {
            "f0": "x24-x23",
            "f1": "T(x24)-x24",
            "delta": "f1-f0",
            "global_inner_product": "unweighted float64 sum over all intensity cells",
            "raw_forward_fraction": "-(<f0,f1>-<f0,f0>)/<delta,delta>",
            "block_reduction_order": "group chunks of 16, increasing global group index",
        },
        "algebraic_gates": algebraic,
        "fresh_map_gates": fresh,
        "resource_gate_provenance": frozen.memory_safe_resource_provenance(),
        "execution_plan": {
            "pass1": "dry T(x24), coefficient/positivity statistics only; no buffer write",
            "pass2": "independent dry T(x24), exact predicted max-norm/positivity/boundary audit; no buffer write",
            "candidate_write": "only after all pass1/pass2 gates; overwrite x23 with x24+(s-1)(x24-x23)",
            "fresh_map": "map candidate in x23 to F(candidate) in x24",
            "additional_full_state_count": 0,
            "transport_equivalent_full_map_count": 3,
            "dry_map_count": 2,
            "fresh_residual_map_count": 1,
            "candidate_algebraic_full_state_write_count": 1,
            "dry_maps_count_as_fresh_residuals": False,
        },
        "authorization": {
            "pass1_may_write_full_state": False,
            "pass2_may_write_full_state": False,
            "preserve_x23_and_x24_until_pass2_complete": True,
            "write_candidate_only_if_all_algebraic_gates_pass": True,
            "fresh_full_original_operator_map_required": True,
            "fresh_map_maximum_concurrent_processes": 2,
            "fresh_map_wall_time_strictly_below_s": 1800.0,
            "each_dry_map_maximum_concurrent_processes": 2,
            "each_dry_map_wall_time_strictly_below_s": 1800.0,
            "predicted_metrics_are_acceptance_authority": False,
            "material_feedback_authorized": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def coefficient_block_statistics(
    x23: np.ndarray,
    x24: np.ndarray,
    mapped_x25: np.ndarray,
    *,
    global_group_start: int,
    scan_chunk: int = SCAN_FREQUENCY_CHUNK,
    mu: np.ndarray | None = None,
    weight: np.ndarray | None = None,
    frequency_width: np.ndarray | None = None,
) -> dict[str, object]:
    """Exact old-kernel chunk sums for one natural frequency block."""
    if x23.shape != x24.shape or x24.shape != mapped_x25.shape:
        raise ValueError("streaming Anderson block shapes differ")
    chunks: list[dict[str, object]] = []
    minimum_basis = np.full(3, np.inf, dtype=np.float64)
    candidate_positive_upper = np.inf
    mapped_positive_upper = np.inf
    for local_start in range(0, x23.shape[0], scan_chunk):
        local_stop = min(local_start + scan_chunk, x23.shape[0])
        a = np.asarray(x23[local_start:local_stop])
        b = np.asarray(x24[local_start:local_stop])
        c = np.asarray(mapped_x25[local_start:local_stop])
        f0 = b - a
        f1 = c - b
        delta = f1 - f0
        chunks.append(
            {
                "group_start": global_group_start + local_start,
                "group_stop": global_group_start + local_stop,
                "g00": float(np.sum(f0 * f0, dtype=np.float64)),
                "g01": float(np.sum(f0 * f1, dtype=np.float64)),
                "g11": float(np.sum(f1 * f1, dtype=np.float64)),
                "difference_squared": float(
                    np.sum(delta * delta, dtype=np.float64)
                ),
            }
        )
        minimum_basis = np.minimum(
            minimum_basis,
            np.asarray([np.min(a), np.min(b), np.min(c)], dtype=np.float64),
        )
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
    payload = {
        "scan_chunks": chunks,
        "minimum_basis_intensities": minimum_basis.tolist(),
        "candidate_positive_upper": candidate_positive_upper,
        "mapped_positive_upper": mapped_positive_upper,
        "mapped_block_sha256": hashlib.sha256(
            np.ascontiguousarray(mapped_x25).tobytes()
        ).hexdigest(),
    }
    if mu is not None and weight is not None and frequency_width is not None:
        current_flux = _block_flux(x24, mu, weight, frequency_width)
        mapped_flux = _block_flux(mapped_x25, mu, weight, frequency_width)
        payload.update(
            {
                "x24_maximum_absolute_change": float(
                    np.max(np.abs(mapped_x25 - x24))
                ),
                "x24_maximum_intensity_scale": max(
                    float(np.max(np.abs(x24))),
                    float(np.max(np.abs(mapped_x25))),
                ),
                "x24_boundary_spectrum_l1_numerator": float(
                    np.sum(np.abs(mapped_flux - current_flux))
                ),
                "x24_boundary_current_absolute_scale": float(
                    np.sum(np.abs(current_flux))
                ),
                "x24_boundary_mapped_absolute_scale": float(
                    np.sum(np.abs(mapped_flux))
                ),
                "x24_boundary_current_bolometric": float(np.sum(current_flux)),
                "x24_boundary_mapped_bolometric": float(np.sum(mapped_flux)),
            }
        )
    return payload


def aggregate_coefficient_statistics(
    reports: list[dict[str, object]],
    *,
    minimum_fraction: float = 1.0,
    maximum_fraction: float = 96.0,
) -> dict[str, object]:
    """Aggregate in the old 16-group order, preserving the frozen formula."""
    ordered = sorted(reports, key=lambda row: int(row["core_group_start"]))
    chunks = [
        chunk
        for report in ordered
        for chunk in sorted(report["scan_chunks"], key=lambda row: row["group_start"])
    ]
    g00 = g01 = g11 = difference_squared = 0.0
    for chunk in chunks:
        g00 += float(chunk["g00"])
        g01 += float(chunk["g01"])
        g11 += float(chunk["g11"])
        difference_squared += float(chunk["difference_squared"])
    if (
        not np.all(np.isfinite([g00, g01, g11, difference_squared]))
        or difference_squared <= 0.0
        or g00 <= 0.0
    ):
        raise ArithmeticError("streaming Anderson direction is unresolved")
    raw = -(g01 - g00) / difference_squared
    candidate_upper = min(float(row["candidate_positive_upper"]) for row in ordered)
    mapped_upper = min(float(row["mapped_positive_upper"]) for row in ordered)
    exact_upper = min(candidate_upper, mapped_upper)
    selected_upper = min(maximum_fraction, exact_upper)
    if np.isfinite(exact_upper) and exact_upper <= maximum_fraction:
        selected_upper = float(np.nextafter(exact_upper, 1.0))
    selected = min(max(raw, minimum_fraction), selected_upper)
    minimum_basis = np.min(
        np.asarray([row["minimum_basis_intensities"] for row in ordered]), axis=0
    )
    payload = {
        "gram": [[g00, g01], [g01, g11]],
        "difference_squared": difference_squared,
        "difference_ratio": difference_squared / g00,
        "raw_forward_fraction": raw,
        "candidate_positive_upper": candidate_upper,
        "mapped_positive_upper": mapped_upper,
        "exact_positive_upper": exact_upper,
        "selected_upper": selected_upper,
        "selected_forward_fraction": selected,
        "minimum_basis_intensities": minimum_basis.tolist(),
    }
    if all("x24_maximum_absolute_change" in row for row in ordered):
        maximum_change = max(
            float(row["x24_maximum_absolute_change"]) for row in ordered
        )
        maximum_scale = max(
            float(row["x24_maximum_intensity_scale"]) for row in ordered
        )
        boundary_numerator = sum(
            float(row["x24_boundary_spectrum_l1_numerator"]) for row in ordered
        )
        current_scale = sum(
            float(row["x24_boundary_current_absolute_scale"]) for row in ordered
        )
        mapped_scale = sum(
            float(row["x24_boundary_mapped_absolute_scale"]) for row in ordered
        )
        current_bolo = sum(
            float(row["x24_boundary_current_bolometric"]) for row in ordered
        )
        mapped_bolo = sum(
            float(row["x24_boundary_mapped_bolometric"]) for row in ordered
        )
        payload.update(
            {
                "x24_global_original_operator_residual": (
                    maximum_change / maximum_scale
                    if maximum_scale > 0.0
                    else maximum_change
                ),
                "x24_boundary_spectrum_l1": boundary_numerator
                / max(current_scale, mapped_scale),
                "x24_boundary_bolometric_fraction": abs(
                    mapped_bolo - current_bolo
                )
                / max(abs(current_bolo), abs(mapped_bolo)),
            }
        )
    return payload


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


def evaluation_block_statistics(
    x23: np.ndarray,
    x24: np.ndarray,
    mapped_x25: np.ndarray,
    selected: float,
    mu: np.ndarray,
    weight: np.ndarray,
    frequency_width: np.ndarray,
) -> dict[str, object]:
    """Evaluate the frozen candidate and predicted-map gates without writing."""
    f0 = x24 - x23
    f1 = mapped_x25 - x24
    candidate = x24 + (selected - 1.0) * f0
    predicted = mapped_x25 + (selected - 1.0) * f1
    candidate_flux = _block_flux(candidate, mu, weight, frequency_width)
    predicted_flux = _block_flux(predicted, mu, weight, frequency_width)
    change = float(np.max(np.abs(predicted - candidate)))
    scale = max(float(np.max(np.abs(candidate))), float(np.max(np.abs(predicted))))
    return {
        "maximum_absolute_change": change,
        "maximum_intensity_scale": scale,
        "minimum_candidate_intensity": float(np.min(candidate)),
        "minimum_predicted_map_intensity": float(np.min(predicted)),
        "candidate_negative_count": int(np.count_nonzero(candidate < 0.0)),
        "predicted_map_negative_count": int(np.count_nonzero(predicted < 0.0)),
        "boundary_spectrum_l1_numerator": float(
            np.sum(np.abs(predicted_flux - candidate_flux))
        ),
        "candidate_boundary_absolute_scale": float(np.sum(np.abs(candidate_flux))),
        "predicted_boundary_absolute_scale": float(np.sum(np.abs(predicted_flux))),
        "candidate_boundary_bolometric": float(np.sum(candidate_flux)),
        "predicted_boundary_bolometric": float(np.sum(predicted_flux)),
        "mapped_block_sha256": hashlib.sha256(
            np.ascontiguousarray(mapped_x25).tobytes()
        ).hexdigest(),
    }


def aggregate_evaluation_statistics(
    reports: list[dict[str, object]],
    pass1_reports: list[dict[str, object]],
) -> dict[str, object]:
    ordered = sorted(reports, key=lambda row: int(row["core_group_start"]))
    first = sorted(pass1_reports, key=lambda row: int(row["core_group_start"]))
    if (
        len(ordered) != 76
        or len(first) != 76
        or any(
            a["core_group_start"] != b["core_group_start"]
            or a["core_group_stop"] != b["core_group_stop"]
            or a["mapped_block_sha256"] != b["mapped_block_sha256"]
            for a, b in zip(first, ordered, strict=True)
        )
    ):
        raise RuntimeError("two dry maps are not blockwise reproducible")
    maximum_change = max(float(row["maximum_absolute_change"]) for row in ordered)
    maximum_scale = max(float(row["maximum_intensity_scale"]) for row in ordered)
    boundary_numerator = sum(float(row["boundary_spectrum_l1_numerator"]) for row in ordered)
    candidate_scale = sum(float(row["candidate_boundary_absolute_scale"]) for row in ordered)
    predicted_scale = sum(float(row["predicted_boundary_absolute_scale"]) for row in ordered)
    candidate_bolo = sum(float(row["candidate_boundary_bolometric"]) for row in ordered)
    predicted_bolo = sum(float(row["predicted_boundary_bolometric"]) for row in ordered)
    return {
        "predicted_global_original_operator_residual": (
            maximum_change / maximum_scale if maximum_scale > 0.0 else maximum_change
        ),
        "predicted_boundary_spectrum_l1": boundary_numerator
        / max(candidate_scale, predicted_scale),
        "predicted_boundary_bolometric_fraction": abs(predicted_bolo - candidate_bolo)
        / max(abs(candidate_bolo), abs(predicted_bolo)),
        "minimum_candidate_intensity": min(
            float(row["minimum_candidate_intensity"]) for row in ordered
        ),
        "minimum_predicted_map_intensity": min(
            float(row["minimum_predicted_map_intensity"]) for row in ordered
        ),
        "candidate_negative_count": sum(int(row["candidate_negative_count"]) for row in ordered),
        "predicted_map_negative_count": sum(
            int(row["predicted_map_negative_count"]) for row in ordered
        ),
        "pass1_pass2_block_sha256_match": True,
    }


def algebraic_gate_checks(
    protocol: dict[str, object],
    coefficient: dict[str, object],
    evaluation: dict[str, object],
) -> dict[str, bool]:
    """Apply the frozen Anderson gates plus strict boundary improvement."""
    gates = protocol["algebraic_gates"]
    x24_residual = float(coefficient["x24_global_original_operator_residual"])
    x24_boundary = float(coefficient["x24_boundary_spectrum_l1"])
    x24_bolo = float(coefficient["x24_boundary_bolometric_fraction"])
    predicted_residual = float(
        evaluation["predicted_global_original_operator_residual"]
    )
    predicted_boundary = float(evaluation["predicted_boundary_spectrum_l1"])
    predicted_bolo = float(evaluation["predicted_boundary_bolometric_fraction"])
    selected = float(coefficient["selected_forward_fraction"])
    coefficient_l1 = abs(1.0 - selected) + abs(selected)
    return {
        "basis_positive_pass": bool(
            np.all(np.asarray(coefficient["minimum_basis_intensities"]) >= 0.0)
        ),
        "resolved_slow_direction_pass": bool(
            coefficient["difference_ratio"]
            > gates["difference_norm_squared_to_x9_residual_norm_squared_above"]
        ),
        "forward_extrapolation_pass": bool(
            selected > gates["selected_forward_picard_fraction_strictly_above"]
        ),
        "coefficient_trust_pass": bool(
            coefficient_l1 < gates["coefficient_l1_norm_strictly_below"]
        ),
        "candidate_and_predicted_map_positive_pass": bool(
            evaluation["candidate_negative_count"] == 0
            and evaluation["predicted_map_negative_count"] == 0
            and evaluation["minimum_candidate_intensity"]
            >= gates["minimum_candidate_and_predicted_map_intensity_at_least"]
            and evaluation["minimum_predicted_map_intensity"]
            >= gates["minimum_candidate_and_predicted_map_intensity_at_least"]
        ),
        "predicted_maximum_norm_improvement_pass": bool(
            x24_residual > 0.0
            and predicted_residual / x24_residual
            < gates["predicted_global_residual_ratio_to_x10_below"]
        ),
        "boundary_absolute_pass": bool(
            predicted_boundary < gates["global_boundary_spectrum_l1_below"]
            and predicted_bolo < gates["global_boundary_bolometric_fraction_below"]
        ),
        "boundary_improvement_pass": bool(
            x24_boundary > 0.0
            and x24_bolo > 0.0
            and predicted_boundary / x24_boundary
            < gates["predicted_boundary_spectrum_ratio_to_x24_below"]
            and predicted_bolo / x24_bolo
            < gates["predicted_boundary_bolometric_ratio_to_x24_below"]
        ),
        "two_dry_maps_reproducible_pass": bool(
            evaluation["pass1_pass2_block_sha256_match"] is True
        ),
    }


def _load_runtime_protocol(path: Path, expected_hash: str) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(path) != expected_hash:
        raise RuntimeError("frozen streaming Anderson protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol["configuration"]["runner_path"] != RUNNER_RELATIVE_PATH:
        raise RuntimeError("streaming Anderson runtime path changed")
    for source in protocol["sources"].values():
        current = ROOT / source["path"]
        if current.stat().st_size != source["size_bytes"] or _sha256(current) != source["sha256"]:
            raise RuntimeError(f"streaming Anderson source changed: {source['path']}")
    return protocol


def _solve_dry_mapped_block(
    protocol: dict[str, object], protocol_path: Path, block_index: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int]:
    """Evaluate T(x24) for one block without opening either buffer for writing."""
    generic = sequence.generic
    cfg = protocol["configuration"]
    x23_path = ROOT / cfg["x23_state_path"]
    x24_path = ROOT / cfg["x24_state_path"]
    finite = json.loads(
        (ROOT / protocol["sources"]["finite_trial_protocol"]["path"]).read_text()
    )
    generic.base.phase7b9d._configure_worker(finite, x24_path)
    template = generic.base.phase7b7i._load_protocol(
        protocol_path, validate_sources=False
    )
    context = generic.base.phase7b7i.phase7b7e.phase7b5x._context(template)
    block = context["blocks"][block_index]
    material = generic.base.phase7b7i._second_full_material(template)
    fields = generic.base.phase7b7i.phase7b7e._local_fields(
        context, block, material
    )
    shape = (
        int(cfg["physical_frequency_groups"]),
        int(cfg["angular_direction_count"]),
        int(cfg["radiation_depth_cell_count"]),
    )
    x23_global = np.memmap(x23_path, mode="r", dtype=np.float64, shape=shape)
    x24_global = np.memmap(x24_path, mode="r", dtype=np.float64, shape=shape)
    full_start = int(context["stencil"].active_outer_group_start)
    full_stop = int(context["stencil"].active_outer_group_stop)
    physical_start = max(block.outer_group_start, full_start)
    physical_stop = min(block.outer_group_stop, full_stop)
    if physical_stop > physical_start:
        fields["outer"][
            physical_start - block.outer_group_start : physical_stop - block.outer_group_start
        ] = x24_global[
            physical_start - full_start : physical_stop - full_start
        ]
    core = slice(block.core_group_start, block.core_group_stop)
    x23 = np.array(x23_global[core], copy=True)
    x24 = np.array(x24_global[core], copy=True)
    result = generic.base.phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
        block.local_stencil,
        fields["old_edge"],
        fields["new_edge"],
        context["mu"],
        context["weight"],
        fields["initial"],
        fields["outer"],
        fields["true_absorption"],
        fields["thermal_emissivity"],
        fields["scattering"],
        context["beta"],
        context["duration_s"],
        propagation_speed_cm_s=generic.base.phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
        source_iteration_initial_guess=x24,
        diagnostic_fixed_iteration_count=int(cfg["diagnostic_fixed_iteration_count"]),
        spatial_scheme=cfg["spatial_scheme"],
        source_map_only=bool(cfg["source_map_only"]),
    )
    mapped = np.array(result.final_lab_intensity_density, copy=True)
    if not np.all(np.isfinite(mapped)) or np.any(mapped < 0.0):
        raise ArithmeticError("dry-map output is not finite/nonnegative")
    with np.load(ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]) as master:
        width = np.diff(np.asarray(master["active_edge_hz"]))[core]
    mu = np.asarray(context["mu"])
    weight = np.asarray(context["weight"])
    start = int(block.core_group_start)
    stop = int(block.core_group_stop)
    del result, fields, material, x23_global, x24_global
    gc.collect()
    return x23, x24, mapped, mu, weight, width, start, stop


def run_dry_worker(
    protocol_path: Path,
    expected_hash: str,
    pass_index: int,
    block_index: int,
    report_path: Path,
    selected_forward_fraction: float | None,
) -> dict[str, object]:
    protocol = _load_runtime_protocol(protocol_path, expected_hash)
    started = time.perf_counter()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    x23, x24, mapped, mu, weight, width, start, stop = _solve_dry_mapped_block(
        protocol, protocol_path, block_index
    )
    if pass_index == 1:
        payload = coefficient_block_statistics(
            x23,
            x24,
            mapped,
            global_group_start=start,
            mu=mu,
            weight=weight,
            frequency_width=width,
        )
    elif pass_index == 2 and selected_forward_fraction is not None:
        payload = evaluation_block_statistics(
            x23, x24, mapped, selected_forward_fraction, mu, weight, width
        )
    else:
        raise ValueError("dry worker pass must be 1, or pass 2 with frozen fraction")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = MIB if sys.platform == "darwin" else MIB / 1024
    report = {
        "protocol_sha256": expected_hash,
        "pass_index": pass_index,
        "block_index": block_index,
        "core_group_start": start,
        "core_group_stop": stop,
        "x23_state_sha256": protocol["configuration"]["x23_state_sha256"],
        "x24_state_sha256": protocol["configuration"]["x24_state_sha256"],
        "baseline_highwater_rss_mib": baseline / scale,
        "peak_process_rss_mib": peak / scale,
        "wall_runtime_s": time.perf_counter() - started,
        "full_state_write_performed": False,
        **payload,
    }
    _write_json_atomic(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--pass-index", required=True, type=int)
    parser.add_argument("--block-index", required=True, type=int)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--selected-forward-fraction", type=float)
    args = parser.parse_args()
    run_dry_worker(
        args.protocol,
        args.expected_protocol_sha256,
        args.pass_index,
        args.block_index,
        args.report,
        args.selected_forward_fraction,
    )


if __name__ == "__main__":
    main()
