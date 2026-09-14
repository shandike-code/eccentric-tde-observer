"""Phase 7B9di：从 7B9dh bootstrap map 继续固定物质辐射迭代。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
    from scripts import phase7b9_half_trial_radiation_continuation as storage
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]
    import phase7b9_half_trial_radiation_continuation as storage  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9di_progression_continuation.py"
MATERIAL_RELAXATION = 0.0625


@dataclass(frozen=True)
class ProgressionContinuationSpec:
    phase: str
    phase_index: int
    classification: str
    dh_protocol_path: str
    dh_manifest_path: str
    dh_summary_path: str
    dh_initialization_receipt_path: str
    runner_path: str
    manifest_path: str
    transient_report_directory: str
    summary_path: str
    figure_path: str


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if path.suffix == ".dat":
        raise RuntimeError("7B9di builder refuses to read or hash full-state .dat")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _read(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _only_boundary_failed(record: dict[str, object]) -> bool:
    checks = record.get("gate_checks", {})
    required = {
        "frequency_ownership_pass",
        "positive_map_pass",
        "initial_reproduction_pass",
        "contraction_pass",
        "boundary_pass",
        "resources_pass",
    }
    return bool(
        set(checks) == required
        and checks["boundary_pass"] is False
        and all(checks[name] is True for name in required - {"boundary_pass"})
        and record.get("map_passed") is False
    )


def _seed_progression_checks(record: dict[str, object]) -> dict[str, bool]:
    checks = record["gate_checks"]
    return {
        "frequency_ownership_pass": checks["frequency_ownership_pass"] is True,
        "positive_map_pass": checks["positive_map_pass"] is True,
        "resources_pass": checks["resources_pass"] is True,
        # 中文：bootstrap 首图没有前一残差，收缩门不适用但不能据此阻止续算。
        "contraction_pass": record.get("contraction_ratio") is None,
    }


def _validate_dh_seed(
    root: Path, spec: ProgressionContinuationSpec
) -> tuple[dict[str, object], dict[str, object]]:
    protocol = _read(root, spec.dh_protocol_path)
    manifest = _read(root, spec.dh_manifest_path)
    summary = _read(root, spec.dh_summary_path)
    receipt = _read(root, spec.dh_initialization_receipt_path)
    protocol_hash = _sha256(root / spec.dh_protocol_path)
    records = manifest.get("iterations", [])
    if (
        manifest.get("protocol_sha256") != protocol_hash
        or summary.get("protocol_sha256") != protocol_hash
        or receipt.get("protocol_sha256") != protocol_hash
        or manifest.get("status") != "gate_failed"
        or summary.get("status") != "gate_failed"
        or receipt.get("status") != "complete"
        or len(records) != 1
        or summary.get("iterations") != records
    ):
        raise RuntimeError("7B9dh bootstrap lineage changed")
    record = records[0]
    if (
        int(record.get("iteration", -1)) != 0
        or not _only_boundary_failed(record)
        or record.get("initial_reproduction_applicable") is not False
        or record.get("input_state_path")
        != protocol["configuration"]["initial_state_path"]
        or record.get("input_state_sha256")
        != protocol["configuration"]["initial_state_sha256"]
        or record.get("mapped_state_path")
        != protocol["configuration"]["scratch_state_path"]
        or receipt.get("buffer_a_path") != record.get("input_state_path")
        or receipt.get("buffer_a_postcopy_sha256")
        != record.get("input_state_sha256")
        or receipt.get("buffer_b_path") != record.get("mapped_state_path")
        or receipt.get("protected_source_modified") is not False
        or protocol["configuration"].get("material_candidate_absolute_relaxation")
        != MATERIAL_RELAXATION
    ):
        raise RuntimeError("7B9dh bootstrap is not boundary-only progression eligible")
    progression = _seed_progression_checks(record)
    if not all(progression.values()):
        raise RuntimeError("7B9dh bootstrap progression gate failed")
    if (
        float(record["global_original_operator_residual"])
        < float(protocol["gates"]["global_original_operator_residual_below"])
        and float(record["boundary_spectrum_l1"])
        < float(protocol["gates"]["global_boundary_spectrum_l1_below"])
        and float(record["boundary_bolometric_fraction"])
        < float(protocol["gates"]["global_boundary_bolometric_fraction_below"])
    ):
        raise RuntimeError("7B9dh bootstrap was already converged")
    seed = json.loads(json.dumps(record))
    seed.update(
        {
            "original_map_passed": False,
            "progression_gate_checks": progression,
            "progression_passed": True,
            "convergence_gate_checks": {
                "residual_pass": False,
                "boundary_spectrum_pass": False,
                "boundary_bolometric_pass": False,
            },
            "convergence_passed": False,
            "progression_classification": (
                "bootstrap_nonconverged/progression_eligible"
            ),
        }
    )
    return protocol, seed


def build_progression_continuation_protocol(
    root: Path, spec: ProgressionContinuationSpec
) -> dict[str, object]:
    """Freeze a B-to-A continuation without opening either full-state buffer."""
    dh, seed = _validate_dh_seed(root, spec)
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9di runner path changed")
    sources: dict[str, object] = {
        "phase7b9dh_protocol": _source(root, spec.dh_protocol_path),
        "phase7b9dh_manifest": _source(root, spec.dh_manifest_path),
        "phase7b9dh_summary": _source(root, spec.dh_summary_path),
        "phase7b9dh_initialization_receipt": _source(
            root, spec.dh_initialization_receipt_path
        ),
        "progression_continuation_runner": _source(root, spec.runner_path),
    }
    # 中文：递归冻结 dh 的小型依赖，但全态检查点只保留声明，不在 builder 中读取。
    for name, claim in dh["sources"].items():
        current = _source(root, str(claim["path"]))
        if current != claim:
            raise RuntimeError(f"7B9dh source changed: {claim['path']}")
        sources[name] = current
    configuration = json.loads(json.dumps(dh["configuration"]))
    configuration.update(
        {
            "phase_index": spec.phase_index,
            "maximum_picard_maps": 24,
            "seed_completed_picard_maps": 1,
            "maximum_concurrent_processes": 2,
            "initial_state_path": seed["mapped_state_path"],
            "initial_state_sha256": seed["mapped_state_sha256"],
            "scratch_state_path": seed["input_state_path"],
            "scratch_state_initial_sha256": seed["input_state_sha256"],
            "manifest_path": spec.manifest_path,
            "report_directory": spec.transient_report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            "initial_reference_mode": "continued_after_bootstrap",
            "copy_or_initialize_full_state": False,
        }
    )
    configuration.pop("initialization_receipt_path", None)
    gates = json.loads(json.dumps(dh["gates"]))
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {
            "buffer_a_next_output": {
                "path": seed["input_state_path"],
                "size_bytes": configuration["raw_float64_checkpoint_size_bytes"],
                "sha256": seed["input_state_sha256"],
            },
            "buffer_b_current_input": {
                "path": seed["mapped_state_path"],
                "size_bytes": configuration["raw_float64_checkpoint_size_bytes"],
                "sha256": seed["mapped_state_sha256"],
            },
        },
        "configuration": configuration,
        "reference": json.loads(json.dumps(dh["reference"])),
        "gates": gates,
        "progression_gate_definition": {
            "frequency_ownership_exact": True,
            "minimum_input_and_mapped_intensity_at_least": gates[
                "minimum_input_and_mapped_intensity_at_least"
            ],
            "subsequent_residual_contraction_ratio_below": gates[
                "subsequent_residual_contraction_ratio_below"
            ],
            "each_process_peak_rss_strictly_below_mib": gates[
                "each_process_peak_rss_strictly_below_mib"
            ],
            "each_worker_wall_time_strictly_below_s": gates[
                "each_worker_wall_time_strictly_below_s"
            ],
            "each_full_map_wall_time_strictly_below_s": gates[
                "each_full_map_wall_time_strictly_below_s"
            ],
        },
        "convergence_gate_definition": {
            "global_original_operator_residual_below": gates[
                "global_original_operator_residual_below"
            ],
            "global_boundary_spectrum_l1_below": gates[
                "global_boundary_spectrum_l1_below"
            ],
            "global_boundary_bolometric_fraction_below": gates[
                "global_boundary_bolometric_fraction_below"
            ],
        },
        "seed_iteration": seed,
        "storage_plan": {
            "buffer_a_role": "next output after dh map0, then alternating",
            "buffer_b_role": "current dh mapped input, then alternating",
            "additional_full_state_allocation_count": 0,
            "copy_initial_source": False,
            "single_stage_owned_transient_report_directory": True,
            "block_reports_compacted_after_each_committed_map": True,
        },
        "authorization": {
            "continue_only_if_progression_gate_passes": True,
            "pause_only_if_full_convergence_gate_passes": True,
            "boundary_failure_alone_blocks_progression": False,
            "overwrite_only_buffer_a_and_buffer_b": True,
            "recopy_protected_initial_source": False,
            "delete_only_stage_owned_transient_reports": True,
            "provisional_feedback_is_acceptance_authority": False,
            "formal_pair_only_after_next_consecutive_fresh_residual": True,
            "material_feedback_before_formal_pair": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def write_protocol(
    root: Path,
    spec: ProgressionContinuationSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_progression_continuation_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, _sha256(output_path)


def _load_runtime_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen 7B9di protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["configuration"].get("runner_path") != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9di runtime runner changed")
    for source in protocol["sources"].values():
        path = root / source["path"]
        if (
            path.stat().st_size != int(source["size_bytes"])
            or _sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"7B9di source changed: {source['path']}")
    return protocol


def initialize_progression_manifest(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    """Verify the dh-produced B and untouched A before any continuation write."""
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if manifest_path.exists():
        manifest = _read(root, str(cfg["manifest_path"]))
        if manifest.get("protocol_sha256") != expected_hash:
            raise RuntimeError("7B9di manifest belongs to another protocol")
        current = root / manifest["current_input_path"]
        output = root / manifest["next_output_path"]
        if current.stat().st_size != expected_size or output.stat().st_size != expected_size:
            raise RuntimeError("7B9di recovery buffer size changed")
        if _sha256(current) != manifest["current_input_sha256"]:
            raise RuntimeError("7B9di recovery current input changed")
        if manifest.get("active_iteration") is None and (
            _sha256(output) != manifest["next_output_sha256"]
        ):
            raise RuntimeError("7B9di recovery next output changed")
        return manifest
    current = root / cfg["initial_state_path"]
    output = root / cfg["scratch_state_path"]
    if (
        current.stat().st_size != expected_size
        or output.stat().st_size != expected_size
        or _sha256(current) != cfg["initial_state_sha256"]
        or _sha256(output) != cfg["scratch_state_initial_sha256"]
    ):
        raise RuntimeError("7B9di initial A/B bytes changed")
    # 中文：直接从 dh 产出的 B 续算；绝不重新复制受保护初猜到 A。
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "next_output_sha256": cfg["scratch_state_initial_sha256"],
        "iterations": [protocol["seed_iteration"]],
        "active_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _progression_checks(
    gates: dict[str, object], metrics: dict[str, object], contraction: float | None
) -> dict[str, bool]:
    return {
        "frequency_ownership_pass": bool(
            metrics["block_report_count"] == gates["block_count_exactly"]
            and metrics["frequency_ownership_count"] == gates["owned_frequency_group_count_exactly"]
            and metrics["frequency_ownership_exact"]
        ),
        "positive_map_pass": bool(
            metrics["minimum_input_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
            and metrics["minimum_mapped_intensity"]
            >= gates["minimum_input_and_mapped_intensity_at_least"]
        ),
        "contraction_pass": bool(
            contraction is not None
            and contraction < gates["subsequent_residual_contraction_ratio_below"]
        ),
        "resources_pass": bool(
            metrics["maximum_process_peak_rss_mib"]
            < gates["each_process_peak_rss_strictly_below_mib"]
            and metrics["maximum_worker_wall_runtime_s"]
            < gates["each_worker_wall_time_strictly_below_s"]
            and metrics["full_map_wall_runtime_s"]
            < gates["each_full_map_wall_time_strictly_below_s"]
        ),
    }


def _convergence_checks(
    gates: dict[str, object], metrics: dict[str, object]
) -> dict[str, bool]:
    return {
        "residual_pass": bool(
            metrics["global_original_operator_residual"]
            < gates["global_original_operator_residual_below"]
        ),
        "boundary_spectrum_pass": bool(
            metrics["boundary_spectrum_l1"]
            < gates["global_boundary_spectrum_l1_below"]
        ),
        "boundary_bolometric_pass": bool(
            metrics["boundary_bolometric_fraction"]
            < gates["global_boundary_bolometric_fraction_below"]
        ),
    }


def _summary(
    protocol: dict[str, object], manifest: dict[str, object], expected_hash: str
) -> dict[str, object]:
    cfg = protocol["configuration"]
    records = manifest["iterations"]
    figure = ROOT / cfg["figure_path"]
    if records:
        engine._plot(figure, records)
    converged = manifest["status"] == "complete"
    payload = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V-progression]+[O]",
        "protocol_sha256": expected_hash,
        "status": manifest["status"],
        "completed_picard_maps": len(records),
        "residual_history": [row["global_original_operator_residual"] for row in records],
        "contraction_ratio_history": [row["contraction_ratio"] for row in records],
        "boundary_spectrum_l1_history": [row["boundary_spectrum_l1"] for row in records],
        "accepted_state_path": manifest.get("accepted_state_path"),
        "accepted_state_sha256": manifest.get("accepted_state_sha256"),
        "iterations": records,
        "decision": {
            "positive_picard_sequence_converged": converged,
            "first_low_residual_and_boundary_input_audited": converged,
            "provisional_feedback_extraction_authorized": converged,
            "provisional_feedback_is_formal_pair_authority": False,
            "next_consecutive_fresh_residual_required": converged,
            "formal_h_he_feedback_pair_authorized": False,
            "material_feedback_authorized": False,
            "dynamic_nlte_solution_accepted": False,
        },
        "figures": [figure.name] if records else [],
    }
    if converged:
        final = records[-1]
        payload.update(
            {
                "first_low_residual_input_path": final["input_state_path"],
                "first_low_residual_input_sha256": final["input_state_sha256"],
                "next_consecutive_input_path": final["mapped_state_path"],
                "next_consecutive_input_sha256": final["mapped_state_sha256"],
            }
        )
    _write_json_atomic(ROOT / cfg["summary_path"], payload)
    return payload


def _run_worker(
    protocol_path: Path,
    expected_hash: str,
    iteration: int,
    block_index: int,
    input_state: Path,
    input_sha256: str,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_runtime_protocol(ROOT, protocol_path, expected_hash)
    fixed = _read(ROOT, protocol["sources"]["finite_trial_protocol"]["path"])
    if fixed["sources"]["current_material_state"] != protocol["sources"]["finite_trial_material"]:
        raise RuntimeError("7B9di fixed-material worker source changed")
    generic = engine.generic
    original = generic.base.phase7b9i._load_protocol
    try:
        generic.base.phase7b9i._load_protocol = lambda _path, validate_sources=False: fixed
        engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
        generic.EXPECTED_PROTOCOL_SHA256 = expected_hash
        engine._run_worker(
            protocol_path,
            iteration,
            block_index,
            input_state,
            input_sha256,
            output_state,
            report_path,
        )
    finally:
        generic.base.phase7b9i._load_protocol = original


def _run_one_map(
    protocol_path: Path,
    protocol: dict[str, object],
    expected_hash: str,
    manifest: dict[str, object],
) -> dict[str, object]:
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = engine._shape(protocol)
    manifest_path = ROOT / cfg["manifest_path"]
    iteration = len(manifest["iterations"])
    input_state = ROOT / manifest["current_input_path"]
    output_state = ROOT / manifest["next_output_path"]
    active = manifest.get("active_iteration")
    if active is None:
        active = {
            "iteration": iteration,
            "input_state_path": str(input_state.resolve().relative_to(ROOT)),
            "input_state_sha256": manifest["current_input_sha256"],
            "output_state_path": str(output_state.resolve().relative_to(ROOT)),
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        manifest["active_iteration"] = active
        _write_json_atomic(manifest_path, manifest)
    if (
        active["iteration"] != iteration
        or active["input_state_path"] != manifest["current_input_path"]
        or active["input_state_sha256"] != manifest["current_input_sha256"]
        or active["output_state_path"] != manifest["next_output_path"]
    ):
        raise RuntimeError("7B9di active map lineage changed")
    completed = {int(row["block_index"]): row for row in active["completed_blocks"]}
    for row in completed.values():
        digest = engine.base.phase7b9d._block_sha256(
            output_state,
            shape,
            int(row["core_group_start"]),
            int(row["core_group_stop"]),
        )
        if digest != row["output_block_sha256"]:
            raise RuntimeError("7B9di completed output block changed")
    pending = [index for index in range(76) if index not in completed]
    report_root = storage._transient_root(ROOT, protocol, expected_hash)
    report_dir = report_root / f"iteration_{iteration:02d}"
    report_dir.mkdir(parents=True, exist_ok=True)
    concurrency = int(cfg["maximum_concurrent_processes"])
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        paths = [report_dir / f"phase7b9di_block{index:02d}.json" for index in batch]
        started = time.perf_counter()
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / cfg["runner_path"]),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--expected-protocol-sha256",
                    expected_hash,
                    "--iteration",
                    str(iteration),
                    "--block-index",
                    str(index),
                    "--input-state",
                    str(input_state),
                    "--input-sha256",
                    str(manifest["current_input_sha256"]),
                    "--output-state",
                    str(output_state),
                    "--worker-report",
                    str(path),
                ],
                cwd=ROOT,
            )
            for index, path in zip(batch, paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"7B9di worker batch failed: {codes}")
        for index, path in zip(batch, paths, strict=True):
            row = json.loads(path.read_text(encoding="utf-8"))
            if (
                row.get("protocol_sha256") != expected_hash
                or row.get("block_index") != index
                or row.get("picard_iteration") != iteration
            ):
                raise RuntimeError("7B9di worker report changed")
            row["output_block_sha256"] = engine.base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            active["completed_blocks"].append(row)
        active["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        active["accumulated_wall_runtime_s"] += time.perf_counter() - started
        _write_json_atomic(manifest_path, manifest)
    reports = list(active["completed_blocks"])
    metrics = engine._aggregate(reports, shape)
    metrics["block_report_count"] = len(reports)
    metrics["full_map_wall_runtime_s"] = float(active["accumulated_wall_runtime_s"])
    previous_residual = float(manifest["iterations"][-1]["global_original_operator_residual"])
    contraction = float(metrics["global_original_operator_residual"]) / previous_residual
    progression_checks = _progression_checks(gates, metrics, contraction)
    convergence_checks = _convergence_checks(gates, metrics)
    progression_passed = all(progression_checks.values())
    convergence_passed = progression_passed and all(convergence_checks.values())
    boundary_passed = bool(
        convergence_checks["boundary_spectrum_pass"]
        and convergence_checks["boundary_bolometric_pass"]
    )
    output_hash = _sha256(output_state)
    record = {
        "iteration": iteration,
        "input_state_path": manifest["current_input_path"],
        "input_state_sha256": manifest["current_input_sha256"],
        "mapped_state_path": manifest["next_output_path"],
        "mapped_state_sha256": output_hash,
        **metrics,
        "contraction_ratio": contraction,
        "initial_reproduction_applicable": False,
        "gate_checks": {
            "frequency_ownership_pass": progression_checks["frequency_ownership_pass"],
            "positive_map_pass": progression_checks["positive_map_pass"],
            "initial_reproduction_pass": True,
            "contraction_pass": progression_checks["contraction_pass"],
            "boundary_pass": boundary_passed,
            "resources_pass": progression_checks["resources_pass"],
        },
        "original_map_passed": bool(
            progression_passed and boundary_passed
        ),
        "progression_gate_checks": progression_checks,
        "progression_passed": progression_passed,
        "convergence_gate_checks": convergence_checks,
        "convergence_passed": convergence_passed,
        "map_passed": convergence_passed,
        "reports": reports,
    }
    manifest["iterations"].append(record)
    manifest["active_iteration"] = None
    if convergence_passed:
        manifest["status"] = "complete"
        manifest["accepted_state_path"] = manifest["current_input_path"]
        manifest["accepted_state_sha256"] = manifest["current_input_sha256"]
        manifest["next_output_sha256"] = output_hash
    elif not progression_passed:
        manifest["status"] = "gate_failed"
        manifest["next_output_sha256"] = output_hash
    elif len(manifest["iterations"]) >= int(cfg["maximum_picard_maps"]):
        manifest["status"] = "maximum_maps_exhausted"
        manifest["next_output_sha256"] = output_hash
    else:
        prior_input_path = manifest["current_input_path"]
        prior_input_hash = manifest["current_input_sha256"]
        manifest["current_input_path"] = manifest["next_output_path"]
        manifest["current_input_sha256"] = output_hash
        manifest["next_output_path"] = prior_input_path
        manifest["next_output_sha256"] = prior_input_hash
    _write_json_atomic(manifest_path, manifest)
    return manifest


def run_progression(
    protocol_path: Path,
    expected_hash: str,
    *,
    stop_after_iteration: int | None = None,
) -> dict[str, object]:
    protocol = _load_runtime_protocol(ROOT, protocol_path, expected_hash)
    manifest = initialize_progression_manifest(ROOT, protocol_path, expected_hash)
    storage._transient_root(ROOT, protocol, expected_hash)
    while manifest["status"] == "running":
        manifest = _run_one_map(protocol_path, protocol, expected_hash, manifest)
        manifest = storage.compact_committed_reports(ROOT, protocol, expected_hash)
        summary = _summary(protocol, manifest, expected_hash)
        if stop_after_iteration is not None and len(manifest["iterations"]) - 1 >= stop_after_iteration:
            return summary
    return _summary(protocol, manifest, expected_hash)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    args = parser.parse_args()
    if args.worker:
        required = (
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        if any(value is None for value in required):
            raise ValueError("worker mode requires iteration, block and both states")
        _run_worker(
            args.protocol,
            args.expected_protocol_sha256,
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    run_progression(
        args.protocol,
        args.expected_protocol_sha256,
        stop_after_iteration=args.stop_after_iteration,
    )


if __name__ == "__main__":
    main()
