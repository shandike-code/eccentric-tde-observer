"""Phase 7B9ci：冻结第三次 Anderson 映射态的锚点副本。"""

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
    mapped = json.loads(
        (OUTPUT / "phase7b9ch_third_candidate_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if mapped["decision"]["global_positive_picard_map_passed"] is not True:
        raise RuntimeError("Phase 7B9ci requires the audited third candidate map")
    source_relative = str(mapped["output_state_path"])
    source = ROOT / source_relative
    target = ROOT / TARGET
    if helper._sha256(source) != mapped["output_state_sha256"]:
        raise RuntimeError("Phase 7B9ci mapped source changed")
    if source.stat().st_size != target.stat().st_size:
        raise RuntimeError("Phase 7B9ci anchor size changed")
    payload = {
        "phase": "7B9ci preserved third accelerated-map anchor",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] preserve the complete third Anderson mapped state "
            "before two mutable Picard maps; [V] require a byte-identical streamed "
            "copy; [O] no residual is inferred for the copied state"
        ),
        "sources": {
            "phase7b9ch_summary": helper._source(
                "outputs/phase7b9ch_third_candidate_map_summary.json"
            ),
            "phase7b9ch_protocol": helper._source(
                "outputs/phase7b9ch_preregistered_third_candidate_map.json"
            ),
            "mapped_source_state": helper._source(source_relative),
            "checkpoint_copy_runner": helper._source(
                "scripts/phase7b9_checkpoint_copy.py"
            ),
        },
        "configuration": {
            "phase_index": 1410,
            "shape": [9632, 32, 4096],
            "copy_frequency_chunk": 32,
            "source_state_path": source_relative,
            "source_state_sha256": mapped["output_state_sha256"],
            "target_state_path": TARGET,
            "target_state_previous_sha256": helper._sha256(target),
            "summary_path": "outputs/phase7b9ci_third_map_anchor_summary.json",
            "postcopy_authorization_key": (
                "fourth_accelerated_picard_continuation_authorized"
            ),
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
            "run_exactly_two_new_picard_maps": True,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9ci_preregistered_third_map_anchor.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
