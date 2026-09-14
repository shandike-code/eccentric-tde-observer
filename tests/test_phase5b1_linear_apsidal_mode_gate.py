from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (
            PROJECT_ROOT
            / "outputs"
            / "phase5b1_linear_apsidal_report.json"
        ).read_text(encoding="utf-8")
    )


def test_phase5b1_linear_small_e_gate_passes_independent_controls() -> None:
    report = _report()
    decision = report["decision"]
    assert decision["all_strong_form_modes_are_node_free"] is True
    assert decision["strong_weak_gate_passed"] is True
    assert decision["radial_convergence_gate_passed"] is True
    assert decision["free_boundary_gate_passed"] is True
    assert decision["symmetric_positive_mass_gate_passed"] is True
    assert decision["uniform_external_precession_shift_gate_passed"] is True
    assert decision["linear_small_e_solver_verified"] is True
    assert report["aggregate"][
        "maximum_finest_grid_strong_weak_relative_error"
    ] < 3.0e-6
    assert report["aggregate"][
        "maximum_256_to_512_relative_frequency_change"
    ] < 1.0e-5


def test_phase5b1_preserves_raw_and_extrapolated_boundary_diagnostics() -> None:
    report = _report()
    aggregate = report["aggregate"]
    assert aggregate["maximum_512_point_piecewise_robin_residual"] > 3.0e-3
    assert aggregate["maximum_512_point_extrapolated_robin_residual"] < 2.0e-5
    assert all(
        "inner_robin_residual" in row
        and "outer_robin_residual" in row
        and "inner_extrapolated_robin_residual" in row
        and "outer_extrapolated_robin_residual" in row
        for row in report["convergence_rows"]
    )


def test_phase5b1_eq40_closes_but_printed_eq48_differs_by_ten() -> None:
    report = _report()
    decision = report["decision"]
    scale = report["scale_audit"]
    assert decision["eq40_dimensionless_gr_scale_reproduced"] is True
    assert decision[
        "printed_eq48_normalization_matches_direct_eq39_ledger"
    ] is False
    assert np.isclose(
        scale["printed_to_direct_frequency_ratio"],
        10.0,
        rtol=2.0e-4,
    )


def test_phase5b1_does_not_authorize_high_e_time_mapping() -> None:
    decision = _report()["decision"]
    assert decision["phase5b2_nonlinear_kernel_authorized"] is True
    assert decision["high_e_zo_mode_reproduced"] is False
    assert decision["strict_domain_phase_to_time_mapping_authorized"] is False


def test_phase5b1_outputs_exist_and_are_nonempty() -> None:
    for relative in (
        "outputs/phase5b1_linear_apsidal_convergence.csv",
        "outputs/phase5b1_local_gr_profile.csv",
        "outputs/phase5b1_linear_eigenfunctions.png",
        "outputs/phase5b1_linear_convergence.png",
        "outputs/phase5b1_precession_scale_audit.png",
    ):
        path = PROJECT_ROOT / relative
        assert path.is_file()
        assert path.stat().st_size > 0


def test_phase5b1_contains_no_forbidden_numerical_repairs() -> None:
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "apsidal_precession.py",
        PROJECT_ROOT
        / "scripts"
        / "phase5b1_linear_apsidal_mode_gate.py",
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
