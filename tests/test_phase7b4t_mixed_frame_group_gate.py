import inspect
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scripts.phase7b4t_mixed_frame_group_gate import (
    angular_lorentz_controls,
    frequency_group_controls,
    run_all,
)


def test_phase7b4t_exact_lorentz_angular_control_passes_at_s16():
    rows = angular_lorentz_controls(0.008028600886554787)
    production = [
        row
        for row in rows
        if row["control"] == "ZO maximum" and row["angular_order"] == 16
    ]
    assert len(production) == 1
    assert float(production[0]["maximum_relative_error"]) < 1.0e-10


def test_phase7b4t_conservative_group_remap_converges_in_integrated_energy():
    rows = frequency_group_controls(0.008028600886554787)
    physical_groups = [int(row["physical_groups"]) for row in rows]
    integrated_error = [
        float(row["maximum_integrated_relative_error"]) for row in rows
    ]
    assert physical_groups == [40, 78, 153, 303]
    assert all(
        finer < coarser
        for coarser, finer in zip(integrated_error, integrated_error[1:])
    )
    assert integrated_error[-1] < 1.0e-3


def test_phase7b4t_saved_scientific_decisions_preserve_scope_boundary():
    summary_path = PROJECT_ROOT / "outputs" / "phase7b4t_summary.json"
    report = json.loads(summary_path.read_text(encoding="utf-8"))
    decision = report["decision"]
    assert decision["phase7b4t_component_gates_passed"] is True
    assert decision["153_physical_group_dynamic_candidate_accepted"] is False
    assert decision["303_physical_group_dynamic_candidate_accepted"] is True
    assert decision["phase7b4q_160_node_grid_reusable_for_doppler_remap"] is False
    assert decision["full_160_frequency_dynamic_orbit_authorized"] is False


def test_phase7b4t_gate_does_not_hide_invalid_values():
    source = inspect.getsource(run_all)
    module_source = (PROJECT_ROOT / "scripts" / "phase7b4t_mixed_frame_group_gate.py").read_text(
        encoding="utf-8"
    )
    assert "nan_to_num" not in source
    assert "np.clip" not in module_source
    assert '"full_160_frequency_dynamic_orbit_authorized": False' in source
