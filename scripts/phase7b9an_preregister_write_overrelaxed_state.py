"""Phase 7B9an：冻结 theta=8 全局超松弛态的可恢复写入。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _block_sha256(path: Path, start: int, stop: int) -> str:
    plane_bytes = 32 * 4096 * 8
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        stream.seek(start * plane_bytes)
        remaining = (stop - start) * plane_bytes
        while remaining:
            block = stream.read(min(16 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("Phase 7B9an state ended inside a block")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest()


def main() -> None:
    search = json.loads(
        (OUTPUT / "phase7b9am_global_picard_overrelaxation_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        search["decision"]["global_picard_overrelaxation_passed"] is not True
        or search["decision"]["write_selected_overrelaxed_state_authorized"]
        is not True
        or search["selected_theta"] != 8.0
        or search["decision"]["material_feedback_authorized"] is not False
    ):
        raise RuntimeError("Phase 7B9an requires the passed theta=8 line search")
    lower_relative = str(search["lower_state_path"])
    upper_relative = str(search["upper_state_path"])
    lower = ROOT / lower_relative
    upper = ROOT / upper_relative
    if (
        _sha256(lower) != search["lower_state_sha256"]
        or _sha256(upper) != search["upper_state_sha256"]
        or lower.stat().st_size != upper.stat().st_size
    ):
        raise RuntimeError("Phase 7B9an line-search endpoints changed")
    blocks = []
    for index in range(76):
        start = index * 128
        stop = min((index + 1) * 128, 9632)
        blocks.append(
            {
                "block_index": index,
                "core_group_start": start,
                "core_group_stop": stop,
                "lower_block_sha256": _block_sha256(lower, start, stop),
            }
        )
    payload = {
        "phase": "7B9an recoverable write of theta-eight overrelaxed state",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] overwrite only the obsolete lower Picard endpoint "
            "with x5+8*(x6-x5), block by block; [V] frozen old-block hashes, exact "
            "frequency ownership, finite nonnegative values and final full-file hash; "
            "[O] the written state remains a candidate until a fresh global audit"
        ),
        "sources": {
            "phase7b9am_summary": _source(
                "outputs/phase7b9am_global_picard_overrelaxation_summary.json"
            ),
            "phase7b9am_protocol": _source(
                "outputs/phase7b9am_preregistered_global_picard_overrelaxation.json"
            ),
            "upper_picard_state": _source(upper_relative),
        },
        "configuration": {
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "selected_theta_exactly": 8.0,
            "lower_state_path": lower_relative,
            "lower_state_initial_sha256": search["lower_state_sha256"],
            "upper_state_path": upper_relative,
            "upper_state_sha256": search["upper_state_sha256"],
            "output_state_path": lower_relative,
            "raw_float64_checkpoint_size_bytes": lower.stat().st_size,
            "blocks": blocks,
            "manifest_path": (
                "outputs/checkpoints/phase7b9an_write_overrelaxed/manifest.json"
            ),
            "summary_path": (
                "outputs/phase7b9an_write_overrelaxed_state_summary.json"
            ),
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "block_count_exactly": 76,
            "owned_frequency_group_count_exactly": 9632,
            "minimum_candidate_intensity_at_least": 0.0,
            "write_wall_time_strictly_below_s": 1200.0,
        },
        "authorization": {
            "write_in_place_to_obsolete_lower_buffer": True,
            "fresh_global_candidate_audit_after_write": True,
            "material_feedback": False,
            "accept_dynamic_nlte_solution": False,
        },
    }
    path = OUTPUT / "phase7b9an_preregistered_write_overrelaxed_state.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
