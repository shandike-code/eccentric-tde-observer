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
from scripts.phase7b4n_joint_depth_time_reference import (
    CaseSpec,
    case_paths,
    case_phase_label,
)
from scripts.phase7b4o_high_depth_time_reference import (
    population_error_locations,
    time_convergence_rows,
)


def _error(scale: float) -> JointDynamicError:
    return JointDynamicError(
        surface_flux_relative_error=scale,
        maximum_pointwise_temperature_or_opacity_relative_error=0.8 * scale,
        maximum_pointwise_population_absolute_error=0.6 * scale,
        maximum_column_mean_temperature_or_opacity_relative_error=0.4 * scale,
        maximum_column_mean_population_absolute_error=0.2 * scale,
        front_status_mismatch_phase_count=0,
        joint_unique_front_phase_count=4,
        maximum_he_iii_half_front_mass_fraction_error=0.1 * scale,
    )


def _fields(phase_points: int, he_offset: float = 0.0):
    phase = np.arange(phase_points) / phase_points
    edges = np.array([0.0, 0.5, 1.0])
    modulation = 1.0 + 0.01 * np.sin(2.0 * np.pi * phase)
    temperature = modulation[:, None] * np.array([[2.0e4, 3.0e4]])
    opacity = modulation[:, None] * np.array([[0.2, 0.3]])
    h_ii = np.full((phase_points, 2), 0.8)
    he_iii = np.tile(np.array([0.7, 0.3]), (phase_points, 1))
    he_iii[-1, 0] += he_offset
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


def test_case_paths_keep_phase7b4n_compatible_and_isolate_phase7b4o(
    tmp_path: Path,
) -> None:
    inherited = CaseSpec("depth64_phase1024", 1024, 64)
    reference = CaseSpec("depth64_phase2048", 2048, 64, "phase7b4o")
    assert case_paths(tmp_path, inherited)[0].name == (
        "phase7b4n_depth64_phase1024.npz"
    )
    assert case_paths(tmp_path, reference)[0].name == (
        "phase7b4o_depth64_phase2048.npz"
    )
    assert case_phase_label(inherited) == "7B4n-case"
    assert case_phase_label(reference) == "7B4o-case"


def test_time_convergence_rows_report_gate_and_finite_reduction() -> None:
    coarse = CaseSpec("coarse", 512, 64)
    intermediate = CaseSpec("intermediate", 1024, 64)
    reference = CaseSpec("reference", 2048, 64, "phase7b4o")
    rows = time_convergence_rows(
        [
            (coarse, intermediate, _error(1.2e-3)),
            (intermediate, reference, _error(3.0e-4)),
        ]
    )
    assert not rows[0]["meets_production_target"]
    assert rows[1]["meets_production_target"]
    assert np.isclose(
        rows[1][
            "previous_over_current_maximum_pointwise_population_absolute_error"
        ],
        4.0,
    )


def test_population_error_locations_preserve_failed_phase_and_depth() -> None:
    candidate = _fields(4)
    reference = _fields(8, he_offset=2.0e-4)
    rows = population_error_locations(
        candidate,
        reference,
        CaseSpec("candidate", 4, 2),
        CaseSpec("reference", 8, 2, "phase7b4o"),
    )
    helium = next(row for row in rows if row["population"] == "He III")
    assert helium["phase_index"] == 7
    assert helium["depth_index"] == 0
    assert np.isclose(helium["maximum_absolute_error"], 2.0e-4)


def test_phase7b4o_script_calls_no_forbidden_numerical_repairs() -> None:
    path = Path("scripts/phase7b4o_high_depth_time_reference.py")
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
