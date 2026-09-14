"""Phase 7B9an：逐块写入经审计的 theta=8 超松弛候选态。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time

import numpy as np

try:
    from scripts import phase7b9ab_global_trial_residual_audit as base_module
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ab_global_trial_residual_audit as base_module  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "1e88fca21e0d36c7e8e4dbd11728f5c7645208d20ede9950297f74b6f84127e5"
)
base = base_module.base


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if base._sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9an protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or base._sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen Phase 7B9an source changed: {source['path']}"
                )
    return protocol


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    shape = (
        int(configuration["physical_frequency_groups"]),
        int(configuration["angular_direction_count"]),
        int(configuration["radiation_depth_cell_count"]),
    )
    lower_path = ROOT / configuration["lower_state_path"]
    upper_path = ROOT / configuration["upper_state_path"]
    manifest_path = ROOT / configuration["manifest_path"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("protocol_sha256") != EXPECTED_PROTOCOL_SHA256:
            raise RuntimeError("Phase 7B9an manifest belongs to another protocol")
    else:
        if (
            lower_path.stat().st_size
            != int(configuration["raw_float64_checkpoint_size_bytes"])
            or base._sha256(lower_path)
            != configuration["lower_state_initial_sha256"]
        ):
            raise RuntimeError("Phase 7B9an lower endpoint changed before writing")
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "status": "running",
            "completed_blocks": [],
            "wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if manifest["status"] == "complete":
        return json.loads(
            (ROOT / configuration["summary_path"]).read_text(encoding="utf-8")
        )
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    blocks = {int(row["block_index"]): row for row in configuration["blocks"]}
    for index, row in completed.items():
        block = blocks[index]
        digest = base.phase7b9d._block_sha256(
            lower_path,
            shape,
            int(block["core_group_start"]),
            int(block["core_group_stop"]),
        )
        if digest != row["candidate_block_sha256"]:
            raise RuntimeError(f"Phase 7B9an completed block changed: {index}")
    lower = np.memmap(lower_path, mode="r+", dtype=np.float64, shape=shape)
    upper = np.memmap(upper_path, mode="r", dtype=np.float64, shape=shape)
    theta = float(configuration["selected_theta_exactly"])
    started = time.perf_counter()
    for index in range(76):
        if index in completed:
            continue
        block = blocks[index]
        start = int(block["core_group_start"])
        stop = int(block["core_group_stop"])
        digest = base.phase7b9d._block_sha256(lower_path, shape, start, stop)
        if digest != block["lower_block_sha256"]:
            raise RuntimeError(f"Phase 7B9an unwritten block changed: {index}")
        # 中文：只沿已审计的全局 Picard 方向外推，不裁剪负值。
        old = np.array(lower[start:stop], copy=True)
        candidate = old + theta * (np.asarray(upper[start:stop]) - old)
        if not np.all(np.isfinite(candidate)) or np.any(candidate < 0.0):
            raise ArithmeticError(f"Phase 7B9an candidate block is invalid: {index}")
        lower[start:stop] = candidate
        lower.flush()
        candidate_sha = base.phase7b9d._block_sha256(
            lower_path, shape, start, stop
        )
        report = {
            "block_index": index,
            "core_group_start": start,
            "core_group_stop": stop,
            "minimum_candidate_intensity": float(np.min(candidate)),
            "maximum_candidate_intensity": float(np.max(candidate)),
            "candidate_block_sha256": candidate_sha,
        }
        manifest["completed_blocks"].append(report)
        manifest["completed_blocks"].sort(key=lambda value: int(value["block_index"]))
        manifest["wall_runtime_s"] = float(manifest["wall_runtime_s"]) + (
            time.perf_counter() - started
        )
        started = time.perf_counter()
        _write_json_atomic(manifest_path, manifest)
        print(json.dumps({"completed_blocks": len(manifest["completed_blocks"]), "total_blocks": 76}), flush=True)
    del lower, upper
    output_sha = base._sha256(lower_path)
    ownership = np.zeros(shape[0], dtype=np.int8)
    for row in manifest["completed_blocks"]:
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
    checks = {
        "frequency_ownership_pass": len(manifest["completed_blocks"])
        == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and bool(np.all(ownership == 1)),
        "positive_candidate_pass": all(
            float(row["minimum_candidate_intensity"])
            >= gates["minimum_candidate_intensity_at_least"]
            for row in manifest["completed_blocks"]
        ),
        "write_resources_pass": float(manifest["wall_runtime_s"])
        < gates["write_wall_time_strictly_below_s"],
    }
    passed = all(checks.values())
    manifest["status"] = "complete" if passed else "gate_failed"
    manifest["output_state_sha256"] = output_sha
    _write_json_atomic(manifest_path, manifest)
    search = json.loads(
        (ROOT / protocol["sources"]["phase7b9am_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    selected_reports = []
    for report in search["candidate_reports"]:
        selected = next(
            row for row in report["rows"] if float(row["theta"]) == theta
        )
        selected_reports.append(
            {
                "block_index": int(report["block_index"]),
                "block_relative_selected_prediction": (
                    float(selected["maximum_absolute_change"])
                    / float(selected["maximum_scale"])
                    if float(selected["maximum_scale"]) > 0.0
                    else float(selected["maximum_absolute_change"])
                ),
            }
        )
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "selected_theta": theta,
        "candidate_state_path": configuration["output_state_path"],
        "candidate_state_sha256": output_sha,
        "predicted_global_original_operator_residual": search[
            "selected_global_residual"
        ],
        "predicted_boundary_spectrum_l1": search[
            "selected_boundary_spectrum_l1"
        ],
        "predicted_boundary_bolometric_fraction": search[
            "selected_boundary_bolometric_fraction"
        ],
        "wall_runtime_s": manifest["wall_runtime_s"],
        "gate_checks": checks,
        "decision": {
            "overrelaxed_state_write_passed": passed,
            "fresh_global_candidate_audit_authorized": passed,
            "material_feedback_authorized": False,
        },
        "reports": selected_reports,
    }
    _write_json_atomic(ROOT / configuration["summary_path"], summary)
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    run(OUTPUT / "phase7b9an_preregistered_write_overrelaxed_state.json")


if __name__ == "__main__":
    main()
