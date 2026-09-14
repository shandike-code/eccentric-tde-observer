from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (
            PROJECT_ROOT
            / "outputs"
            / "phase5b2_nonlinear_hamiltonian_report.json"
        ).read_text(encoding="utf-8")
    )


def test_phase5b2_local_hamiltonian_gate_passes_all_controls() -> None:
    report = _report()
    decision = report["decision"]
    for key in (
        "circular_limit_passed",
        "constant_e_existing_solver_regression_passed",
        "signed_state_symmetry_passed",
        "corrected_linear_hamiltonian_limit_passed",
        "five_point_derivative_stability_passed",
        "vertical_tolerance_gate_passed",
        "periodic_vertical_boundary_gate_passed",
        "all_surface_states_positive_without_repairs",
        "nonlinear_local_hamiltonian_verified",
        "phase5b3_nonlinear_bvp_authorized",
    ):
        assert decision[key] is True


def test_phase5b2_preserves_high_e_global_mode_boundary() -> None:
    decision = _report()["decision"]
    assert decision["published_high_e_mode_reproduced"] is False
    assert decision["strict_domain_phase_to_time_mapping_authorized"] is False


def test_phase5b2_surface_and_vertical_controls_are_strict() -> None:
    aggregate = _report()["aggregate"]
    assert aggregate["surface_state_count"] == 130
    assert aggregate["minimum_surface_height"] > 0.0
    assert aggregate["maximum_surface_apoapsis_boundary_residual"] < 1.0e-8
    assert aggregate["maximum_constant_e_height_relative_difference"] < 2.0e-10
    assert aggregate["maximum_signed_symmetry_relative_difference"] < 1.0e-11
    assert aggregate[
        "maximum_vertical_tolerance_relative_hamiltonian_difference"
    ] < 2.0e-9


def test_phase5b2_linear_and_derivative_limits_pass() -> None:
    aggregate = _report()["aggregate"]
    assert aggregate["linear_remainder_logarithmic_slope"] > 3.9
    assert aggregate["maximum_derivative_vector_relative_change"] < 1.0e-5
    rows = _report()["derivative_convergence"]
    assert {row["state"] for row in rows} == {"moderate", "strong", "high-e"}
    assert {row["evaluated_state_count"] for row in rows} == {25}


def test_phase5b2_outputs_exist_and_are_nonempty() -> None:
    for relative in (
        "outputs/phase5b2_hamiltonian_surface.csv",
        "outputs/phase5b2_derivative_convergence.csv",
        "outputs/phase5b2_hamiltonian_surface.png",
        "outputs/phase5b2_vertical_breathing_profiles.png",
        "outputs/phase5b2_local_hamiltonian_controls.png",
    ):
        path = PROJECT_ROOT / relative
        assert path.is_file()
        assert path.stat().st_size > 0


def test_phase5b2_contains_no_forbidden_numerical_repairs() -> None:
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "nonlinear_hamiltonian.py",
        PROJECT_ROOT
        / "scripts"
        / "phase5b2_nonlinear_hamiltonian_gate.py",
    )
    calls: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls.update(
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        )
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
