from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SCRIPT = ROOT / "scripts/phase7b9dg_authorize_storage_reuse.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("phase7b9dg", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_frozen_authorization_records_exact_verified_targets() -> None:
    protocol = json.loads(
        (OUTPUT / "phase7b9dg_preregistered_storage_reuse.json").read_text()
    )
    preflight = json.loads(
        (OUTPUT / "phase7b9df_storage_reuse_preflight.json").read_text()
    )
    expected = {
        row["path"]: row["frozen_sha256_claim"] for row in preflight["targets"]
    }
    targets = protocol["configuration"]["targets"]
    assert {row["path"]: row["verified_current_sha256"] for row in targets} == expected
    assert {row["future_role"] for row in targets} == {"buffer_a", "buffer_b"}
    assert protocol["authorization"]["destructive_reuse_authorized"] is True
    assert protocol["authorization"]["overwrite_only_exact_named_targets"] is True
    assert len(protocol["configuration"]["protected_current_chain"]) == 3


def test_builder_rejects_hash_drift_without_reading_checkpoints() -> None:
    module = _load_module()
    preflight = json.loads(module.PREFLIGHT.read_text())
    inventory = json.loads(module.INVENTORY.read_text())
    hashes = {
        row["path"]: row["frozen_sha256_claim"] for row in preflight["targets"]
    }
    broken = copy.deepcopy(hashes)
    broken[next(iter(broken))] = "0" * 64
    with pytest.raises(RuntimeError, match="hash mismatch"):
        module.build_protocol(
            preflight,
            inventory,
            broken,
            generated_at_utc="test",
        )


def test_authorization_does_not_expand_destructive_scope() -> None:
    protocol = json.loads(
        (OUTPUT / "phase7b9dg_preregistered_storage_reuse.json").read_text()
    )
    assert protocol["authorization"]["delete_unrelated_files"] is False
    assert protocol["authorization"]["modify_protected_current_chain"] is False
    assert protocol["authorization"][
        "historical_bytes_become_unrecoverable_without_recomputation"
    ] is True
    assert all(
        value is False
        for value in protocol["authorization"]["numerical_repair"].values()
    )
