"""Phase 7B9df：只读预检两个历史完整态的复用条件。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
INVENTORY = OUTPUT / "phase7_checkpoint_inventory.json"
REPORT = OUTPUT / "phase7b9df_storage_reuse_preflight.json"


TARGET_SPECS = (
    {
        "path": "outputs/checkpoints/phase7b9k_retained_trial_map3.dat",
        "source_protocol": "outputs/phase7b9k_preregistered_block_aitken_pilot.json",
        "source_key": "retained_trial_map3",
        "historical_role": "failed Phase 7B9k acceleration-pilot map 3",
    },
    {
        "path": "outputs/checkpoints/phase7b9cs_resource_adjusted_tail_anchor.dat",
        "source_protocol": "outputs/phase7b9cu_preregistered_protected_anderson_tail.json",
        "source_key": "x9_state",
        "historical_role": "superseded Picard x9 anchor used by Phase 7B9cu",
    },
)


def load_json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def run() -> dict[str, object]:
    inventory = load_json(str(INVENTORY.relative_to(ROOT)))
    full_states = {
        row["path"]: row for row in inventory["full_state_checkpoints"]
    }
    rows: list[dict[str, object]] = []
    for spec in TARGET_SPECS:
        path = ROOT / spec["path"]
        protocol = load_json(spec["source_protocol"])
        frozen = protocol["sources"][spec["source_key"]]
        entry = full_states[spec["path"]]
        stat = path.stat()
        rows.append(
            {
                **spec,
                "current_size_bytes": stat.st_size,
                "current_allocated_size_bytes": stat.st_blocks * 512,
                "frozen_size_bytes": frozen["size_bytes"],
                "frozen_sha256_claim": frozen["sha256"],
                "current_sha256_recomputed": False,
                "size_matches_frozen_claim": stat.st_size == frozen["size_bytes"],
                "inventory_classification": entry["classification"],
                "current_protected_roles": entry["active_phase7b9dd_roles"],
                "direct_referencer_count": entry["direct_referencer_count"],
                "direct_referencers": entry["direct_referencers"],
                "currently_in_phase7b9dd_protected_chain": bool(
                    entry["active_phase7b9dd_roles"]
                ),
                "exact_historical_bytes_recoverable_without_recompute_after_reuse": False,
            }
        )
    usage = shutil.disk_usage(ROOT)
    total = sum(int(row["current_size_bytes"]) for row in rows)
    gates = {
        "both_paths_exist": all((ROOT / row["path"]).is_file() for row in rows),
        "both_sizes_match_frozen_claims": all(
            row["size_matches_frozen_claim"] for row in rows
        ),
        "neither_path_is_in_current_protected_chain": all(
            not row["currently_in_phase7b9dd_protected_chain"] for row in rows
        ),
        "both_paths_are_still_historically_referenced": all(
            int(row["direct_referencer_count"]) > 0 for row in rows
        ),
        "current_hash_recheck_complete": False,
        "explicit_user_reuse_approval_recorded": False,
    }
    report = {
        "phase": "7B9df non-destructive storage-reuse preflight",
        "classification": "[V-metadata]+[A-resource]+[O-authorization]",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "scope": {
            "checkpoint_content_bytes_read": 0,
            "checkpoint_hashes_computed": False,
            "checkpoint_files_deleted": False,
            "checkpoint_files_modified": False,
            "metadata_operations": ["stat", "small JSON lineage scan"],
        },
        "current_disk": {
            "free_bytes": usage.free,
            "free_gib": usage.free / 1024**3,
        },
        "candidate_reuse_total_bytes": total,
        "candidate_reuse_total_gib": total / 1024**3,
        "targets": rows,
        "gate_checks": gates,
        "decision": {
            "metadata_preflight_passed": all(
                gates[name]
                for name in (
                    "both_paths_exist",
                    "both_sizes_match_frozen_claims",
                    "neither_path_is_in_current_protected_chain",
                    "both_paths_are_still_historically_referenced",
                )
            ),
            "destructive_reuse_authorized": False,
            "reuse_may_start_without_current_hash_recheck": False,
            "reuse_may_start_without_explicit_user_approval": False,
            "next_action_after_approval": (
                "recompute both current SHA-256 values, compare with frozen claims, "
                "freeze an exact overwrite protocol, then use both paths only as "
                "recoverable ping-pong work buffers"
            ),
        },
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
