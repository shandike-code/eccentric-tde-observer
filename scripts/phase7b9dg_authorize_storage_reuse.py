"""Phase 7B9dg：复核并冻结两个历史检查点的定向复用授权。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "outputs/phase7b9df_storage_reuse_preflight.json"
INVENTORY = ROOT / "outputs/phase7_checkpoint_inventory.json"
OUTPUT = ROOT / "outputs/phase7b9dg_preregistered_storage_reuse.json"

TARGET_ROLES = {
    "outputs/checkpoints/phase7b9k_retained_trial_map3.dat": "buffer_a",
    "outputs/checkpoints/phase7b9cs_resource_adjusted_tail_anchor.dat": "buffer_b",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source_entry(path: Path, *, include_hash: bool = True) -> dict[str, object]:
    entry: dict[str, object] = {
        "path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
    }
    if include_hash:
        entry["sha256"] = sha256(path)
    return entry


def build_protocol(
    preflight: dict[str, object],
    inventory: dict[str, object],
    current_hashes: dict[str, str],
    *,
    generated_at_utc: str,
) -> dict[str, object]:
    """用已复算身份构造授权；该纯函数不会读取检查点内容。"""

    if not preflight["decision"]["metadata_preflight_passed"]:
        raise RuntimeError("Phase 7B9df metadata preflight did not pass")
    rows = preflight["targets"]
    if {row["path"] for row in rows} != set(TARGET_ROLES):
        raise RuntimeError("storage-reuse target set changed")

    targets: list[dict[str, object]] = []
    for row in rows:
        path = row["path"]
        actual_hash = current_hashes.get(path)
        if actual_hash != row["frozen_sha256_claim"]:
            raise RuntimeError(f"current checkpoint hash mismatch: {path}")
        if row["current_size_bytes"] != row["frozen_size_bytes"]:
            raise RuntimeError(f"current checkpoint size mismatch: {path}")
        if row["currently_in_phase7b9dd_protected_chain"]:
            raise RuntimeError(f"protected checkpoint cannot be reused: {path}")
        targets.append(
            {
                "path": path,
                "future_role": TARGET_ROLES[path],
                "size_bytes": row["current_size_bytes"],
                "verified_current_sha256": actual_hash,
                "historical_role": row["historical_role"],
                "historical_referencers": row["direct_referencers"],
                "exact_historical_bytes_recoverable_without_recompute_after_reuse": False,
            }
        )

    protected: list[dict[str, object]] = []
    for row in inventory["full_state_checkpoints"]:
        if row["active_phase7b9dd_roles"]:
            protected.append(
                {
                    "path": row["path"],
                    "roles": row["active_phase7b9dd_roles"],
                    "must_not_be_modified": True,
                }
            )
    if len(protected) != 3:
        raise RuntimeError("expected exactly three protected Phase 7B9dd radiation states")

    return {
        "phase": "7B9dg exact storage-reuse authorization",
        "classification": "[V-hash]+[A-resource]+[A-authorized]",
        "generated_at_utc": generated_at_utc,
        "approval_record": {
            "verbatim": "批准复用两个检查点",
            "scope": "only the two named historical checkpoints below",
            "approved_in_current_project_task": True,
        },
        "sources": {
            "preflight": source_entry(PREFLIGHT),
            "inventory": source_entry(INVENTORY),
            "authorization_runner": source_entry(Path(__file__).resolve()),
        },
        "configuration": {
            "purpose": "Phase 7B9de fixed-material radiation ping-pong buffers",
            "target_count": 2,
            "targets": targets,
            "protected_current_chain": protected,
            "overwrite_may_begin_only_after_future_protocol_hash_is_frozen": True,
        },
        "gate_checks": {
            "metadata_preflight_passed": True,
            "both_current_hashes_recomputed": True,
            "both_current_hashes_match_frozen_claims": True,
            "neither_target_is_protected": True,
            "explicit_user_reuse_approval_recorded": True,
        },
        "authorization": {
            "destructive_reuse_authorized": True,
            "overwrite_only_exact_named_targets": True,
            "delete_unrelated_files": False,
            "modify_protected_current_chain": False,
            "preserve_historical_hashes_and_referencers_in_this_protocol": True,
            "historical_bytes_become_unrecoverable_without_recomputation": True,
            "numerical_repair": {
                "nan_to_num": False,
                "clipping": False,
                "floors": False,
                "failed_point_deletion": False,
                "posthoc_renormalization": False,
            },
        },
    }


def run(output: Path = OUTPUT) -> dict[str, object]:
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    current_hashes = {
        path: sha256(ROOT / path)
        for path in TARGET_ROLES
    }
    protocol = build_protocol(
        preflight,
        inventory,
        current_hashes,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    output.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return protocol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite frozen authorization: {args.output}")
    protocol = run(args.output)
    print(json.dumps(protocol, indent=2))


if __name__ == "__main__":
    main()
