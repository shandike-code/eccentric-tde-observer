"""Phase 7B9bz：冻结已审计慢模映射态的不可变锚点副本。"""

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
        (OUTPUT / "phase7b9by_slow_mode_candidate_map_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        mapped["decision"]["global_positive_picard_map_passed"] is not True
        or mapped["decision"]["mapped_state_committed_as_diagnostic_candidate"]
        is not True
        or mapped["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9bz requires the audited slow-mode map")
    source_relative = str(mapped["output_state_path"])
    source = ROOT / source_relative
    target = ROOT / TARGET
    if helper._sha256(source) != mapped["output_state_sha256"]:
        raise RuntimeError("Phase 7B9bz mapped source changed")
    if source.stat().st_size != target.stat().st_size:
        raise RuntimeError("Phase 7B9bz anchor size changed")
    payload = {
        "phase": "7B9bz preserved accelerated-map anchor",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] preserve the complete mapped Anderson state before "
            "starting a mutable double-buffer continuation; [V] require a byte-"
            "identical streamed copy; [O] the residual of this mapped state is not "
            "known until the next complete original-operator map"
        ),
        "sources": {
            "phase7b9by_summary": helper._source(
                "outputs/phase7b9by_slow_mode_candidate_map_summary.json"
            ),
            "phase7b9by_protocol": helper._source(
                "outputs/phase7b9by_preregistered_slow_mode_candidate_map.json"
            ),
            "mapped_source_state": helper._source(source_relative),
        },
        "configuration": {
            "phase_index": 1401,
            "shape": [9632, 32, 4096],
            "copy_frequency_chunk": 32,
            "source_state_path": source_relative,
            "source_state_sha256": mapped["output_state_sha256"],
            "target_state_path": TARGET,
            "target_state_previous_sha256": helper._sha256(target),
            "summary_path": "outputs/phase7b9bz_accelerated_anchor_summary.json",
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
            "start_accelerated_positive_picard_continuation": True,
            "material_feedback": False,
        },
    }
    path = OUTPUT / "phase7b9bz_preregistered_accelerated_anchor.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(helper._sha256(path))


if __name__ == "__main__":
    main()
