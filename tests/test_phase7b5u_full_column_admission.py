import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
PROTOCOL_SHA256 = (
    "895225b50a7feccd5563dec5ef580947e90bca4f48c08d0e2eef9ed9e60d363c"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _summary() -> dict[str, object]:
    return json.loads(
        (OUTPUT / "phase7b5u_full_column_admission.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5u_protocol_and_recorded_source_hashes_are_frozen():
    protocol_path = OUTPUT / "phase7b5u_preregistered_full_column_admission.json"
    assert _sha256(protocol_path) == PROTOCOL_SHA256
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    assert protocol["sources"]["phase7b4r_material"]["sha256"] == (
        "33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455"
    )
    assert protocol["sources"]["phase7b5t_summary"]["sha256"] == (
        "5c29b4563913fd9c7eddfba9f7d7f20f53604d0cba6042243a8d2358563bf61f"
    )


def test_phase7b5u_full_column_shape_and_memory_decision():
    summary = _summary()
    full = summary["full_column"]
    assert full["orbital_phase_count"] == 2048
    assert full["material_cell_count"] == 256
    assert full["radiation_depth_cell_count"] == 4096
    assert full["physical_frequency_groups"] == 9632
    assert full["angular_direction_count"] == 32
    assert full["radiation_unknown_count"] == 1_262_485_504
    assert full["single_active_intensity_array_bytes"] == 10_099_884_032
    memory = summary["memory"]
    assert memory["identified_live_array_bytes"] == 90_911_907_840
    assert memory["identified_live_over_physical_memory"] > 5.0
    assert memory["monolithic_memory_admitted"] is False


def test_phase7b5u_turning_ray_decision_uses_all_phases():
    summary = _summary()
    characteristic = summary["characteristics"]
    assert characteristic["reversing_phase_count"] == 586
    assert np.isclose(characteristic["reversing_phase_fraction"], 586 / 2048)
    assert characteristic["maximum_reversing_direction_count"] == 2
    assert np.isclose(
        characteristic["maximum_reversing_angular_weight_fraction"],
        0.013576229705877027,
        rtol=2.0e-14,
    )
    assert characteristic["pure_step_characteristics_admitted"] is False


def test_phase7b5u_integrity_passes_but_production_does_not():
    decision = _summary()["decision"]
    assert decision["audit_integrity_passed"] is True
    assert decision["monolithic_full_column_admitted"] is False
    assert decision["pure_step_full_column_admitted"] is False
    assert decision["requires_frequency_streaming"] is True
    assert decision["requires_turning_ray_treatment"] is True
    assert decision["production_full_column_admitted"] is False


def test_phase7b5u_outputs_exist_and_are_nonempty():
    for name in (
        "phase7b5u_characteristic_phases.csv",
        "phase7b5u_memory_arrays.csv",
        "phase7b5u_full_column_admission.png",
    ):
        path = OUTPUT / name
        assert path.exists()
        assert path.stat().st_size > 0
