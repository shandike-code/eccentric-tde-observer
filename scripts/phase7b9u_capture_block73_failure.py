"""Phase 7B9u：固化 Phase 7B9t 第 73 块的正性失败证据。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


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


def _raw_block_sha256(
    path: Path,
    *,
    group_start: int,
    group_stop: int,
    angle_count: int,
    depth_count: int,
) -> str:
    item_bytes = 8
    group_bytes = angle_count * depth_count * item_bytes
    remaining = (group_stop - group_start) * group_bytes
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(group_start * group_bytes)
        while remaining:
            block = stream.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("candidate state ended inside the audited block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> None:
    protocol = OUTPUT / "phase7b9t_preregistered_full_frequency_krylov_map.json"
    manifest_path = OUTPUT / "checkpoints/phase7b9t_full_frequency_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    completed = [int(row["block_index"]) for row in manifest["completed_blocks"]]
    if (
        manifest["status"] != "running"
        or completed != list(range(73))
        or manifest["candidate_state_sha256"] is not None
    ):
        raise RuntimeError("Phase 7B9u requires the stopped 73/76 transaction")
    report = OUTPUT / "checkpoints/phase7b9i_work/reports_phase7b9t/phase7b9t_block73.json"
    if report.exists():
        raise RuntimeError("Phase 7B9t block 73 unexpectedly has a completed report")
    configuration = json.loads(protocol.read_text(encoding="utf-8"))["configuration"]
    state = OUTPUT / "checkpoints/phase7b9i_work/state_a.dat"
    group_start = int(manifest["completed_blocks"][-1]["core_group_stop"])
    group_stop = min(group_start + 128, int(configuration["physical_frequency_groups"]))
    block_sha_before = _raw_block_sha256(
        state,
        group_start=group_start,
        group_stop=group_stop,
        angle_count=int(configuration["angular_direction_count"]),
        depth_count=int(configuration["radiation_depth_cell_count"]),
    )
    started = time.perf_counter()
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/phase7b9t_full_frequency_krylov_map.py"),
            "--worker",
            "--protocol",
            str(protocol),
            "--block-index",
            "73",
            "--worker-report",
            str(report),
            "--output-state",
            str(state),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = process.stderr
    block_sha_after = _raw_block_sha256(
        state,
        group_start=group_start,
        group_stop=group_stop,
        angle_count=int(configuration["angular_direction_count"]),
        depth_count=int(configuration["radiation_depth_cell_count"]),
    )
    expected = "PhysicalDomainError: no positive affine step preserves non-negativity"
    reproduced = bool(
        process.returncode != 0
        and expected in stderr
        and not report.exists()
        and block_sha_after == block_sha_before
    )
    payload = {
        "phase": "7B9u Phase 7B9t block-73 failure capture",
        "classification": "[V]+[O]",
        "phase7b9t_protocol_sha256": _sha256(protocol),
        "stopped_manifest_sha256_before_replay": _sha256(manifest_path),
        "completed_blocks_before_replay": len(completed),
        "replayed_block_index": 73,
        "return_code": process.returncode,
        "expected_exception": expected,
        "stderr": stderr,
        "stdout": process.stdout,
        "worker_report_absent": not report.exists(),
        "candidate_group_start": group_start,
        "candidate_group_stop": group_stop,
        "candidate_block_sha256_before": block_sha_before,
        "candidate_block_sha256_after": block_sha_after,
        "candidate_block_not_written_before_exception": (
            block_sha_after == block_sha_before
        ),
        "failure_reproduced": reproduced,
        "wall_runtime_s": time.perf_counter() - started,
        "decision": {
            "phase7b9t_full_map_passed": False,
            "unconstrained_affine_krylov_tail_rejected": reproduced,
            "positive_domain_solver_redesign_required": reproduced,
            "global_candidate_residual_authorized": False,
            "material_feedback_authorized": False,
        },
    }
    _write_json_atomic(
        OUTPUT / "phase7b9u_block73_failure_capture_summary.json", payload
    )
    if not reproduced:
        raise RuntimeError("Phase 7B9u did not reproduce the frozen block-73 failure")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
