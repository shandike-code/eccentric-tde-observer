"""可恢复地编排 streaming Anderson pass1/pass2 的 76 个 dry workers。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable

try:
    from scripts import phase7b9di_streaming_anderson_tail as streaming
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9di_streaming_anderson_tail as streaming  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PARENT_RELATIVE_PATH = "scripts/phase7b9_streaming_dry_pass_parent.py"
PARENT_SOURCE_KEY = "streaming_anderson_dry_pass_parent"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen streaming-Anderson protocol changed")
    protocol = _read_json(protocol_path)
    cfg = protocol.get("configuration", {})
    if (
        cfg.get("runner_path") != streaming.RUNNER_RELATIVE_PATH
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
    ):
        raise RuntimeError("streaming dry-pass worker/concurrency changed")
    for source in protocol["sources"].values():
        current = root / source["path"]
        if (
            current.stat().st_size != int(source["size_bytes"])
            or _sha256(current) != source["sha256"]
        ):
            raise RuntimeError(f"streaming dry-pass source changed: {source['path']}")
    parent = protocol["sources"].get(PARENT_SOURCE_KEY)
    expected_parent = root / PARENT_RELATIVE_PATH
    if (
        not isinstance(parent, dict)
        or parent.get("path") != PARENT_RELATIVE_PATH
        or parent.get("sha256") != _sha256(expected_parent)
        or int(parent.get("size_bytes", -1)) != expected_parent.stat().st_size
    ):
        raise RuntimeError("streaming dry-pass parent is not frozen in the protocol")
    return protocol


def _ranges(protocol: dict[str, object]) -> list[tuple[int, int]]:
    cfg = protocol["configuration"]
    groups = int(cfg["physical_frequency_groups"])
    count = int(cfg["natural_frequency_block_count"])
    width = int(cfg["diagnostic_frequency_block"])
    ranges = [
        (index * width, min((index + 1) * width, groups))
        for index in range(count)
    ]
    if count != 76 or ranges[-1][1] != groups:
        raise RuntimeError("streaming dry-pass block partition changed")
    return ranges


def _report_path(root: Path, protocol: dict[str, object], pass_index: int, index: int) -> Path:
    cfg = protocol["configuration"]
    key = (
        "coefficient_report_directory"
        if pass_index == 1
        else "evaluation_report_directory"
    )
    return root / cfg[key] / f"pass{pass_index}_block{index:02d}.json"


def _manifest_path(
    root: Path, protocol: dict[str, object], pass_index: int
) -> Path:
    key = "coefficient_manifest_path" if pass_index == 1 else "evaluation_manifest_path"
    return root / protocol["configuration"][key]


def _validate_report(
    protocol: dict[str, object],
    expected_hash: str,
    pass_index: int,
    index: int,
    report: dict[str, object],
) -> None:
    cfg = protocol["configuration"]
    start, stop = _ranges(protocol)[index]
    gates = protocol["algebraic_gates"]
    if (
        report.get("protocol_sha256") != expected_hash
        or int(report.get("pass_index", -1)) != pass_index
        or int(report.get("block_index", -1)) != index
        or (report.get("core_group_start"), report.get("core_group_stop"))
        != (start, stop)
        or report.get("x23_state_sha256") != cfg["x23_state_sha256"]
        or report.get("x24_state_sha256") != cfg["x24_state_sha256"]
        or report.get("full_state_write_performed") is not False
        or float(report.get("peak_process_rss_mib", float("inf")))
        >= gates["each_dry_process_peak_rss_strictly_below_mib"]
        or float(report.get("wall_runtime_s", float("inf")))
        >= gates["each_dry_worker_wall_time_strictly_below_s"]
    ):
        raise RuntimeError(f"streaming dry pass {pass_index} block {index} failed")


BatchExecutor = Callable[
    [int, list[int], float | None, list[Path]], list[dict[str, object]]
]


def _default_executor(
    protocol_path: Path, expected_hash: str
) -> BatchExecutor:
    def execute(
        pass_index: int,
        indices: list[int],
        selected: float | None,
        paths: list[Path],
    ) -> list[dict[str, object]]:
        processes = []
        for index, path in zip(indices, paths, strict=True):
            command = [
                sys.executable,
                str(ROOT / streaming.RUNNER_RELATIVE_PATH),
                "--protocol",
                str(protocol_path),
                "--expected-protocol-sha256",
                expected_hash,
                "--pass-index",
                str(pass_index),
                "--block-index",
                str(index),
                "--report",
                str(path),
            ]
            if selected is not None:
                command.extend(["--selected-forward-fraction", repr(selected)])
            processes.append(subprocess.Popen(command, cwd=ROOT))
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"streaming dry worker batch failed: {codes}")
        return [_read_json(path) for path in paths]

    return execute


def _new_manifest(
    protocol: dict[str, object],
    expected_hash: str,
    pass_index: int,
    coefficient_sha: str | None,
    selected: float | None,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    payload = {
        "protocol_sha256": expected_hash,
        "status": "running",
        "pass_index": pass_index,
        "x23_state_sha256": cfg["x23_state_sha256"],
        "x24_state_sha256": cfg["x24_state_sha256"],
        "full_state_write_performed": False,
        "reports": [],
        "report_files": [],
        "active_blocks": [],
        "full_map_wall_runtime_s": 0.0,
    }
    if pass_index == 2:
        payload["coefficient_manifest_sha256"] = coefficient_sha
        payload["selected_forward_fraction"] = selected
    return payload


def _recover_manifest(
    root: Path,
    protocol: dict[str, object],
    expected_hash: str,
    pass_index: int,
    manifest: dict[str, object],
    coefficient_sha: str | None,
    selected: float | None,
) -> None:
    cfg = protocol["configuration"]
    if (
        manifest.get("protocol_sha256") != expected_hash
        or manifest.get("pass_index") != pass_index
        or manifest.get("x23_state_sha256") != cfg["x23_state_sha256"]
        or manifest.get("x24_state_sha256") != cfg["x24_state_sha256"]
        or manifest.get("full_state_write_performed") is not False
        or (pass_index == 2 and manifest.get("coefficient_manifest_sha256") != coefficient_sha)
        or (pass_index == 2 and manifest.get("selected_forward_fraction") != selected)
    ):
        raise RuntimeError("streaming dry-pass recovery lineage changed")
    reports = manifest.get("reports", [])
    files = manifest.get("report_files", [])
    if len(reports) != len(files):
        raise RuntimeError("streaming dry-pass report/file audit count changed")
    indices: set[int] = set()
    for report, source in zip(reports, files, strict=True):
        index = int(report.get("block_index", -1))
        if index in indices or index < 0 or index >= 76:
            raise RuntimeError("streaming dry-pass completed block ownership changed")
        indices.add(index)
        _validate_report(protocol, expected_hash, pass_index, index, report)
        path = root / source["path"]
        if (
            path.stat().st_size != int(source["size_bytes"])
            or _sha256(path) != source["sha256"]
            or _read_json(path) != report
        ):
            raise RuntimeError("streaming dry-pass completed report changed")
    if manifest.get("active_blocks"):
        # Dry workers never write full state; uncommitted reports are safe to recompute.
        manifest["active_blocks"] = []


def _coefficient_manifest(
    root: Path, protocol: dict[str, object], expected_hash: str
) -> tuple[dict[str, object], str, float]:
    path = _manifest_path(root, protocol, 1)
    manifest = _read_json(path)
    if (
        manifest.get("protocol_sha256") != expected_hash
        or manifest.get("status") != "complete"
        or manifest.get("pass_index") != 1
        or manifest.get("full_state_write_performed") is not False
    ):
        raise RuntimeError("streaming pass2 requires a complete frozen pass1")
    _recover_manifest(root, protocol, expected_hash, 1, manifest, None, None)
    aggregate = streaming.aggregate_coefficient_statistics(
        manifest["reports"],
        minimum_fraction=float(protocol["configuration"]["minimum_forward_picard_fraction"]),
        maximum_fraction=float(protocol["configuration"]["maximum_forward_picard_fraction"]),
    )
    if manifest.get("aggregate") != aggregate:
        raise RuntimeError("streaming pass1 aggregate changed")
    return manifest, _sha256(path), float(aggregate["selected_forward_fraction"])


def run_dry_pass(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    pass_index: int,
    *,
    batch_executor: BatchExecutor | None = None,
) -> dict[str, object]:
    if pass_index not in (1, 2):
        raise ValueError("dry pass index must be 1 or 2")
    protocol = _load_protocol(root, protocol_path, expected_hash)
    coefficient = coefficient_sha = selected = None
    if pass_index == 2:
        coefficient, coefficient_sha, selected = _coefficient_manifest(
            root, protocol, expected_hash
        )
    manifest_path = _manifest_path(root, protocol, pass_index)
    if manifest_path.exists():
        manifest = _read_json(manifest_path)
        _recover_manifest(
            root,
            protocol,
            expected_hash,
            pass_index,
            manifest,
            coefficient_sha,
            selected,
        )
        if manifest.get("status") in {"complete", "gate_failed"}:
            return manifest
    else:
        manifest = _new_manifest(
            protocol, expected_hash, pass_index, coefficient_sha, selected
        )
    executor = batch_executor or _default_executor(protocol_path, expected_hash)
    completed = {int(row["block_index"]) for row in manifest["reports"]}
    pending = [index for index in range(76) if index not in completed]
    for offset in range(0, len(pending), 2):
        batch = pending[offset : offset + 2]
        paths = [_report_path(root, protocol, pass_index, index) for index in batch]
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        manifest["active_blocks"] = batch
        _write_json_atomic(manifest_path, manifest)
        started = time.perf_counter()
        rows = executor(pass_index, batch, selected, paths)
        manifest["full_map_wall_runtime_s"] += time.perf_counter() - started
        if len(rows) != len(batch):
            raise RuntimeError("streaming dry-pass worker report count changed")
        for index, path, report in zip(batch, paths, rows, strict=True):
            _validate_report(protocol, expected_hash, pass_index, index, report)
            _write_json_atomic(path, report)
            manifest["reports"].append(report)
            manifest["report_files"].append(
                {
                    "block_index": index,
                    "path": str(path.resolve().relative_to(root.resolve())),
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
        order = sorted(
            range(len(manifest["reports"])),
            key=lambda item: int(manifest["reports"][item]["block_index"]),
        )
        manifest["reports"] = [manifest["reports"][item] for item in order]
        manifest["report_files"] = [manifest["report_files"][item] for item in order]
        manifest["active_blocks"] = []
        _write_json_atomic(manifest_path, manifest)
    gates = protocol["algebraic_gates"]
    resource_pass = bool(
        manifest["full_map_wall_runtime_s"]
        < gates["each_dry_full_map_wall_time_strictly_below_s"]
    )
    if pass_index == 1:
        aggregate = streaming.aggregate_coefficient_statistics(
            manifest["reports"],
            minimum_fraction=float(protocol["configuration"]["minimum_forward_picard_fraction"]),
            maximum_fraction=float(protocol["configuration"]["maximum_forward_picard_fraction"]),
        )
        manifest["aggregate"] = aggregate
        manifest["resource_gate_checks"] = {
            "worker_reports_pass": True,
            "full_map_wall_runtime_pass": resource_pass,
        }
        manifest["status"] = "complete" if resource_pass else "gate_failed"
    else:
        assert coefficient is not None
        current_coefficient_sha = _sha256(_manifest_path(root, protocol, 1))
        if current_coefficient_sha != coefficient_sha:
            raise RuntimeError("streaming pass1 changed while pass2 was running")
        evaluation = streaming.aggregate_evaluation_statistics(
            manifest["reports"], coefficient["reports"]
        )
        checks = streaming.algebraic_gate_checks(
            protocol, coefficient["aggregate"], evaluation
        )
        checks.update(
            {
                "pass1_resources_pass": True,
                "pass2_resources_pass": resource_pass,
                "block_ownership_pass": True,
            }
        )
        manifest["aggregate"] = evaluation
        manifest["gate_checks"] = checks
        manifest["status"] = "complete" if all(checks.values()) else "gate_failed"
    manifest["full_state_write_performed"] = False
    _write_json_atomic(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> dict[str, object]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--pass-index", required=True, type=int, choices=(1, 2))
    args = parser.parse_args(argv)
    manifest = run_dry_pass(
        root,
        root / args.protocol,
        args.expected_protocol_sha256,
        args.pass_index,
    )
    print(
        json.dumps(
            {
                "pass_index": args.pass_index,
                "status": manifest["status"],
                "completed_blocks": len(manifest["reports"]),
                "full_state_write_performed": False,
            },
            indent=2,
        )
    )
    return manifest


if __name__ == "__main__":
    main()
