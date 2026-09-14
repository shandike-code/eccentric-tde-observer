"""Phase 7B9dj：固化 iteration 20 的不可复现 block 34 失败证据。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path


IMMUTABLE_INPUT_SHA256 = (
    "e2d718bd509e28a30f488babcb3ecff6adc612bfa0509f7161073400ffd4bf6f"
)
FAILED_OUTPUT_SHA256 = (
    "65f7307cffb3e52d7d8492ddfdc55fa47074dc565aa9fe466e643f74e1bc2608"
)
FAILED_ITERATION = 20
ANOMALOUS_BLOCK_INDEX = 34


@dataclass(frozen=True)
class FailureAuditSpec:
    phase: str
    classification: str
    di_protocol_path: str
    di_manifest_path: str
    di_summary_path: str
    in_memory_rerun_summary_path: str
    builder_path: str
    immutable_input_sha256: str = IMMUTABLE_INPUT_SHA256
    failed_output_sha256: str = FAILED_OUTPUT_SHA256
    failed_iteration: int = FAILED_ITERATION
    anomalous_block_index: int = ANOMALOUS_BLOCK_INDEX


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _small_source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    if path.suffix == ".dat":
        raise RuntimeError("7B9dj builder refuses to read or hash full-state .dat")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _validate_failure_record(
    record: dict[str, object], spec: FailureAuditSpec
) -> None:
    if (
        int(record.get("iteration", -1)) != spec.failed_iteration
        or record.get("input_state_sha256") != spec.immutable_input_sha256
        or record.get("mapped_state_sha256") != spec.failed_output_sha256
    ):
        raise RuntimeError("7B9dj iteration-20 A/B lineage changed")
    progression = record.get("progression_gate_checks", {})
    expected = {
        "frequency_ownership_pass": True,
        "positive_map_pass": True,
        "resources_pass": True,
        "contraction_pass": False,
    }
    if progression != expected or record.get("progression_passed") is not False:
        raise RuntimeError("7B9dj expected a contraction-only progression failure")
    audit = record.get("block_report_audit", {})
    if (
        audit.get("record_count") != 76
        or audit.get("block_indices") != list(range(76))
    ):
        raise RuntimeError("7B9dj failed map does not contain all 76 block audits")


def _validate_rerun(
    rerun: dict[str, object], record: dict[str, object], spec: FailureAuditSpec
) -> None:
    if (
        rerun.get("input_state_sha256") != spec.immutable_input_sha256
        or int(rerun.get("source_iteration", -1)) != spec.failed_iteration
        or int(rerun.get("block_index", -1)) != spec.anomalous_block_index
        or rerun.get("output_persisted") is not False
        or rerun.get("input_modified") is not False
    ):
        raise RuntimeError("7B9dj in-memory rerun lineage is not fail-closed")
    independent = rerun.get("independent_memory_only_reruns")
    if not isinstance(independent, list) or len(independent) != 2:
        raise RuntimeError("7B9dj requires exactly two independent memory-only reruns")
    failed_block = str(rerun.get("failed_persisted_block_sha256", ""))
    mapped_hashes = []
    for row in independent:
        relative_change = float(row["block_relative_radiation_change"])
        if (
            not math.isfinite(relative_change)
            or relative_change < 0.0
            or relative_change >= float(record["global_original_operator_residual"])
            or row.get("output_persisted") is not False
            or row.get("input_modified") is not False
        ):
            raise RuntimeError("7B9dj in-memory rerun change is invalid")
        mapped_hashes.append(str(row.get("in_memory_rerun_block_sha256", "")))
    if (
        len(failed_block) != 64
        or any(len(value) != 64 for value in mapped_hashes)
        or mapped_hashes[0] != mapped_hashes[1]
        or mapped_hashes[0] == failed_block
    ):
        raise RuntimeError("7B9dj block 34 anomaly was not independently reproduced")


def build_failure_audit(root: Path, spec: FailureAuditSpec) -> dict[str, object]:
    """只消费小文件；A/B 全态在此阶段仅作为冻结哈希声明。"""
    protocol = _read_json(root / spec.di_protocol_path)
    manifest = _read_json(root / spec.di_manifest_path)
    summary = _read_json(root / spec.di_summary_path)
    rerun = _read_json(root / spec.in_memory_rerun_summary_path)
    protocol_sha = _sha256(root / spec.di_protocol_path)
    if (
        manifest.get("protocol_sha256") != protocol_sha
        or summary.get("protocol_sha256") != protocol_sha
        or manifest.get("status") != "gate_failed"
        or summary.get("status") != "gate_failed"
        or manifest.get("active_iteration") is not None
        or manifest.get("iterations") != summary.get("iterations")
    ):
        raise RuntimeError("7B9dj frozen 7B9di small-file evidence changed")
    records = manifest.get("iterations", [])
    if len(records) != spec.failed_iteration + 1:
        raise RuntimeError("7B9dj expected exactly iterations 0..20")
    record = records[-1]
    _validate_failure_record(record, spec)
    _validate_rerun(rerun, record, spec)
    if protocol.get("configuration", {}).get("maximum_concurrent_processes") != 2:
        raise RuntimeError("7B9dj 7B9di worker count changed")
    return {
        "phase": spec.phase,
        "classification": spec.classification,
        "sources": {
            "di_protocol": _small_source(root, spec.di_protocol_path),
            "di_manifest": _small_source(root, spec.di_manifest_path),
            "di_summary": _small_source(root, spec.di_summary_path),
            "in_memory_rerun_summary": _small_source(
                root, spec.in_memory_rerun_summary_path
            ),
            "failure_audit_builder": _small_source(root, spec.builder_path),
        },
        "frozen_state_claims": {
            "immutable_input_path": record["input_state_path"],
            "immutable_input_sha256": spec.immutable_input_sha256,
            "failed_output_path": record["mapped_state_path"],
            "failed_output_sha256": spec.failed_output_sha256,
            "full_state_bytes_read_by_builder": False,
        },
        "failed_map": {
            "iteration": spec.failed_iteration,
            "global_original_operator_residual": record[
                "global_original_operator_residual"
            ],
            "contraction_ratio": record["contraction_ratio"],
            "boundary_spectrum_l1": record["boundary_spectrum_l1"],
            "boundary_bolometric_fraction": record[
                "boundary_bolometric_fraction"
            ],
            "block_report_audit": record["block_report_audit"],
        },
        "localized_failure": dict(rerun),
        "decision": {
            "double_buffer_lineage_error_found": False,
            "failed_persisted_block_reproduced_in_memory": False,
            "unreproducible_block_index": spec.anomalous_block_index,
            "single_block_repair_authorized": False,
            "fresh_full_76_block_reproduction_required": True,
        },
    }


def write_failure_audit(
    root: Path, spec: FailureAuditSpec, output_path: Path
) -> tuple[dict[str, object], str]:
    payload = build_failure_audit(root, spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f"{output_path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, output_path)
    return payload, _sha256(output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--di-protocol", required=True)
    parser.add_argument("--di-manifest", required=True)
    parser.add_argument("--di-summary", required=True)
    parser.add_argument("--rerun-summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    spec = FailureAuditSpec(
        phase="7B9dj iteration20 failure audit",
        classification="[V]+[O]",
        di_protocol_path=args.di_protocol,
        di_manifest_path=args.di_manifest,
        di_summary_path=args.di_summary,
        in_memory_rerun_summary_path=args.rerun_summary,
        builder_path="scripts/phase7b9dj_iteration20_failure_audit.py",
    )
    _, digest = write_failure_audit(root, spec, root / args.output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
