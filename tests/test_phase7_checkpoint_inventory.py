"""Phase 7 递归检查点只读清单回归。"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
CHECKPOINTS = OUTPUT / "checkpoints"


def inventory() -> dict[str, object]:
    return json.loads((OUTPUT / "phase7_checkpoint_inventory.json").read_text())


def test_phase7_inventory_recursively_accounts_for_every_regular_file() -> None:
    data = inventory()
    files = [
        path
        for path in CHECKPOINTS.rglob("*")
        if path.is_file() and not path.is_symlink()
    ]
    summary = data["recursive_tree_summary"]
    assert summary["regular_file_count"] == len(files)
    assert summary["regular_file_apparent_size_bytes"] == sum(
        path.stat().st_size for path in files
    )
    assert summary["regular_file_allocated_size_bytes"] == sum(
        path.stat().st_blocks * 512 for path in files
    )
    assert summary["tree_stat_allocated_size_bytes"] == (
        summary["regular_file_allocated_size_bytes"]
        + summary["directory_metadata_allocated_size_bytes"]
    )


def test_phase7_inventory_covers_every_recursive_full_state() -> None:
    data = inventory()
    expected_size = data["active_phase"]["expected_full_state_size_bytes"]
    actual = sorted(
        str(path.relative_to(ROOT))
        for path in CHECKPOINTS.rglob("*.dat")
        if path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == expected_size
    )
    recorded = sorted(entry["path"] for entry in data["full_state_checkpoints"])
    assert recorded == actual
    assert data["full_state_summary"]["checkpoint_count"] == len(actual)


def test_phase7_inventory_storage_categories_close_top_level_gap() -> None:
    data = inventory()
    categories = data["storage_categories"]["summary"]
    assert set(categories) == {
        "full-state-dat",
        "block-chunk-state",
        "json-report",
        "other",
    }
    assert sum(row["file_count"] for row in categories.values()) == data[
        "recursive_tree_summary"
    ]["regular_file_count"]
    assert sum(
        row["apparent_size_bytes"] for row in categories.values()
    ) == data["recursive_tree_summary"]["regular_file_apparent_size_bytes"]
    explanation = data["top_level_vs_recursive_explanation"]
    assert (
        explanation["top_level_full_state_count"]
        + explanation["nested_full_state_count"]
        == data["full_state_summary"]["checkpoint_count"]
    )
    assert explanation["top_level_full_state_count"] >= 12
    assert explanation["nested_full_state_count"] > 0
    assert data["recursive_tree_summary"]["regular_file_apparent_size_bytes"] > (
        explanation["top_level_full_state_apparent_size_bytes"]
    )


def test_phase7_inventory_identifies_current_protected_roles() -> None:
    data = inventory()
    roles = {
        role: entry["path"]
        for entry in data["full_state_checkpoints"]
        for role in entry["active_phase7b9dd_roles"]
    }
    assert roles == {
        "previous_converged": (
            "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"
        ),
        "final_converged": (
            "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
        ),
        "residual_audit_output": (
            "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
        ),
    }
    assert data["full_state_summary"]["classification_counts"]["active"] == 3
    assert data["active_phase"]["summary_status_at_snapshot"] == (
        "finite_trial_rejected"
    )
    assert data["active_phase"]["runtime_roles_at_snapshot"] == {}


def test_phase7_inventory_only_uses_declared_non_destructive_classes() -> None:
    data = inventory()
    allowed = {"active", "referenced", "unreferenced-candidate", "unknown"}
    assert {
        entry["classification"] for entry in data["full_state_checkpoints"]
    } <= allowed
    assert sum(data["full_state_summary"]["classification_counts"].values()) == data[
        "full_state_summary"
    ]["checkpoint_count"]
    for entry in data["full_state_checkpoints"]:
        assert entry["direct_referencer_count"] == len(
            entry["direct_referencers"]
        )
        assert entry["direct_reference_occurrence_count"] >= entry[
            "direct_referencer_count"
        ]
    authorization = data["cleanup_authorization"]
    assert not authorization["files_deleted"]
    assert not authorization["safe_to_delete_claim_made"]
    assert authorization["requires_phase7_convergence"]
    assert authorization["requires_final_hash_audit"]
    assert authorization["requires_final_dependency_audit"]
    assert authorization["requires_user_approval"]


def test_phase7_inventory_does_not_read_or_hash_checkpoint_contents() -> None:
    data = inventory()
    assert not data["scope"]["hashes_computed_for_checkpoint_tree"]
    assert data["scope"]["checkpoint_content_bytes_read"] == 0
    tree = ast.parse((ROOT / "scripts/phase7_checkpoint_inventory.py").read_text())
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "hashlib" not in imported_modules
    assert {"read_bytes", "unlink", "rename", "replace"}.isdisjoint(attributes)


def test_phase7_inventory_document_rejects_early_cleanup() -> None:
    document = (ROOT / "docs/phase7_checkpoint_inventory.md").read_text()
    assert "112.875 GiB" in document
    assert "218.0291 GiB" in document
    assert "不写“可安全删除”" in document
    assert "Phase 7 收敛完成" in document
    assert "获得用户明确批准" in document
    assert "[A-classification]" in document
    assert "[O]" in document
