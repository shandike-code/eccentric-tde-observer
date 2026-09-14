from __future__ import annotations

import ast
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report() -> dict[str, object]:
    return json.loads(
        (PROJECT_ROOT / "outputs" / "phase7b5c_summary.json").read_text(
            encoding="utf-8"
        )
    )


def test_phase7b5c_saved_gate_is_diagnostic_only() -> None:
    decision = _report()["decision"]
    assert decision["localization_controls_passed"] is True
    assert decision["same_dominant_region_in_all_states"] is False
    assert decision["stable_single_region_localization_passed"] is False
    assert decision["new_frequency_basis_design_authorized"] is False
    assert decision["production_frequency_representation_selected"] is False
    assert decision["angular_radiation_subgrid_time_gate_authorized"] is False
    assert decision["full_dynamic_orbit_authorized"] is False
    assert decision["matter_temperature_population_feedback_authorized"] is False
    assert decision["phase4_replacement_authorized"] is False
    assert decision["uvot_authorized"] is False


def test_phase7b5c_rate_and_decomposition_ledgers_close() -> None:
    for row in _report()["case_decomposition"]:
        assert row["candidate_native_rate_reconciliation_relative"] < 2.0e-8
        assert row["reference_native_rate_reconciliation_relative"] < 2.0e-8
        assert row["localization_quadrature_relative"] < 2.0e-10
        assert row["decomposition_ledger_relative"] < 2.0e-12
        assert row["total_signed_relative"] < 0.0
    for row in _report()["projection_audit"]:
        assert row["projection_energy_integral_relative_error"] < 2.0e-12


def test_phase7b5c_dynamic_remainder_dominates_static_compression_error() -> None:
    for row in _report()["case_decomposition"]:
        assert abs(row["compression_limiter_signed_relative"]) < 2.0e-9
        assert abs(row["dynamic_remainder_signed_relative"]) > 1.0e3 * abs(
            row["compression_limiter_signed_relative"]
        )
        assert row["final_saturated_error_fraction"] < 1.0e-12


def test_phase7b5c_moving_states_localize_to_doppler_band_but_cold_does_not() -> None:
    dominant = _report()["decision"]["dominant_region_by_case"]
    assert dominant["cold coefficient surface"]["region"] == "H I shoulder to He I"
    assert (
        dominant["cold coefficient surface"][
            "absolute_integrand_difference_fraction"
        ]
        > 0.8
    )
    for case in ("maximum cell speed", "maximum width change"):
        assert dominant[case]["region"] == "H I Doppler band"
        assert dominant[case]["absolute_integrand_difference_fraction"] > 0.5


def test_phase7b5c_uses_no_forbidden_repairs_or_hidden_approval() -> None:
    paths = (
        PROJECT_ROOT
        / "src"
        / "eccentric_tde_observer"
        / "rate_error_localization.py",
        PROJECT_ROOT
        / "scripts"
        / "phase7b5c_signed_rate_error_localization.py",
    )
    calls: set[str] = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls.update(
            ast.unparse(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        )
    source = paths[-1].read_text(encoding="utf-8")
    assert "np.nan_to_num" not in calls
    assert "np.clip" not in calls
    assert "numpy.nan_to_num" not in calls
    assert "numpy.clip" not in calls
    assert '"production_frequency_representation_selected": False' in source
    assert '"full_dynamic_orbit_authorized": False' in source
    assert '"phase4_replacement_authorized": False' in source
    assert '"uvot_authorized": False' in source
