"""Phase 7B9df 非破坏性存储复用预检。"""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def report() -> dict[str, object]:
    return json.loads((OUTPUT / "phase7b9df_storage_reuse_preflight.json").read_text())


def test_preflight_identifies_two_non_active_full_states() -> None:
    data = report()
    assert data["candidate_reuse_total_gib"] == 18.8125
    assert len(data["targets"]) == 2
    assert all(row["current_size_bytes"] == 10_099_884_032 for row in data["targets"])
    assert all(row["current_protected_roles"] == [] for row in data["targets"])
    assert all(row["inventory_classification"] == "referenced" for row in data["targets"])
    assert all(row["direct_referencer_count"] > 0 for row in data["targets"])
    assert all(not row["current_sha256_recomputed"] for row in data["targets"])


def test_preflight_does_not_authorize_reuse() -> None:
    data = report()
    assert data["decision"]["metadata_preflight_passed"] is True
    assert data["gate_checks"]["current_hash_recheck_complete"] is False
    assert data["gate_checks"]["explicit_user_reuse_approval_recorded"] is False
    assert data["decision"]["destructive_reuse_authorized"] is False
    assert data["decision"]["reuse_may_start_without_current_hash_recheck"] is False
    assert data["decision"]["reuse_may_start_without_explicit_user_approval"] is False


def test_preflight_source_cannot_read_or_mutate_checkpoints() -> None:
    tree = ast.parse(
        (ROOT / "scripts/phase7b9df_storage_reuse_preflight.py").read_text()
    )
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "hashlib" not in imports
    assert {"read_bytes", "unlink", "rename", "replace"}.isdisjoint(attributes)
    assert report()["scope"]["checkpoint_content_bytes_read"] == 0
    assert report()["scope"]["checkpoint_files_deleted"] is False
    assert report()["scope"]["checkpoint_files_modified"] is False
