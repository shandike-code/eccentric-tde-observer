"""Phase 7：只读建立递归检查点存储与完整辐射态依赖清单。"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CHECKPOINTS = OUTPUT / "checkpoints"
PROTOCOL_PATH = OUTPUT / "phase7b9dd_preregistered_material_trial_rejection.json"
SUMMARY_PATH = OUTPUT / "phase7b9dd_material_trial_rejection_summary.json"
CONFIRMATION_PATH = OUTPUT / "phase7b9cw_consecutive_confirmation_summary.json"
INVENTORY_PATH = OUTPUT / "phase7_checkpoint_inventory.json"
DOCUMENT_PATH = ROOT / "docs/phase7_checkpoint_inventory.md"
SCRIPT_PATH = ROOT / "scripts/phase7_checkpoint_inventory.py"


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def gib(size_bytes: int) -> float:
    return size_bytes / 1024**3


def allocated_bytes(stat_result: object) -> int:
    """POSIX st_blocks 以 512 bytes 为单位；这里只读取元数据。"""
    blocks = getattr(stat_result, "st_blocks", None)
    if blocks is None:
        raise RuntimeError("filesystem does not expose st_blocks")
    return int(blocks) * 512


def scan_sources() -> list[Path]:
    """仅扫描任务声明的文本域，并排除清单自己的派生产物。"""
    sources = sorted(OUTPUT.glob("*.json"))
    sources.extend(sorted((ROOT / "docs").rglob("*.md")))
    sources.extend(sorted((ROOT / "scripts").rglob("*.py")))
    excluded = {INVENTORY_PATH, DOCUMENT_PATH, SCRIPT_PATH}
    return [path for path in sources if path not in excluded]


def read_current_phase() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """读取当前受保护链；不读取或哈希任何完整辐射态。"""
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    confirmation = json.loads(CONFIRMATION_PATH.read_text(encoding="utf-8"))
    return protocol, summary, confirmation


def recursive_regular_files() -> list[Path]:
    """递归枚举普通文件；不跟随符号链接。"""
    return sorted(
        path
        for path in CHECKPOINTS.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def storage_category(path: Path, size_bytes: int, full_state_size: int) -> str:
    if path.suffix.lower() == ".dat" and size_bytes == full_state_size:
        return "full-state-dat"
    if path.suffix.lower() in {".dat", ".npz"}:
        return "block-chunk-state"
    if path.suffix.lower() == ".json":
        return "json-report"
    return "other"


def full_state_references(
    full_states: list[Path], sources: list[Path]
) -> tuple[dict[str, dict[str, object]], int]:
    """解析完整路径；仅在文件名唯一时接纳 basename-only 引用。"""
    basename_counts = Counter(path.name for path in full_states)
    references: dict[str, dict[str, object]] = {
        relative(path): {
            "direct_referencers": [],
            "ambiguous_basename_reference_occurrence_count": 0,
        }
        for path in full_states
    }
    scanned_bytes = 0
    for source in sources:
        text = source.read_text(encoding="utf-8")
        scanned_bytes += source.stat().st_size
        for path in full_states:
            checkpoint_path = relative(path)
            exact_count = text.count(checkpoint_path)
            basename_count = text.count(path.name)
            basename_only_count = max(0, basename_count - exact_count)
            unique_basename_only_count = (
                basename_only_count if basename_counts[path.name] == 1 else 0
            )
            ambiguous_count = (
                basename_only_count if basename_counts[path.name] > 1 else 0
            )
            entry = references[checkpoint_path]
            entry["ambiguous_basename_reference_occurrence_count"] = int(
                entry["ambiguous_basename_reference_occurrence_count"]
            ) + ambiguous_count
            if exact_count or unique_basename_only_count:
                entry["direct_referencers"].append(
                    {
                        "path": relative(source),
                        "exact_path_occurrence_count": exact_count,
                        "unique_basename_only_occurrence_count": (
                            unique_basename_only_count
                        ),
                    }
                )
    return references, scanned_bytes


def category_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    apparent = sum(int(row["apparent_size_bytes"]) for row in rows)
    allocated = sum(int(row["allocated_size_bytes"]) for row in rows)
    return {
        "file_count": len(rows),
        "apparent_size_bytes": apparent,
        "apparent_size_gib": gib(apparent),
        "allocated_size_bytes": allocated,
        "allocated_size_gib": gib(allocated),
    }


def main() -> None:
    protocol, summary, confirmation = read_current_phase()
    sources = protocol["sources"]
    expected_size = int(sources["previous_radiation"]["size_bytes"])
    role_paths = {
        "previous_converged": str(sources["previous_radiation"]["path"]),
        "final_converged": str(sources["final_radiation"]["path"]),
        "residual_audit_output": str(confirmation["output_state_path"]),
    }
    runtime_paths: dict[str, str] = {}

    files = recursive_regular_files()
    rows_by_category: dict[str, list[dict[str, object]]] = {
        "full-state-dat": [],
        "block-chunk-state": [],
        "json-report": [],
        "other": [],
    }
    for path in files:
        stat = path.stat()
        category = storage_category(path, stat.st_size, expected_size)
        rows_by_category[category].append(
            {
                "path": relative(path),
                "apparent_size_bytes": stat.st_size,
                "allocated_size_bytes": allocated_bytes(stat),
                "mtime_unix_ns": stat.st_mtime_ns,
                "mtime_utc": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )

    full_state_paths = [
        ROOT / str(row["path"]) for row in rows_by_category["full-state-dat"]
    ]
    scanned_sources = scan_sources()
    references, scanned_bytes = full_state_references(full_state_paths, scanned_sources)

    full_state_entries: list[dict[str, object]] = []
    class_counts = {
        "active": 0,
        "referenced": 0,
        "unreferenced-candidate": 0,
        "unknown": 0,
    }
    for row in rows_by_category["full-state-dat"]:
        checkpoint_path = str(row["path"])
        active_roles = [
            role for role, role_path in role_paths.items() if role_path == checkpoint_path
        ]
        runtime_roles = [
            role
            for role, runtime_path in runtime_paths.items()
            if runtime_path == checkpoint_path
        ]
        reference = references[checkpoint_path]
        referencers = reference["direct_referencers"]
        ambiguous_count = int(
            reference["ambiguous_basename_reference_occurrence_count"]
        )
        if active_roles:
            classification = "active"
        elif referencers:
            classification = "referenced"
        elif ambiguous_count:
            classification = "unknown"
        else:
            classification = "unreferenced-candidate"
        class_counts[classification] += 1
        full_state_entries.append(
            {
                **row,
                "filename": Path(checkpoint_path).name,
                "apparent_size_gib": gib(int(row["apparent_size_bytes"])),
                "allocated_size_gib": gib(int(row["allocated_size_bytes"])),
                "matches_active_full_state_size": True,
                "direct_referencer_count": len(referencers),
                "direct_reference_occurrence_count": sum(
                    int(item["exact_path_occurrence_count"])
                    + int(item["unique_basename_only_occurrence_count"])
                    for item in referencers
                ),
                "ambiguous_basename_reference_occurrence_count": ambiguous_count,
                "direct_referencers": referencers,
                "active_phase7b9dd_roles": active_roles,
                "active_runtime_roles_at_snapshot": runtime_roles,
                "classification": classification,
            }
        )

    category_summaries = {
        category: category_summary(rows)
        for category, rows in rows_by_category.items()
    }
    recursive_apparent = sum(
        int(summary["apparent_size_bytes"])
        for summary in category_summaries.values()
    )
    recursive_allocated = sum(
        int(summary["allocated_size_bytes"])
        for summary in category_summaries.values()
    )
    directory_allocated = sum(
        allocated_bytes(path.stat())
        for path in CHECKPOINTS.rglob("*")
        if path.is_dir() and not path.is_symlink()
    ) + allocated_bytes(CHECKPOINTS.stat())
    top_level_full_states = [
        entry
        for entry in full_state_entries
        if Path(str(entry["path"])).parent == Path("outputs/checkpoints")
    ]
    nested_full_states = [
        entry for entry in full_state_entries if entry not in top_level_full_states
    ]
    top_level_apparent = sum(
        int(entry["apparent_size_bytes"]) for entry in top_level_full_states
    )
    nested_apparent = sum(
        int(entry["apparent_size_bytes"]) for entry in nested_full_states
    )

    report = {
        "phase": "Phase 7 recursive checkpoint inventory",
        "evidence": "[V-inventory]+[A-classification]+[O]",
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "scope": {
            "recursive_checkpoint_root": "outputs/checkpoints",
            "regular_files_recursive": True,
            "symbolic_links_followed": False,
            "reference_roots": ["outputs/*.json", "docs/**/*.md", "scripts/**/*.py"],
            "excluded_self_generated_files": [
                relative(INVENTORY_PATH),
                relative(DOCUMENT_PATH),
                relative(SCRIPT_PATH),
            ],
            "hashes_computed_for_checkpoint_tree": False,
            "checkpoint_content_bytes_read": 0,
            "metadata_only_checkpoint_operations": [
                "recursive directory listing",
                "stat apparent size",
                "stat allocated blocks",
            ],
            "snapshot_is_not_atomic_while_manifest_running": False,
        },
        "active_phase": {
            "protocol_path": relative(PROTOCOL_PATH),
            "phase": protocol["phase"],
            "summary_path": relative(SUMMARY_PATH),
            "summary_status_at_snapshot": (
                "finite_trial_rejected"
                if summary["decision"]["finite_trial_rejected"]
                else "unknown"
            ),
            "expected_full_state_size_bytes": expected_size,
            "declared_roles": role_paths,
            "runtime_roles_at_snapshot": runtime_paths,
        },
        "storage_categories": {
            "definitions": {
                "full-state-dat": (
                    "A .dat ordinary file whose apparent size exactly matches the "
                    "active protocol full radiation-state byte size."
                ),
                "block-chunk-state": (
                    "A smaller .dat block or an .npz block/chunk state."
                ),
                "json-report": "A JSON manifest, worker report, or diagnostic ledger.",
                "other": "Any remaining ordinary file under the checkpoint tree.",
            },
            "summary": category_summaries,
        },
        "recursive_tree_summary": {
            "regular_file_count": len(files),
            "directory_count_including_root": 1
            + sum(
                1
                for path in CHECKPOINTS.rglob("*")
                if path.is_dir() and not path.is_symlink()
            ),
            "regular_file_apparent_size_bytes": recursive_apparent,
            "regular_file_apparent_size_gib": gib(recursive_apparent),
            "regular_file_allocated_size_bytes": recursive_allocated,
            "regular_file_allocated_size_gib": gib(recursive_allocated),
            "directory_metadata_allocated_size_bytes": directory_allocated,
            "tree_stat_allocated_size_bytes": recursive_allocated
            + directory_allocated,
            "tree_stat_allocated_size_gib": gib(
                recursive_allocated + directory_allocated
            ),
            "allocated_size_definition": "sum(st_blocks * 512)",
        },
        "top_level_vs_recursive_explanation": {
            "top_level_full_state_count": len(top_level_full_states),
            "top_level_full_state_apparent_size_bytes": top_level_apparent,
            "top_level_full_state_apparent_size_gib": gib(top_level_apparent),
            "nested_full_state_count": len(nested_full_states),
            "nested_full_state_apparent_size_bytes": nested_apparent,
            "nested_full_state_apparent_size_gib": gib(nested_apparent),
            "additional_recursive_apparent_size_bytes": recursive_apparent
            - top_level_apparent,
            "additional_recursive_apparent_size_gib": gib(
                recursive_apparent - top_level_apparent
            ),
            "interpretation": (
                "The former 112.875 GiB snapshot covered only 12 top-level full-state "
                ".dat files. The current snapshot is recomputed rather than frozen to "
                "that historical count. Recursive accounting also includes nested "
                "full-state work buffers, block/chunk states, and JSON reports."
            ),
        },
        "reference_scan": {
            "applies_only_to_full_state_paths": True,
            "source_file_count": len(scanned_sources),
            "source_bytes_read": scanned_bytes,
            "direct_reference_definition": (
                "An exact root-relative checkpoint path, plus basename-only references "
                "only when that basename is unique among recursive full states."
            ),
            "duplicate_basename_only_references_are_ambiguous": True,
            "dynamic_references_not_resolved": True,
        },
        "full_state_summary": {
            "checkpoint_count": len(full_state_entries),
            "classification_counts": class_counts,
        },
        "classifications": {
            "active": (
                "Retained as previous converged, final converged, or residual-audit "
                "output by the current Phase 7B9dd decision chain; this does not imply "
                "that a process is running."
            ),
            "referenced": (
                "Not active, but named directly by at least one scanned JSON, document, "
                "or script."
            ),
            "unreferenced-candidate": (
                "A full state with no resolved direct textual reference; this is not a "
                "deletion authorization."
            ),
            "unknown": (
                "A full state with only ambiguous duplicate-basename references, so its "
                "dependency cannot be assigned safely."
            ),
        },
        "full_state_checkpoints": full_state_entries,
        "cleanup_authorization": {
            "files_deleted": False,
            "safe_to_delete_claim_made": False,
            "requires_phase7_convergence": True,
            "requires_final_hash_audit": True,
            "requires_final_dependency_audit": True,
            "requires_user_approval": True,
            "note": (
                "No class in this inventory is a deletion list. Final cleanup must wait "
                "for Phase 7 convergence, then repeat hash and dependency audits and "
                "obtain explicit user approval."
            ),
        },
    }
    INVENTORY_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
