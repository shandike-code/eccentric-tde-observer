"""Phase 7B9bn：构造非相邻偶数目标块候选。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = "aec2b1826086d1d6dd4ff10e46967fad9612c6f5ad058ab1b069c830a29eb4fa"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    protocol_path = OUTPUT / "phase7b9bn_preregistered_even_block_candidate.json"
    if _sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bn protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if path.stat().st_size != source["size_bytes"] or _sha256(path) != source["sha256"]:
            raise RuntimeError(f"Phase 7B9bn source changed: {source['path']}")
    cfg = protocol["configuration"]
    shape = tuple(int(value) for value in cfg["shape"])
    base_path = ROOT / cfg["base_state_path"]
    targeted_path = ROOT / cfg["full_targeted_state_path"]
    output_path = ROOT / cfg["candidate_state_path"]
    if _sha256(output_path) != cfg["candidate_state_previous_sha256"]:
        raise RuntimeError("Phase 7B9bn named scratch changed")
    base = np.memmap(base_path, mode="r", dtype=np.float64, shape=shape)
    targeted = np.memmap(targeted_path, mode="r", dtype=np.float64, shape=shape)
    output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
    chunk = int(cfg["copy_frequency_chunk"])
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        output[start:stop] = base[start:stop]
    block_size = int(cfg["natural_frequency_block_size"])
    for block_index in cfg["selected_even_blocks"]:
        start = int(block_index) * block_size
        stop = min(start + block_size, shape[0])
        # 红黑第一步只替换互不相邻的偶数核心块，邻块仍保持已审计基准态。
        output[start:stop] = targeted[start:stop]
    output.flush()
    minimum = float(np.min(output))
    checks = {
        "positive_candidate_pass": minimum >= protocol["gates"]["minimum_candidate_intensity_at_least"],
        "selected_count_pass": len(cfg["selected_even_blocks"]) == protocol["gates"]["selected_block_count_exactly"],
        "pairwise_nonadjacent_pass": all(b - a > 1 for a, b in zip(cfg["selected_even_blocks"][:-1], cfg["selected_even_blocks"][1:])),
    }
    if not all(checks.values()):
        raise RuntimeError("Phase 7B9bn constructor gate failed")
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "selected_even_blocks": cfg["selected_even_blocks"],
        "minimum_candidate_intensity": minimum,
        "candidate_state_path": cfg["candidate_state_path"],
        "candidate_state_sha256": _sha256(output_path),
        "gate_checks": checks,
        "decision": {"fresh_global_map_authorized": True, "material_feedback_authorized": False},
    }
    summary_path = ROOT / cfg["summary_path"]
    temporary = summary_path.with_name(f"{summary_path.name}.tmp")
    temporary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    os.replace(temporary, summary_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
