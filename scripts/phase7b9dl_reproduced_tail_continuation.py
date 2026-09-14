"""Phase 7B9dl：以 dk fresh reproduction 替换被拒绝的 di iteration 20 后续算。"""

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
from typing import Callable

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
    from scripts import phase7b9_half_trial_radiation_continuation as storage
    from scripts import phase7b9di_progression_continuation as di
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]
    import phase7b9_half_trial_radiation_continuation as storage  # type: ignore[no-redef]
    import phase7b9di_progression_continuation as di  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9dl_reproduced_tail_continuation.py"
FRESH_CURRENT_SHA256 = (
    "c58861b3039bc2dd0141114cbce012180323147b4316ce3dc57debdf886443f6"
)
IMMUTABLE_SCRATCH_SHA256 = (
    "e2d718bd509e28a30f488babcb3ecff6adc612bfa0509f7161073400ffd4bf6f"
)


@dataclass(frozen=True)
class ReproducedTailContinuationSpec:
    phase: str
    phase_index: int
    classification: str
    di_protocol_path: str
    di_manifest_path: str
    di_summary_path: str
    dk_protocol_path: str
    dk_manifest_path: str
    dk_summary_path: str
    runner_path: str
    manifest_path: str
    transient_report_directory: str
    summary_path: str
    figure_path: str
    fresh_current_sha256: str = FRESH_CURRENT_SHA256
    immutable_scratch_sha256: str = IMMUTABLE_SCRATCH_SHA256


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _small_source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if path.suffix == ".dat":
        raise RuntimeError("7B9dl builder refuses to read or hash full-state .dat")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _valid_progression_record(record: dict[str, object], index: int) -> bool:
    return bool(
        int(record.get("iteration", -1)) == index
        and record.get("progression_passed") is True
        and record.get("convergence_passed") is False
        and all(record.get("progression_gate_checks", {}).values())
    )


def _validate_di_history(
    root: Path, spec: ReproducedTailContinuationSpec
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    protocol = _read(root, spec.di_protocol_path)
    manifest = _read(root, spec.di_manifest_path)
    summary = _read(root, spec.di_summary_path)
    protocol_sha = _sha256(root / spec.di_protocol_path)
    records = manifest.get("iterations", [])
    if (
        manifest.get("protocol_sha256") != protocol_sha
        or summary.get("protocol_sha256") != protocol_sha
        or manifest.get("status") != "gate_failed"
        or summary.get("status") != "gate_failed"
        or manifest.get("active_iteration") is not None
        or summary.get("iterations") != records
        or len(records) != 21
        or int(protocol["configuration"].get("maximum_picard_maps", -1)) != 24
    ):
        raise RuntimeError("7B9dl 7B9di small-file lineage changed")
    valid = records[:20]
    for index, record in enumerate(valid):
        if not _valid_progression_record(record, index):
            raise RuntimeError("7B9dl 7B9di valid prefix contains a failed map")
        if index and (
            record.get("input_state_path") != valid[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != valid[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("7B9dl 7B9di valid prefix chain changed")
    rejected = records[20]
    progression = rejected.get("progression_gate_checks", {})
    if (
        int(rejected.get("iteration", -1)) != 20
        or rejected.get("progression_passed") is not False
        or progression.get("contraction_pass") is not False
        or any(
            progression.get(name) is not True
            for name in (
                "frequency_ownership_pass",
                "positive_map_pass",
                "resources_pass",
            )
        )
    ):
        raise RuntimeError("7B9dl expected the contraction-only rejected di map20")
    return protocol, valid, rejected


def _validate_dk_reproduction(
    root: Path,
    spec: ReproducedTailContinuationSpec,
    di_valid: list[dict[str, object]],
    rejected: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    protocol = _read(root, spec.dk_protocol_path)
    manifest = _read(root, spec.dk_manifest_path)
    summary = _read(root, spec.dk_summary_path)
    protocol_sha = _sha256(root / spec.dk_protocol_path)
    metrics = summary.get("metrics", {})
    progression = summary.get("progression_gate_checks", {})
    convergence = summary.get("convergence_gate_checks", {})
    decision = summary.get("decision", {})
    if (
        manifest.get("protocol_sha256") != protocol_sha
        or summary.get("protocol_sha256") != protocol_sha
        or manifest.get("status") != "reproduction_passed"
        or summary.get("status") != "reproduction_passed"
        or manifest.get("reproduction_passed") is not True
        or decision.get("full_76_block_reproduction_passed") is not True
        or decision.get("fresh_state_authorized_as_continuation_input") is not True
        or summary.get("block_report_count") != 76
        or not all(progression.values())
        or convergence.get("residual_pass") is not False
        or convergence.get("boundary_spectrum_pass") is not True
        or convergence.get("boundary_bolometric_pass") is not True
    ):
        raise RuntimeError("7B9dl 7B9dk full reproduction did not pass")
    prior = di_valid[-1]
    if (
        summary.get("immutable_input_path") != prior.get("mapped_state_path")
        or summary.get("immutable_input_sha256") != prior.get("mapped_state_sha256")
        or summary.get("immutable_input_sha256") != spec.immutable_scratch_sha256
        or summary.get("fresh_output_path") != rejected.get("mapped_state_path")
        or summary.get("fresh_output_sha256") != spec.fresh_current_sha256
        or summary.get("failed_output_previous_sha256")
        != rejected.get("mapped_state_sha256")
    ):
        raise RuntimeError("7B9dl reproduced map20 A/B lineage changed")
    return protocol, summary, metrics


def _reproduced_iteration20(
    summary: dict[str, object], metrics: dict[str, object]
) -> dict[str, object]:
    progression = dict(summary["progression_gate_checks"])
    convergence = dict(summary["convergence_gate_checks"])
    boundary_pass = bool(
        convergence["boundary_spectrum_pass"]
        and convergence["boundary_bolometric_pass"]
    )
    return {
        "iteration": 20,
        "input_state_path": summary["immutable_input_path"],
        "input_state_sha256": summary["immutable_input_sha256"],
        "mapped_state_path": summary["fresh_output_path"],
        "mapped_state_sha256": summary["fresh_output_sha256"],
        **metrics,
        "gate_checks": {
            "frequency_ownership_pass": progression["frequency_ownership_pass"],
            "positive_map_pass": progression["positive_map_pass"],
            "initial_reproduction_pass": True,
            "contraction_pass": progression["contraction_pass"],
            "boundary_pass": boundary_pass,
            "resources_pass": progression["resources_pass"],
        },
        "original_map_passed": bool(all(progression.values()) and boundary_pass),
        "progression_gate_checks": progression,
        "progression_passed": True,
        "convergence_gate_checks": convergence,
        "convergence_passed": False,
        "map_passed": False,
        "reproduction_classification": "fresh_full_76_block_reproduction",
        "block_report_audit": {
            "record_count": 76,
            "block_indices": list(range(76)),
            "full_reports_retained_in_phase7b9dk": True,
        },
    }


def build_reproduced_tail_protocol(
    root: Path, spec: ReproducedTailContinuationSpec
) -> dict[str, object]:
    di_protocol, valid_prefix, rejected = _validate_di_history(root, spec)
    _, dk_summary, metrics = _validate_dk_reproduction(
        root, spec, valid_prefix, rejected
    )
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9dl runner path changed")
    reproduced = _reproduced_iteration20(dk_summary, metrics)
    valid_history = [*valid_prefix, reproduced]
    cfg = di_protocol["configuration"]
    gates = dict(di_protocol["gates"])
    if (
        cfg.get("maximum_concurrent_processes") != 2
        or gates.get("each_full_map_wall_time_strictly_below_s") != 1800.0
    ):
        raise RuntimeError("7B9dl frozen 2-worker/1800-s resource gate changed")
    sources = dict(di_protocol["sources"])
    if any(Path(str(row["path"])).suffix == ".dat" for row in sources.values()):
        raise RuntimeError("7B9dl inherited source pins include a full-state dat")
    sources.update(
        {
            "phase7b9di_protocol": _small_source(root, spec.di_protocol_path),
            "phase7b9di_manifest": _small_source(root, spec.di_manifest_path),
            "phase7b9di_summary": _small_source(root, spec.di_summary_path),
            "phase7b9dk_protocol": _small_source(root, spec.dk_protocol_path),
            "phase7b9dk_manifest": _small_source(root, spec.dk_manifest_path),
            "phase7b9dk_summary": _small_source(root, spec.dk_summary_path),
            "reproduced_tail_runner": _small_source(root, spec.runner_path),
        }
    )
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "configuration": {
            **cfg,
            "phase_index": spec.phase_index,
            "initial_state_path": dk_summary["fresh_output_path"],
            "initial_state_sha256": spec.fresh_current_sha256,
            "scratch_state_path": dk_summary["immutable_input_path"],
            "scratch_state_initial_sha256": spec.immutable_scratch_sha256,
            "maximum_picard_maps": 24,
            "seed_completed_picard_maps": 21,
            "first_runtime_iteration": 21,
            "last_runtime_iteration": 23,
            "maximum_concurrent_processes": 2,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.transient_report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
        },
        "gates": gates,
        "seed_valid_iterations": valid_history,
        "rejected_evidence": {
            "classification": "rejected_nonreproducible_di_iteration20",
            "record": rejected,
            "may_enter_valid_history": False,
        },
        "storage_plan": {
            "additional_full_state_allocation_count": 0,
            "single_stage_owned_transient_report_directory": True,
            "block_reports_compacted_after_each_committed_map": True,
        },
        "authorization": {
            "only_runtime_iterations_21_through_23": True,
            "failed_di_iteration20_may_be_reused": False,
            "single_block_repair_authorized": False,
            "overwrite_only_two_authorized_buffers": True,
            "matter_feedback_during_sequence": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
    }


def write_protocol(
    root: Path,
    spec: ReproducedTailContinuationSpec,
    output_path: Path,
) -> tuple[dict[str, object], str]:
    protocol = build_reproduced_tail_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, _sha256(output_path)


def _load_runtime_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen 7B9dl protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["configuration"].get("runner_path") != RUNNER_RELATIVE_PATH:
        raise RuntimeError("7B9dl runtime runner changed")
    for source in protocol["sources"].values():
        path = root / source["path"]
        if (
            path.stat().st_size != int(source["size_bytes"])
            or _sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"7B9dl source changed: {source['path']}")
    return protocol


def initialize_manifest(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if manifest_path.exists():
        manifest = _read(root, cfg["manifest_path"])
        if manifest.get("protocol_sha256") != expected_hash:
            raise RuntimeError("7B9dl manifest belongs to another protocol")
        current = root / manifest["current_input_path"]
        output = root / manifest["next_output_path"]
        if current.stat().st_size != expected_size or output.stat().st_size != expected_size:
            raise RuntimeError("7B9dl recovery buffer size changed")
        if _sha256(current) != manifest["current_input_sha256"]:
            raise RuntimeError("7B9dl recovery current input changed")
        if manifest.get("active_iteration") is None and _sha256(output) != manifest[
            "next_output_sha256"
        ]:
            raise RuntimeError("7B9dl recovery next output changed")
        return manifest
    current = root / cfg["initial_state_path"]
    output = root / cfg["scratch_state_path"]
    if (
        current.resolve() == output.resolve()
        or current.stat().st_size != expected_size
        or output.stat().st_size != expected_size
        or _sha256(current) != cfg["initial_state_sha256"]
        or _sha256(output) != cfg["scratch_state_initial_sha256"]
    ):
        raise RuntimeError("7B9dl initial A/B bytes changed")
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "next_output_sha256": cfg["scratch_state_initial_sha256"],
        "iterations": protocol["seed_valid_iterations"],
        "rejected_evidence": protocol["rejected_evidence"],
        "active_iteration": None,
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


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
        raise RuntimeError("7B9dl fixed material changed")
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


BatchExecutor = Callable[
    [int, list[int], Path, str, Path, list[Path]], list[dict[str, object]]
]


def _default_batch_executor(
    protocol_path: Path, expected_hash: str
) -> BatchExecutor:
    def execute(
        iteration: int,
        indices: list[int],
        input_path: Path,
        input_sha: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(ROOT / RUNNER_RELATIVE_PATH),
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
                    str(input_path),
                    "--input-sha256",
                    input_sha,
                    "--output-state",
                    str(output_path),
                    "--worker-report",
                    str(report_path),
                ],
                cwd=ROOT,
            )
            for index, report_path in zip(indices, report_paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"7B9dl worker batch failed: {codes}")
        return [_read(ROOT, str(path.resolve().relative_to(ROOT))) for path in report_paths]

    return execute


def _summary(
    root: Path,
    protocol: dict[str, object],
    manifest: dict[str, object],
    expected_hash: str,
) -> dict[str, object]:
    records = manifest["iterations"]
    converged = manifest["status"] == "complete"
    payload = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V-progression]+[O]",
        "protocol_sha256": expected_hash,
        "status": manifest["status"],
        "completed_picard_maps": len(records),
        "iterations": records,
        "rejected_evidence": manifest["rejected_evidence"],
        "residual_history": [row["global_original_operator_residual"] for row in records],
        "contraction_ratio_history": [row["contraction_ratio"] for row in records],
        "boundary_spectrum_l1_history": [row["boundary_spectrum_l1"] for row in records],
        "decision": {
            "positive_picard_sequence_converged": converged,
            "material_feedback_authorized": False,
            "dynamic_nlte_solution_accepted": False,
            "failed_di_iteration20_used_as_valid_history": False,
            "fresh_dk_reproduction_used_as_iteration20": True,
        },
        "figures": [],
    }
    _write_json_atomic(root / protocol["configuration"]["summary_path"], payload)
    return payload


def _run_one_map(
    root: Path,
    protocol_path: Path,
    protocol: dict[str, object],
    expected_hash: str,
    manifest: dict[str, object],
    executor: BatchExecutor,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = engine._shape(protocol)
    manifest_path = root / cfg["manifest_path"]
    iteration = len(manifest["iterations"])
    if iteration < 21 or iteration > 23:
        raise RuntimeError("7B9dl runtime iteration is outside 21..23")
    input_state = root / manifest["current_input_path"]
    output_state = root / manifest["next_output_path"]
    active = manifest.get("active_iteration")
    if active is None:
        active = {
            "iteration": iteration,
            "input_state_path": manifest["current_input_path"],
            "input_state_sha256": manifest["current_input_sha256"],
            "output_state_path": manifest["next_output_path"],
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
        raise RuntimeError("7B9dl active map lineage changed")
    completed = {int(row["block_index"]): row for row in active["completed_blocks"]}
    for row in completed.values():
        digest = engine.base.phase7b9d._block_sha256(
            output_state,
            shape,
            int(row["core_group_start"]),
            int(row["core_group_stop"]),
        )
        if digest != row["output_block_sha256"]:
            raise RuntimeError("7B9dl completed output block changed")
    pending = [index for index in range(76) if index not in completed]
    report_root = storage._transient_root(root, protocol, expected_hash)
    report_dir = report_root / f"iteration_{iteration:02d}"
    report_dir.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(pending), 2):
        batch = pending[offset : offset + 2]
        paths = [report_dir / f"phase7b9dl_block{index:02d}.json" for index in batch]
        started = time.perf_counter()
        rows = executor(
            iteration,
            batch,
            input_state,
            str(manifest["current_input_sha256"]),
            output_state,
            paths,
        )
        if len(rows) != len(batch):
            raise RuntimeError("7B9dl worker batch report count changed")
        for index, path, row in zip(batch, paths, rows, strict=True):
            if (
                row.get("protocol_sha256") != expected_hash
                or int(row.get("block_index", -1)) != index
                or int(row.get("picard_iteration", -1)) != iteration
            ):
                raise RuntimeError("7B9dl worker report changed")
            row["output_block_sha256"] = engine.base.phase7b9d._block_sha256(
                output_state,
                shape,
                int(row["core_group_start"]),
                int(row["core_group_stop"]),
            )
            _write_json_atomic(path, row)
            active["completed_blocks"].append(row)
        active["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        active["accumulated_wall_runtime_s"] += time.perf_counter() - started
        _write_json_atomic(manifest_path, manifest)
    reports = list(active["completed_blocks"])
    metrics = engine._aggregate(reports, shape)
    metrics["block_report_count"] = len(reports)
    metrics["full_map_wall_runtime_s"] = float(active["accumulated_wall_runtime_s"])
    prior_residual = float(manifest["iterations"][-1]["global_original_operator_residual"])
    contraction = float(metrics["global_original_operator_residual"]) / prior_residual
    progression = di._progression_checks(gates, metrics, contraction)
    convergence = di._convergence_checks(gates, metrics)
    progression_passed = all(progression.values())
    convergence_passed = progression_passed and all(convergence.values())
    boundary_passed = bool(
        convergence["boundary_spectrum_pass"]
        and convergence["boundary_bolometric_pass"]
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
        "gate_checks": {
            "frequency_ownership_pass": progression["frequency_ownership_pass"],
            "positive_map_pass": progression["positive_map_pass"],
            "initial_reproduction_pass": True,
            "contraction_pass": progression["contraction_pass"],
            "boundary_pass": boundary_passed,
            "resources_pass": progression["resources_pass"],
        },
        "original_map_passed": bool(progression_passed and boundary_passed),
        "progression_gate_checks": progression,
        "progression_passed": progression_passed,
        "convergence_gate_checks": convergence,
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
    elif len(manifest["iterations"]) >= 24:
        manifest["status"] = "maximum_maps_exhausted"
        manifest["next_output_sha256"] = output_hash
    else:
        prior_path = manifest["current_input_path"]
        prior_hash = manifest["current_input_sha256"]
        manifest["current_input_path"] = manifest["next_output_path"]
        manifest["current_input_sha256"] = output_hash
        manifest["next_output_path"] = prior_path
        manifest["next_output_sha256"] = prior_hash
    _write_json_atomic(manifest_path, manifest)
    return manifest


def run_continuation(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    *,
    batch_executor: BatchExecutor | None = None,
    stop_after_iteration: int | None = None,
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    manifest = initialize_manifest(root, protocol_path, expected_hash)
    storage._transient_root(root, protocol, expected_hash)
    executor = batch_executor or _default_batch_executor(protocol_path, expected_hash)
    while manifest["status"] == "running":
        manifest = _run_one_map(
            root, protocol_path, protocol, expected_hash, manifest, executor
        )
        manifest = storage.compact_committed_reports(root, protocol, expected_hash)
        summary = _summary(root, protocol, manifest, expected_hash)
        if (
            stop_after_iteration is not None
            and len(manifest["iterations"]) - 1 >= stop_after_iteration
        ):
            return summary
    return _summary(root, protocol, manifest, expected_hash)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    protocol_path = Path(args.protocol).resolve()
    if args.worker:
        if None in (
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        ):
            raise RuntimeError("7B9dl worker arguments are incomplete")
        _run_worker(
            protocol_path,
            args.expected_protocol_sha256,
            int(args.iteration),
            int(args.block_index),
            args.input_state,
            str(args.input_sha256),
            args.output_state,
            args.worker_report,
        )
    else:
        summary = run_continuation(
            ROOT, protocol_path, args.expected_protocol_sha256
        )
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
