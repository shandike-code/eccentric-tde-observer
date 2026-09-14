"""Phase 7B9：通用的全频率检查点字节一致锚点复制器。"""

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
        raise RuntimeError("frozen checkpoint-copy protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if path.stat().st_size != source["size_bytes"] or _sha256(path) != source["sha256"]:
            raise RuntimeError(f"checkpoint-copy source changed: {source['path']}")
    cfg = protocol["configuration"]
    source_path = ROOT / cfg["source_state_path"]
    target_path = ROOT / cfg["target_state_path"]
    target_previous_sha = _sha256(target_path)
    if target_previous_sha != cfg["target_state_previous_sha256"]:
        raise RuntimeError("named checkpoint-copy target changed")
    already_identical = (
        target_previous_sha == cfg["source_state_sha256"]
        and source_path.stat().st_size == target_path.stat().st_size
    )
    if not already_identical:
        # 中文：APFS 文件级 clone 避免 10 GB memmap 复制触发内存压力；字节哈希仍独立复核。
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
