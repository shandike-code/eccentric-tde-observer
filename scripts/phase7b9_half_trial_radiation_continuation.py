"""Phase 7B9：0.0625 物质候选上的双缓冲 fixed-material 辐射续算。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil

try:
    from scripts import phase7b9_protocol_builders as common
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as common  # type: ignore[no-redef]
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9_half_trial_radiation_continuation.py"
SEQUENCE_ENGINE_RELATIVE_PATH = (
    "scripts/phase7b9_half_trial_positive_sequence_engine.py"
)
EXPECTED_HASH_ENV = "PHASE7B9_HALF_TRIAL_RADIATION_PROTOCOL_SHA256"
MATERIAL_RELAXATION = 0.0625
MAXIMUM_PICARD_MAPS = 24
MAXIMUM_CONCURRENT_PROCESSES = 2
FULL_MAP_WALL_GATE_S = 1800.0
INITIAL_RADIATION_PATH = (
    "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
)
INITIAL_RADIATION_SHA256 = (
    "192bce63a94ecd45e88be7538414d063e4e54fa0931a70ca356aeb218af8bd08"
)
BUFFER_ROLES = {"buffer_a", "buffer_b"}
TRANSIENT_REPORT_BUDGET_BYTES = 64 * 1024 * 1024
MINIMUM_FREE_BYTES_BEFORE_RUN = 256 * 1024 * 1024


@dataclass(frozen=True)
class HalfTrialRadiationContinuationSpec:
    phase: str
    phase_index: int
    classification: str
    material_protocol_path: str
    material_summary_path: str
    storage_authorization_path: str
    initial_radiation_claim_protocol_path: str
    finite_radiation_template_path: str
    fixed_material_worker_template_path: str
    runner_path: str
    initialization_receipt_path: str
    manifest_path: str
    transient_report_directory: str
    summary_path: str
    figure_path: str


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _validate_hash(value: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("expected SHA256 must be 64 lowercase hexadecimal characters")
    return value


def _claim_entry(path: str, size_bytes: int, sha256: str) -> dict[str, object]:
    return {
        "path": path,
        "size_bytes": int(size_bytes),
        "sha256": _validate_hash(sha256),
    }


def _small_source(root: Path, relative_path: str) -> dict[str, object]:
    if relative_path.endswith(".dat"):
        raise RuntimeError("builder must not read or hash a full radiation checkpoint")
    return common.source_entry(root, relative_path)


def _material_candidate(
    root: Path,
    protocol_path: str,
    summary_path: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    protocol = common.read_json(root, protocol_path)
    summary = common.read_json(root, summary_path)
    decision = summary.get("decision", {})
    candidate_path = str(summary.get("candidate_path"))
    candidate = _small_source(root, candidate_path)
    if (
        summary.get("protocol_sha256") != common.sha256(root / protocol_path)
        or float(summary.get("candidate_absolute_relaxation", -1.0))
        != MATERIAL_RELAXATION
        or float(protocol.get("configuration", {}).get("candidate_absolute_relaxation", -1.0))
        != MATERIAL_RELAXATION
        or candidate.get("sha256") != summary.get("candidate_sha256")
        or decision.get("material_candidate_gate_passed") is not True
        or decision.get("candidate_full_frequency_radiation_authorized") is not True
        or decision.get("candidate_radiation_evaluated") is not False
        or decision.get("candidate_formal_feedback_evaluated") is not False
        or decision.get("candidate_accepted_as_nonlinear_step") is not False
        or not summary.get("gate_checks")
        or any(value is not True for value in summary["gate_checks"].values())
    ):
        raise RuntimeError("0.0625 material-candidate lineage or gates changed")
    return protocol, summary, candidate


def _authorized_buffers(
    authorization: dict[str, object],
) -> dict[str, dict[str, object]]:
    gates = authorization.get("gate_checks", {})
    rights = authorization.get("authorization", {})
    configuration = authorization.get("configuration", {})
    targets = configuration.get("targets")
    if (
        not isinstance(targets, list)
        or len(targets) != 2
        or {row.get("future_role") for row in targets} != BUFFER_ROLES
        or configuration.get("target_count") != 2
        or configuration.get("overwrite_may_begin_only_after_future_protocol_hash_is_frozen")
        is not True
        or not gates
        or any(value is not True for value in gates.values())
        or rights.get("destructive_reuse_authorized") is not True
        or rights.get("overwrite_only_exact_named_targets") is not True
        or rights.get("delete_unrelated_files") is not False
        or rights.get("modify_protected_current_chain") is not False
        or any(value is not False for value in rights.get("numerical_repair", {}).values())
    ):
        raise RuntimeError("storage-reuse authorization contract changed")
    by_role = {str(row["future_role"]): dict(row) for row in targets}
    sizes = {int(row["size_bytes"]) for row in targets}
    if len(sizes) != 1:
        raise RuntimeError("authorized ping-pong buffers have different sizes")
    for row in targets:
        _validate_hash(str(row["verified_current_sha256"]))
    return by_role


def _initial_radiation_claim(
    claim_protocol: dict[str, object],
) -> dict[str, object]:
    matches = [
        source
        for source in claim_protocol.get("sources", {}).values()
        if source.get("path") == INITIAL_RADIATION_PATH
    ]
    if (
        len(matches) != 1
        or matches[0].get("sha256") != INITIAL_RADIATION_SHA256
        or int(matches[0].get("size_bytes", -1)) <= 0
    ):
        raise RuntimeError("protected initial-radiation claim changed")
    return dict(matches[0])


def build_fixed_material_worker_template(
    root: Path,
    spec: HalfTrialRadiationContinuationSpec,
) -> dict[str, object]:
    """Build the small worker template without opening a full-state `.dat`."""
    _, _, candidate = _material_candidate(
        root, spec.material_protocol_path, spec.material_summary_path
    )
    template = deepcopy(common.read_json(root, spec.finite_radiation_template_path))
    if "current_material_state" not in template.get("sources", {}):
        raise RuntimeError("finite-radiation template lacks current material source")
    template["phase"] = "7B9 0.0625 fixed-material radiation worker template"
    template["protocol_version"] = 2
    template["classification"] = "[A-initialization]+[V-lineage]+[O]"
    # 中文：只替换固定物质态；ZO/辐射输运算子及旧时间层均保持原模板定义。
    template["sources"]["current_material_state"] = dict(candidate)
    if "finite_trial_material" in template["sources"]:
        template["sources"]["finite_trial_material"] = dict(candidate)
    template["authorization"] = {
        "template_only": True,
        "fixed_material_relaxation_exactly": MATERIAL_RELAXATION,
        "material_update": False,
        "radiation_update_outside_named_ping_pong_buffers": False,
        "accept_dynamic_nlte_solution": False,
    }
    return template


def build_half_trial_radiation_continuation_protocol(
    root: Path,
    spec: HalfTrialRadiationContinuationSpec,
) -> dict[str, object]:
    """Build a hash-free storage plan; runtime alone verifies full-state bytes."""
    _, material_summary, candidate = _material_candidate(
        root, spec.material_protocol_path, spec.material_summary_path
    )
    storage = common.read_json(root, spec.storage_authorization_path)
    buffers = _authorized_buffers(storage)
    claim_protocol = common.read_json(root, spec.initial_radiation_claim_protocol_path)
    initial = _initial_radiation_claim(claim_protocol)
    protected = {
        row.get("path")
        for row in storage["configuration"].get("protected_current_chain", [])
        if row.get("must_not_be_modified") is True
    }
    if INITIAL_RADIATION_PATH not in protected:
        raise RuntimeError("initial radiation is no longer protected by storage authorization")
    if int(initial["size_bytes"]) != int(buffers["buffer_a"]["size_bytes"]):
        raise RuntimeError("initial radiation and authorized buffers have different sizes")
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("half-trial continuation runner path changed")
    transient = Path(spec.transient_report_directory)
    if (
        transient.is_absolute()
        or ".." in transient.parts
        or transient.parts[:2] != ("outputs", "checkpoints")
        or "transient" not in transient.name
    ):
        raise RuntimeError("transient report directory is not a stage-owned safe target")
    worker_template = common.read_json(root, spec.fixed_material_worker_template_path)
    if (
        worker_template.get("sources", {}).get("current_material_state") != candidate
        or worker_template.get("authorization", {}).get(
            "fixed_material_relaxation_exactly"
        )
        != MATERIAL_RELAXATION
    ):
        raise RuntimeError("fixed-material worker template changed")
    worker_dependencies = {
        "phase7b5p_master_input": worker_template["sources"][
            "phase7b5p_master_input"
        ],
        "phase7b7i_worker": _small_source(root, common.MAP_WORKER),
        "phase7b9d_worker_helpers": _small_source(root, common.WORKER_HELPERS),
        "generic_positive_picard_runner": _small_source(
            root, common.GENERIC_MAP_RUNNER
        ),
        "positive_sequence_engine": _small_source(
            root, SEQUENCE_ENGINE_RELATIVE_PATH
        ),
        "mixed_frame_operator": _small_source(root, common.MIXED_FRAME_OPERATOR),
        "mixed_frame_frequency": _small_source(root, common.MIXED_FRAME_FREQUENCY),
    }
    gates = common.memory_safe_seeded_two_map_gates()
    if gates["each_full_map_wall_time_strictly_below_s"] != FULL_MAP_WALL_GATE_S:
        raise ArithmeticError("two-worker wall gate is not the frozen 1800 s")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "half_trial_material_protocol": _small_source(
                root, spec.material_protocol_path
            ),
            "half_trial_material_summary": _small_source(
                root, spec.material_summary_path
            ),
            "storage_reuse_authorization": _small_source(
                root, spec.storage_authorization_path
            ),
            "initial_radiation_claim_protocol": _small_source(
                root, spec.initial_radiation_claim_protocol_path
            ),
            "finite_trial_protocol": _small_source(
                root, spec.fixed_material_worker_template_path
            ),
            "finite_trial_material": candidate,
            "half_trial_continuation_runner": _small_source(root, spec.runner_path),
            **worker_dependencies,
        },
        "full_state_claims": {
            # 中文：builder 只冻结既有声明；runtime 在覆盖 A 前只复核一次真实字节。
            "protected_initial_radiation": initial,
            "authorized_buffer_a_precopy": {
                "path": buffers["buffer_a"]["path"],
                "size_bytes": buffers["buffer_a"]["size_bytes"],
                "sha256": buffers["buffer_a"]["verified_current_sha256"],
            },
            "authorized_buffer_b_precopy": {
                "path": buffers["buffer_b"]["path"],
                "size_bytes": buffers["buffer_b"]["size_bytes"],
                "sha256": buffers["buffer_b"]["verified_current_sha256"],
            },
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": common.PHYSICAL_FREQUENCY_GROUPS,
            "angular_direction_count": common.ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": common.RADIATION_DEPTH_CELL_COUNT,
            "natural_frequency_block_count": common.NATURAL_FREQUENCY_BLOCK_COUNT,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "material_candidate_absolute_relaxation": MATERIAL_RELAXATION,
            "maximum_picard_maps": MAXIMUM_PICARD_MAPS,
            "maximum_concurrent_processes": MAXIMUM_CONCURRENT_PROCESSES,
            "stop_after_iteration": MAXIMUM_PICARD_MAPS - 1,
            "initial_reference_mode": "unreferenced_fixed_material_bootstrap",
            "material_feedback_authorization_mode": (
                "after_two_consecutive_and_formal_pair"
            ),
            "initialization_classification": "[A-initialization]",
            "initialization_reason": (
                "nearest protected converged radiation field from the previous "
                "material fixed point; it changes the start, not the fixed point"
            ),
            "protected_initial_source_path": initial["path"],
            "protected_initial_source_sha256": initial["sha256"],
            "initial_state_path": buffers["buffer_a"]["path"],
            "initial_state_sha256": initial["sha256"],
            "precopy_buffer_a_sha256": buffers["buffer_a"][
                "verified_current_sha256"
            ],
            "scratch_state_path": buffers["buffer_b"]["path"],
            "scratch_state_initial_sha256": buffers["buffer_b"][
                "verified_current_sha256"
            ],
            "raw_float64_checkpoint_size_bytes": int(initial["size_bytes"]),
            "initialization_receipt_path": spec.initialization_receipt_path,
            "manifest_path": spec.manifest_path,
            "report_directory": spec.transient_report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            "transient_report_budget_bytes": TRANSIENT_REPORT_BUDGET_BYTES,
            "minimum_free_bytes_before_run": MINIMUM_FREE_BYTES_BEFORE_RUN,
            **common.numerical_repair_prohibitions(sequence=True),
        },
        "reference": {
            "initial_global_residual": None,
            "initial_boundary_spectrum_l1": None,
            "initial_boundary_bolometric_fraction": None,
            "initial_reference_is_applicable": False,
            "material_candidate_sha256": material_summary["candidate_sha256"],
        },
        "gates": gates,
        "storage_plan": {
            "buffer_a_role": "protected-source copy, then alternating input/output",
            "buffer_b_role": "initial scratch, then alternating output/input",
            "additional_full_state_allocation_count": 0,
            "protected_initial_source_modified": False,
            "single_stage_owned_transient_report_directory": True,
            "block_reports_compacted_after_each_committed_map": True,
            "peak_additional_disk_bytes_upper_bound": TRANSIENT_REPORT_BUDGET_BYTES,
        },
        "authorization": {
            "copy_protected_initial_source_into_buffer_a_once": True,
            "modify_protected_initial_source": False,
            "overwrite_only_authorized_buffer_a_and_buffer_b": True,
            "delete_only_stage_owned_transient_reports": True,
            "evaluate_provisional_feedback_after_first_low_residual": True,
            "provisional_feedback_is_acceptance_authority": False,
            "formal_pair_only_after_next_consecutive_fresh_residual": True,
            "material_feedback_before_formal_pair": False,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }


def write_protocol_bundle(
    root: Path,
    spec: HalfTrialRadiationContinuationSpec,
    protocol_path: Path,
) -> tuple[dict[str, object], str]:
    """Write only small JSON templates/protocols; never touch a `.dat`."""
    worker = build_fixed_material_worker_template(root, spec)
    _write_json_atomic(root / spec.fixed_material_worker_template_path, worker)
    protocol = build_half_trial_radiation_continuation_protocol(root, spec)
    _write_json_atomic(protocol_path, protocol)
    return protocol, common.sha256(protocol_path)


def _load_runtime_protocol(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    expected_hash = _validate_hash(expected_hash)
    if common.sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen half-trial radiation protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("configuration", {}).get("runner_path") != RUNNER_RELATIVE_PATH:
        raise RuntimeError("half-trial radiation runner changed")
    for source in protocol.get("sources", {}).values():
        path = root / str(source["path"])
        if (
            path.stat().st_size != int(source["size_bytes"])
            or common.sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"frozen half-trial source changed: {source['path']}")
    return protocol


def initialize_authorized_buffers(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    """Copy the protected start into A after rechecking both authorized old hashes."""
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    initial = root / cfg["protected_initial_source_path"]
    buffer_a = root / cfg["initial_state_path"]
    buffer_b = root / cfg["scratch_state_path"]
    receipt_path = root / cfg["initialization_receipt_path"]
    manifest_path = root / cfg["manifest_path"]
    # 中文：只创建冻结 receipt 的父目录；尚不触碰任何全态检查点。
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if any(path.stat().st_size != expected_size for path in (initial, buffer_a, buffer_b)):
        raise RuntimeError("initial radiation or authorized buffer size changed")
    initial_hash = common.sha256(initial)
    if initial_hash != cfg["protected_initial_source_sha256"]:
        raise RuntimeError("protected initial radiation changed")
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (
            receipt.get("protocol_sha256") != expected_hash
            or receipt.get("buffer_a_postcopy_sha256") != initial_hash
            or receipt.get("protected_source_modified") is not False
        ):
            raise RuntimeError("buffer initialization receipt changed")
        # 中文：map 开始后 A/B 会交替改写；恢复时由 manifest 对当前 input 作字节守卫。
        if not manifest_path.exists():
            if (
                common.sha256(buffer_a) != initial_hash
                or common.sha256(buffer_b) != cfg["scratch_state_initial_sha256"]
            ):
                raise RuntimeError("initialized buffers changed before first manifest")
        return receipt
    a_hash = common.sha256(buffer_a)
    b_hash = common.sha256(buffer_b)
    if b_hash != cfg["scratch_state_initial_sha256"]:
        raise RuntimeError("authorized buffer_b changed before initialization")
    if a_hash not in {cfg["precopy_buffer_a_sha256"], initial_hash}:
        raise RuntimeError("authorized buffer_a changed before initialization")
    free = shutil.disk_usage(receipt_path.parent).free
    if free <= int(cfg["minimum_free_bytes_before_run"]):
        raise OSError("insufficient free space for transient report budget")
    resumed_after_copy = a_hash == initial_hash
    if not resumed_after_copy:
        # 中文：只覆盖用户批准的 A；受保护初猜以只读源身份保留。
        shutil.copyfile(initial, buffer_a)
        if common.sha256(buffer_a) != initial_hash:
            raise RuntimeError("buffer_a initialization copy failed byte identity")
    receipt = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "complete",
        "protected_source_path": cfg["protected_initial_source_path"],
        "protected_source_sha256": initial_hash,
        "protected_source_modified": False,
        "buffer_a_path": cfg["initial_state_path"],
        "buffer_a_precopy_sha256": cfg["precopy_buffer_a_sha256"],
        "buffer_a_postcopy_sha256": initial_hash,
        "buffer_b_path": cfg["scratch_state_path"],
        "buffer_b_unchanged_sha256": b_hash,
        "resumed_after_copy_before_receipt": resumed_after_copy,
        "free_bytes_before_run": free,
        "estimated_peak_additional_disk_bytes": int(
            cfg["transient_report_budget_bytes"]
        ),
    }
    _write_json_atomic(receipt_path, receipt)
    return receipt


def _transient_root(root: Path, protocol: dict[str, object], expected_hash: str) -> Path:
    path = (root / protocol["configuration"]["report_directory"]).resolve()
    allowed_parent = (root / "outputs/checkpoints").resolve()
    if not path.is_relative_to(allowed_parent) or "transient" not in path.name:
        raise RuntimeError("refusing unsafe transient-report directory")
    path.mkdir(parents=True, exist_ok=True)
    marker = path / ".phase7b9_transient_owner.json"
    if marker.exists():
        data = json.loads(marker.read_text(encoding="utf-8"))
        if data.get("protocol_sha256") != expected_hash:
            raise RuntimeError("transient-report directory belongs to another protocol")
    else:
        _write_json_atomic(marker, {"protocol_sha256": expected_hash})
    return path


def compact_committed_reports(
    root: Path,
    protocol: dict[str, object],
    expected_hash: str,
) -> dict[str, object]:
    """Retain a small block audit and remove only this stage's transient reports."""
    manifest_path = root / protocol["configuration"]["manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("protocol_sha256") != expected_hash:
        raise RuntimeError("half-trial manifest lineage changed before compaction")
    for record in manifest.get("iterations", []):
        reports = record.pop("reports", None)
        if reports is None:
            continue
        encoded = json.dumps(reports, sort_keys=True, separators=(",", ":")).encode()
        record["block_report_audit"] = {
            "record_count": len(reports),
            "block_indices": [int(row["block_index"]) for row in reports],
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "full_reports_retained": False,
        }
    _write_json_atomic(manifest_path, manifest)
    transient = _transient_root(root, protocol, expected_hash)
    marker = transient / ".phase7b9_transient_owner.json"
    for child in transient.iterdir():
        if child == marker:
            continue
        if child.is_symlink():
            raise RuntimeError("refusing symlink in transient-report directory")
        if child.is_file():
            child.unlink()
            continue
        for nested in sorted(child.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if nested.is_symlink():
                raise RuntimeError("refusing symlink in transient-report tree")
            if nested.is_file():
                nested.unlink()
            else:
                nested.rmdir()
        child.rmdir()
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
    fixed_template = json.loads(
        (ROOT / protocol["sources"]["finite_trial_protocol"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    if (
        fixed_template["sources"]["current_material_state"]
        != protocol["sources"]["finite_trial_material"]
    ):
        raise RuntimeError("worker fixed-material source changed")
    generic = engine.generic
    original_loader = generic.base.phase7b9i._load_protocol
    try:
        generic.base.phase7b9i._load_protocol = (
            lambda _path, validate_sources=False: fixed_template
        )
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
        generic.base.phase7b9i._load_protocol = original_loader


def run_to_first_low_residual(
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    """Run recoverably to one audited low-residual input, then pause for feedback."""
    expected_hash = _validate_hash(expected_hash)
    protocol = _load_runtime_protocol(ROOT, protocol_path, expected_hash)
    initialize_authorized_buffers(ROOT, protocol_path, expected_hash)
    _transient_root(ROOT, protocol, expected_hash)
    engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
    os.environ[EXPECTED_HASH_ENV] = expected_hash
    manifest_path = ROOT / protocol["configuration"]["manifest_path"]
    while True:
        completed = 0
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            completed = len(manifest.get("iterations", []))
            if manifest.get("status") != "running":
                break
        engine.run(protocol_path, stop_after_iteration=completed)
        manifest = compact_committed_reports(ROOT, protocol, expected_hash)
        engine._summary(protocol, manifest)
        if manifest.get("status") != "running":
            break
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = engine._summary(protocol, manifest)
    if manifest.get("status") == "complete":
        final_map = manifest["iterations"][-1]
        summary["first_low_residual_input_path"] = final_map["input_state_path"]
        summary["first_low_residual_input_sha256"] = final_map["input_state_sha256"]
        summary["next_consecutive_input_path"] = final_map["mapped_state_path"]
        summary["next_consecutive_input_sha256"] = final_map["mapped_state_sha256"]
        summary["decision"].update(
            {
                "first_low_residual_and_boundary_input_audited": True,
                "provisional_feedback_extraction_authorized": True,
                "provisional_feedback_is_formal_pair_authority": False,
                "next_consecutive_fresh_residual_required": True,
                "formal_h_he_feedback_pair_authorized": False,
            }
        )
        _write_json_atomic(ROOT / protocol["configuration"]["summary_path"], summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    expected = args.expected_protocol_sha256 or os.environ.get(EXPECTED_HASH_ENV)
    if expected is None:
        raise ValueError("frozen protocol SHA256 is required")
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
            expected,
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    run_to_first_low_residual(args.protocol, expected)


if __name__ == "__main__":
    main()
