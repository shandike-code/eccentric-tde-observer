"""Phase 7B9bz：保存已审计慢模映射态的字节一致副本。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "70e61a89edc7ba92829ffaa297274c6d63922b06ffa3c737fa4f3af0f485cb3b"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    protocol_path = OUTPUT / "phase7b9bz_preregistered_accelerated_anchor.json"
    if _sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bz protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if path.stat().st_size != source["size_bytes"] or _sha256(path) != source["sha256"]:
            raise RuntimeError(f"Phase 7B9bz source changed: {source['path']}")
    cfg = protocol["configuration"]
    source_path = ROOT / cfg["source_state_path"]
    target_path = ROOT / cfg["target_state_path"]
    if _sha256(target_path) != cfg["target_state_previous_sha256"]:
        raise RuntimeError("Phase 7B9bz named target changed")
    shape = tuple(int(value) for value in cfg["shape"])
    source = np.memmap(source_path, mode="r", dtype=np.float64, shape=shape)
    target = np.memmap(target_path, mode="r+", dtype=np.float64, shape=shape)
    chunk = int(cfg["copy_frequency_chunk"])
    # 中文：只保存完整字节锚点，不做插值、裁剪、floor 或重归一化。
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        target[start:stop] = source[start:stop]
    target.flush()
    del source, target
    copied_sha = _sha256(target_path)
    if copied_sha != cfg["source_state_sha256"]:
        raise RuntimeError("Phase 7B9bz copied anchor changed bytes")
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "source_state_path": cfg["source_state_path"],
        "source_state_sha256": cfg["source_state_sha256"],
        "anchor_state_path": cfg["target_state_path"],
        "anchor_state_sha256": copied_sha,
        "gate_checks": {
            "byte_identical_copy_pass": True,
            "source_and_target_size_pass": source_path.stat().st_size
            == target_path.stat().st_size,
        },
        "decision": {
            "accelerated_positive_picard_continuation_authorized": True,
            "material_feedback_authorized": False,
        },
    }
    summary_path = ROOT / cfg["summary_path"]
    temporary = summary_path.with_name(f"{summary_path.name}.tmp")
    temporary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    os.replace(temporary, summary_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
