from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from eccentric_tde_observer import (
    MixedFrameALEStep,
    MixedFrameFrequencyStencil,
    mixed_frame_frequency_stencil,
    solve_mixed_frame_ale_group_step,
)
from scripts.phase7b4v_mixed_frame_ale_gate import (
    analytic_control_rows,
    run_all,
)


def test_phase7b4v_stencil_has_physical_collision_and_outer_guard_groups():
    stencil = mixed_frame_frequency_stencil(
        0.1, 5000.0, 256, 0.008028600886554787
    )
    assert isinstance(stencil, MixedFrameFrequencyStencil)
    assert stencil.physical_group_count == 1205
    assert stencil.comoving_collision_group_count == 1207
    assert stencil.outer_lab_group_count == 1209
    assert callable(solve_mixed_frame_ale_group_step)
    assert MixedFrameALEStep.__name__ == "MixedFrameALEStep"


def test_phase7b4v_analytic_operator_controls_pass_without_approving_orbit():
    controls, diffusion = analytic_control_rows()
    assert len(controls) == 3
    assert len(diffusion) == 3
    assert all(bool(row["passed"]) for row in controls)
    assert all(bool(row["passed"]) for row in diffusion)
    assert all(float(row["beta_tau"]) > 1.0 for row in diffusion)


def test_phase7b4v_saved_decision_retains_1205_frequency_failure():
    report = json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b4v_summary.json").read_text(
            encoding="utf-8"
        )
    )
    decision = report["decision"]
    assert decision["full_lorentz_ale_operator_gate_passed"] is True
    assert decision["actual_1205_vs_38496_frequency_gate_passed"] is False
    assert decision["minimum_one_cell_passing_physical_frequency_groups"] == 19249
    assert decision["1205_group_mixed_frame_ale_component_gate_passed"] is False
    assert decision["selected_dynamic_physical_frequency_groups"] is None
    assert decision["frequency_representation_refinement_required"] is True
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert report["maximum_1205_vs_38496_actual_error"] > 1.0e-3


def test_phase7b4v_code_uses_no_forbidden_repairs_or_hidden_approval():
    module_source = (
        PROJECT_ROOT / "src" / "eccentric_tde_observer" / "mixed_frame_ale.py"
    ).read_text(encoding="utf-8")
    script_source = inspect.getsource(run_all)
    assert "nan_to_num" not in module_source
    assert "np.clip" not in module_source
    assert '"full_dynamic_orbit_authorized": False' in script_source
    assert '"selected_dynamic_physical_frequency_groups": None' in script_source
