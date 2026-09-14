"""Phase 7B9de 第一次二分物质回溯回归。"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase7b9de_protocol_freezes_one_half_trial() -> None:
    protocol_path = OUTPUT / "phase7b9de_preregistered_half_trial_material.json"
    protocol = json.loads(protocol_path.read_text())
    cfg = protocol["configuration"]
    assert cfg["failed_absolute_relaxation"] == 0.125
    assert cfg["backtrack_factor"] == 0.5
    assert cfg["candidate_absolute_relaxation"] == 0.0625
    assert protocol["authorization"]["build_exactly_one_material_candidate"] is True
    assert protocol["authorization"]["evaluate_radiation_in_this_stage"] is False
    assert protocol["authorization"]["accept_dynamic_nlte_solution"] is False
    for row in protocol["sources"].values():
        path = ROOT / row["path"]
        assert path.stat().st_size == row["size_bytes"]
        assert sha256(path) == row["sha256"]


def test_phase7b9de_candidate_follows_frozen_encoded_definition() -> None:
    summary = json.loads(
        (OUTPUT / "phase7b9de_half_trial_material_summary.json").read_text()
    )
    with np.load(OUTPUT / "phase7b9de_half_trial_material_state.npz") as state:
        expected = state["base_encoded_state"] + float(state["relaxation"]) * state[
            "finite_direction"
        ]
        assert np.array_equal(state["encoded_state"], expected)
        assert float(state["relaxation"]) == 0.0625
        assert np.all(state["temperature_k"] > 0.0)
        assert np.all(state["specific_material_energy_erg_g"] > 0.0)
        assert np.all(state["hydrogen_fraction"] >= 0.0)
        assert np.all(state["helium_fraction"] >= 0.0)
        bound = 4.0 * np.finfo(np.float64).eps
        assert np.max(
            np.abs(np.sum(state["hydrogen_fraction"], axis=1) - 1.0)
        ) < bound
        assert np.max(
            np.abs(np.sum(state["helium_fraction"], axis=1) - 1.0)
        ) < bound
    assert sha256(ROOT / summary["candidate_path"]) == summary["candidate_sha256"]
    assert all(summary["gate_checks"].values())
    assert summary["decision"]["candidate_full_frequency_radiation_authorized"] is True
    assert summary["decision"]["candidate_accepted_as_nonlinear_step"] is False


def test_phase7b9de_builder_has_no_numerical_repair_calls() -> None:
    tree = ast.parse(
        (ROOT / "scripts/phase7b9de_build_half_trial_material.py").read_text()
    )
    names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "nan_to_num" not in names
    assert "clip" not in names
    assert "maximum" not in names
