from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from eccentric_tde_observer.joint_dynamic_reference import (
    JointDynamicError,
    dynamic_reference_fields,
)
from scripts.phase7b4n_joint_depth_time_reference import case_paths
from scripts.phase7b4q_threshold_quadrature import DEPTH_REFERENCE_CASE
from scripts.phase7b4r_n128_time_reference import (
    REFERENCE_CASE,
    diagnostic_error_locations,
    n128_time_gate_decision,
)


def _error(scale: float, *, front_mismatch: int = 0) -> JointDynamicError:
    return JointDynamicError(
        surface_flux_relative_error=scale,
        maximum_pointwise_temperature_or_opacity_relative_error=0.8 * scale,
        maximum_pointwise_population_absolute_error=0.6 * scale,
        maximum_column_mean_temperature_or_opacity_relative_error=0.4 * scale,
        maximum_column_mean_population_absolute_error=0.2 * scale,
        front_status_mismatch_phase_count=front_mismatch,
        joint_unique_front_phase_count=4,
        maximum_he_iii_half_front_mass_fraction_error=0.1 * scale,
    )


def _case_report(*, cycle: bool = True, conserve: bool = True):
    return {
        "decision": {
            "cycle_converged": cycle,
            "initial_and_restriction_conservation_passed": conserve,
        }
    }


def _inherited(*, formal: bool = True):
    return {
        "decision": {
            "phase7b4q_selected_formal_configuration_passed": formal,
        }
    }


def _fields(phase_points: int, *, helium_offset: float = 0.0):
    phase = np.arange(phase_points) / phase_points
    edges = np.array([0.0, 0.5, 1.0])
    modulation = 1.0 + 0.01 * np.sin(2.0 * np.pi * phase)
    temperature = modulation[:, None] * np.array([[2.0e4, 3.0e4]])
    opacity = modulation[:, None] * np.array([[0.2, 0.3]])
    h_ii = np.full((phase_points, 2), 0.8)
    he_iii = np.tile(np.array([0.7, 0.3]), (phase_points, 1))
    he_iii[-1, 0] += helium_offset
    return dynamic_reference_fields(
        phase,
        edges,
        np.array([2.0, 2.0]),
        temperature,
        opacity,
        h_ii,
        he_iii,
        3.0e14 * modulation,
    )


def test_phase7b4r_paths_isolate_n128_time_reference(tmp_path: Path) -> None:
    assert case_paths(tmp_path, DEPTH_REFERENCE_CASE)[0].name == (
        "phase7b4q_depth128_phase1024.npz"
    )
    assert case_paths(tmp_path, REFERENCE_CASE)[0].name == (
        "phase7b4r_depth128_phase2048.npz"
    )


def test_n128_time_gate_requires_every_independent_gate() -> None:
    passed = n128_time_gate_decision(
        _error(3.0e-4),
        _case_report(),
        _case_report(),
        _inherited(),
    )
    assert passed["n128_material_depth_time_gate_passed"]

    failed_time = n128_time_gate_decision(
        _error(3.0e-4, front_mismatch=1),
        _case_report(),
        _case_report(),
        _inherited(),
    )
    assert not failed_time[
        "n128_phase1024_vs_phase2048_time_difference_below_target"
    ]
    assert not failed_time["n128_material_depth_time_gate_passed"]

    failed_conservation = n128_time_gate_decision(
        _error(3.0e-4),
        _case_report(),
        _case_report(conserve=False),
        _inherited(),
    )
    assert not failed_conservation["both_n128_cases_conserve"]
    assert not failed_conservation["n128_material_depth_time_gate_passed"]


def test_diagnostic_error_locations_preserve_metric_phase_and_depth() -> None:
    rows = diagnostic_error_locations(
        _fields(4),
        _fields(8, helium_offset=2.0e-4),
    )
    assert len(rows) == 9
    helium = next(row for row in rows if row["metric"] == "He III fraction")
    assert helium["error_kind"] == "absolute"
    assert helium["phase_index"] == 7
    assert helium["depth_index"] == 0
    assert np.isclose(helium["maximum_error"], 2.0e-4)


def test_phase7b4r_script_calls_no_forbidden_numerical_repairs() -> None:
    path = Path("scripts/phase7b4r_n128_time_reference.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
