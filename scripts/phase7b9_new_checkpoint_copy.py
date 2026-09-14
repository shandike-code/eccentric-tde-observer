"""Phase 7B9：支持首次创建新命名目标的严格字节一致锚点复制器。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def run(protocol_path: Path, expected_protocol_sha256: str) -> dict[str, object]:
    if _sha256(protocol_path) != expected_protocol_sha256:
        raise RuntimeError("frozen new-target checkpoint-copy protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if (
            path.stat().st_size != source["size_bytes"]
            or _sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"new checkpoint-copy source changed: {source['path']}")

    cfg = protocol["configuration"]
    if "target_previous_exists" not in cfg:
        raise RuntimeError("new-target protocol must freeze target_previous_exists")
    source_path = ROOT / cfg["source_state_path"]
    target_path = ROOT / cfg["target_state_path"]
    target_previous_exists = cfg["target_previous_exists"]
    target_previous_sha = cfg["target_state_previous_sha256"]
    target_exists_at_run = target_path.exists()

    if target_previous_exists is True:
        if target_previous_sha is None or not target_exists_at_run:
            raise RuntimeError("named checkpoint-copy target changed")
        current_target_sha = _sha256(target_path)
        if current_target_sha != target_previous_sha:
            raise RuntimeError("named checkpoint-copy target changed")
        already_identical = (
            current_target_sha == cfg["source_state_sha256"]
            and source_path.stat().st_size == target_path.stat().st_size
        )
    elif target_previous_exists is False:
        if target_previous_sha is not None:
            raise RuntimeError("absent checkpoint-copy target must freeze a null hash")
        if target_exists_at_run:
            # 中文：仅接受首次复制完成、但 summary 尚未落盘的字节一致恢复态。
            already_identical = (
                target_path.is_file()
                and target_path.stat().st_size == source_path.stat().st_size
                and _sha256(target_path) == cfg["source_state_sha256"]
            )
            if not already_identical:
                raise RuntimeError("new checkpoint-copy target exists but is not identical")
        else:
            already_identical = False
    else:
        raise RuntimeError("target_previous_exists must be boolean")

    if not already_identical:
        # 中文：APFS 文件级 clone 避免复制大检查点产生额外内存压力。
        subprocess.run(
            ["/bin/cp", "-c", str(source_path), str(target_path)],
            check=True,
        )
    copied_sha = _sha256(target_path)
    if copied_sha != cfg["source_state_sha256"]:
        raise RuntimeError("copied anchor is not byte-identical to its source")
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": expected_protocol_sha256,
        "source_state_path": cfg["source_state_path"],
        "source_state_sha256": cfg["source_state_sha256"],
        "anchor_state_path": cfg["target_state_path"],
        "anchor_state_sha256": copied_sha,
        "gate_checks": {
            "byte_identical_copy_pass": True,
            "already_identical_recovery": already_identical,
            "target_created_from_absent": not target_exists_at_run,
            "source_and_target_size_pass": source_path.stat().st_size
            == target_path.stat().st_size,
        },
        "decision": {
            str(cfg["postcopy_authorization_key"]): True,
            "material_feedback_authorized": False,
        },
    }
    summary_path = ROOT / cfg["summary_path"]
    temporary = summary_path.with_name(f"{summary_path.name}.tmp")
    temporary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    os.replace(temporary, summary_path)
    print(json.dumps(summary, indent=2))
    return summary
