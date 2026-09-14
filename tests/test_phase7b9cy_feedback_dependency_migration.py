"""Phase 7B9cy 单一依赖迁移的精确重建与正路径回归。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9cy_refresh_feedback_worker_template.py"
SPEC = importlib.util.spec_from_file_location("phase7b9cy_migration", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not import Phase 7B9cy migration audit")
migration = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = migration
SPEC.loader.exec_module(migration)


def test_exactly_reconstructs_frozen_legacy_frequency_source() -> None:
    current = (ROOT / migration.CURRENT_FREQUENCY).read_text(encoding="utf-8")
    legacy = migration.reconstruct_legacy_frequency_source(current).encode("utf-8")
    assert len(legacy) == migration.LEGACY_FREQUENCY_SIZE
    assert migration.sha256_bytes(legacy) == migration.LEGACY_FREQUENCY_SHA256


def test_feedback_positive_path_is_array_identical() -> None:
    current = (ROOT / migration.CURRENT_FREQUENCY).read_text(encoding="utf-8")
    legacy = migration.reconstruct_legacy_frequency_source(current)
    parity = migration.positive_feedback_path_parity(legacy)
    assert all(row["array_equal"] for row in parity.values())
    assert all(row["maximum_absolute_difference"] == 0.0 for row in parity.values())


def test_feedback_worker_does_not_reference_signed_ali_interfaces() -> None:
    assert not any(migration.signed_api_references().values())
