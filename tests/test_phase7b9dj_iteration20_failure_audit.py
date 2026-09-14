"""7B9dj 只用 tmp_path 小文件固化 iteration20 失败证据。"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import phase7b9dj_iteration20_failure_audit as audit


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fixture(root: Path) -> audit.FailureAuditSpec:
    a_sha = _sha(b"immutable-A")
    b_sha = _sha(b"failed-B")
    runner = "scripts/dj.py"
    _write(root / runner, b"dj builder")
    protocol = {"configuration": {"maximum_concurrent_processes": 2}}
    _write(root / "outputs/di_protocol.json", protocol)
    protocol_sha = _sha((root / "outputs/di_protocol.json").read_bytes())
    records = []
    for index in range(21):
        records.append(
            {
                "iteration": index,
                "input_state_path": "outputs/A.dat",
                "input_state_sha256": a_sha,
                "mapped_state_path": "outputs/B.dat",
                "mapped_state_sha256": b_sha,
                "global_original_operator_residual": (
                    0.013567072657945642 if index == 20 else 0.001777798494271581
                ),
                "contraction_ratio": 7.631389441301383 if index == 20 else 0.95,
                "boundary_spectrum_l1": 5.478670983169336e-4,
                "boundary_bolometric_fraction": 5.460319970160108e-4,
                "progression_gate_checks": {
                    "frequency_ownership_pass": True,
                    "positive_map_pass": True,
                    "contraction_pass": index != 20,
                    "resources_pass": True,
                },
                "progression_passed": index != 20,
                "block_report_audit": {
                    "record_count": 76,
                    "block_indices": list(range(76)),
                    "sha256": _sha(f"reports-{index}".encode()),
                    "full_reports_retained": False,
                },
            }
        )
    manifest = {
        "protocol_sha256": protocol_sha,
        "status": "gate_failed",
        "active_iteration": None,
        "iterations": records,
    }
    _write(root / "outputs/di_manifest.json", manifest)
    _write(root / "outputs/di_summary.json", manifest)
    mapped_sha = _sha(b"deterministic-rerun")
    rerun = {
        "source_iteration": 20,
        "block_index": 34,
        "input_state_sha256": a_sha,
        "failed_persisted_block_sha256": _sha(b"failed-block"),
        "output_persisted": False,
        "input_modified": False,
        "independent_memory_only_reruns": [
            {
                "attempt": attempt,
                "block_relative_radiation_change": 9.716e-4,
                "in_memory_rerun_block_sha256": mapped_sha,
                "output_persisted": False,
                "input_modified": False,
            }
            for attempt in (1, 2)
        ],
    }
    _write(root / "outputs/rerun.json", rerun)
    return audit.FailureAuditSpec(
        phase="dj",
        classification="[V]+[O]",
        di_protocol_path="outputs/di_protocol.json",
        di_manifest_path="outputs/di_manifest.json",
        di_summary_path="outputs/di_summary.json",
        in_memory_rerun_summary_path="outputs/rerun.json",
        builder_path=runner,
        immutable_input_sha256=a_sha,
        failed_output_sha256=b_sha,
    )


def test_two_independent_memory_reruns_freeze_failure(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    payload = audit.build_failure_audit(tmp_path, spec)
    assert payload["frozen_state_claims"]["full_state_bytes_read_by_builder"] is False
    assert payload["decision"]["unreproducible_block_index"] == 34
    assert payload["decision"]["single_block_repair_authorized"] is False
    rows = payload["localized_failure"]["independent_memory_only_reruns"]
    assert rows[0]["in_memory_rerun_block_sha256"] == rows[1][
        "in_memory_rerun_block_sha256"
    ]


def test_mismatched_second_rerun_is_rejected(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.in_memory_rerun_summary_path
    rerun = json.loads(path.read_text())
    rerun["independent_memory_only_reruns"][1]["in_memory_rerun_block_sha256"] = _sha(
        b"different"
    )
    _write(path, rerun)
    with pytest.raises(RuntimeError, match="not independently reproduced"):
        audit.build_failure_audit(tmp_path, spec)


def test_failed_block_equal_to_rerun_is_rejected(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.in_memory_rerun_summary_path
    rerun = json.loads(path.read_text())
    rerun["failed_persisted_block_sha256"] = rerun[
        "independent_memory_only_reruns"
    ][0]["in_memory_rerun_block_sha256"]
    _write(path, rerun)
    with pytest.raises(RuntimeError, match="not independently reproduced"):
        audit.build_failure_audit(tmp_path, spec)


def test_dat_source_is_never_accepted_as_builder_source(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    _write(tmp_path / "outputs/not_allowed.dat", b"tiny synthetic bytes")
    bad = replace(spec, builder_path="outputs/not_allowed.dat")
    with pytest.raises(RuntimeError, match="refuses to read or hash"):
        audit.build_failure_audit(tmp_path, bad)
