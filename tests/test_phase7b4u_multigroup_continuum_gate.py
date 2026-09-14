from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts.phase7b4u_multigroup_continuum_gate import (
    _load_states,
    _physical_group_edges,
    run_all,
)


def test_phase7b4u_physical_groups_exclude_but_preserve_guard_band():
    expected = {32: (153, 155), 64: (303, 305), 128: (604, 606), 256: (1205, 1209)}
    for groups_per_decade, counts in expected.items():
        edge, physical, extended = _physical_group_edges(groups_per_decade)
        assert (physical, extended) == counts
        assert edge.size == physical + 1


def test_phase7b4u_state_sample_includes_stress_and_extreme_phases():
    states, phase_indices, _ = _load_states(
        PROJECT_ROOT / "outputs" / "phase7b4r_depth128_phase2048.npz"
    )
    assert len(states) == phase_indices.size * 8
    assert 628 in phase_indices
    assert 1367 in phase_indices
    assert 1025 in phase_indices
    assert {state.depth_index for state in states} == {0, 1, 8, 24, 42, 64, 96, 127}


def test_phase7b4u_saved_decision_retains_near_threshold_failure():
    report = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4u_summary.json").read_text(
            encoding="utf-8"
        )
    )
    decision = report["decision"]
    assert decision["153_physical_groups_accepted"] is False
    assert decision["303_physical_groups_accepted"] is False
    assert decision["604_physical_groups_accepted"] is False
    assert decision["1205_physical_groups_accepted"] is True
    assert decision["selected_physical_frequency_groups"] == 1205
    assert decision["fully_coupled_mixed_frame_ale_authorized"] is True
    assert decision["full_dynamic_orbit_authorized"] is False


def test_phase7b4u_script_uses_no_forbidden_repairs():
    source = inspect.getsource(run_all)
    module_source = (
        PROJECT_ROOT / "scripts" / "phase7b4u_multigroup_continuum_gate.py"
    ).read_text(encoding="utf-8")
    assert "nan_to_num" not in source
    assert "np.clip" not in module_source
    assert '"full_dynamic_orbit_authorized": False' in source
