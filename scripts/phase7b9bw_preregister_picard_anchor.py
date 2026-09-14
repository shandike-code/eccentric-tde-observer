"""Phase 7B9bw：冻结慢模诊断所需的当前 Picard 锚点副本。"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from scripts import phase7b9al_preregister_positive_picard_convergence as helper
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9al_preregister_positive_picard_convergence as helper  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
TARGET = "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"


def main() -> None:
    manifest_path = (
        OUTPUT / "checkpoints/phase7b9bt_long_positive_picard/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    active = manifest["active_iteration"]
    latest = manifest["iterations"][-1]
    if (
        manifest["status"] != "running"
        or len(manifest["iterations"]) != 9
        or int(active["iteration"]) != 9
        or active["input_state_path"] != latest["mapped_state_path"]
        or active["input_state_sha256"] != latest["mapped_state_sha256"]
        or latest["contraction_ratio"] >= 0.99
    ):
        raise RuntimeError("Phase 7B9bw requires the paused map-9 slow-mode anchor")
    source_relative = str(active["input_state_path"])
    source = ROOT / source_relative
    target = ROOT / TARGET
    if helper._sha256(source) != active["input_state_sha256"]:
        raise RuntimeError("Phase 7B9bw source state changed")
    if source.stat().st_size != target.stat().st_size:
        raise RuntimeError("Phase 7B9bw target buffer size changed")
    payload = {
        "phase": "7B9bw preserved Picard slow-mode anchor",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] preserve the complete input to Picard map 9 before "
            "resuming two-buffer iteration; [V] byte-identical chunked copy into one "
            "named superseded checkpoint; [O] no accelerated state is constructed"
        ),
        "sources": {
            "phase7b9bt_manifest_at_pause": helper._source(
                "outputs/checkpoints/phase7b9bt_long_positive_picard/manifest.json"
            ),
            "phase7b9bt_protocol": helper._source(
                "outputs/phase7b9bt_preregistered_long_positive_picard.json"
            ),
            "anchor_source_state": helper._source(source_relative),
        },
        "configuration": {
            "phase_index": 1396,
            "shape": [9632, 32, 4096],
            "copy_frequency_chunk": 32,
            "source_state_path": source_relative,
            "source_state_sha256": active["input_state_sha256"],
            "target_state_path": TARGET,
            "target_state_previous_sha256": helper._sha256(target),
            "summary_path": "outputs/phase7b9bw_picard_anchor_summary.json",
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "target_sha256_must_equal_source_sha256": True,
            "source_and_target_size_equal": True,
        },
        "authorization": {
            "overwrite_only_named_superseded_checkpoint": True,
            "resume_phase7b9bt_after_copy": True,
            "construct_accelerated_candidate": False,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9bw_preregistered_picard_anchor.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
