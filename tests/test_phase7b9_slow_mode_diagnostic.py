"""Phase 7B9 慢模诊断的纯函数与只读边界回归。"""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_slow_mode_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("phase7b9_slow_mode_diagnostic", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Phase 7B9 slow-mode diagnostic")
diagnostic = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = diagnostic
SPEC.loader.exec_module(diagnostic)


def test_monotonic_geometric_sequence_has_finite_forecast() -> None:
    residuals = [2.0e-4 * 0.9**index for index in range(6)]
    result = diagnostic.conservative_picard_forecast(residuals, [10.0] * 6)
    assert result["available"] is True
    assert result["conservative_contraction_ratio_per_map"] == pytest.approx(0.9)
    expected = math.ceil(math.log(1.0e-4 / residuals[-1]) / math.log(0.9))
    assert result["estimated_additional_maps"] == expected
    assert result["prediction_is_convergence_proof"] is False


def test_contracting_plateau_is_reported_as_large_uncertain_forecast() -> None:
    residuals = [2.0e-4 * 0.999**index for index in range(10)]
    result = diagnostic.conservative_picard_forecast(residuals, [12.0] * 10)
    assert result["available"] is True
    assert result["plateau_warning"] is True
    assert result["estimated_additional_maps"] > 600
    assert result["requires_fresh_map_confirmation"] is True


def test_non_contracting_recent_segment_has_no_threshold_forecast() -> None:
    result = diagnostic.conservative_picard_forecast(
        [1.30e-4, 1.20e-4, 1.21e-4],
        [10.0, 10.0, 10.0],
    )
    assert result["available"] is False
    assert result["reason"] == "recent_segment_contains_non_contraction"
    assert result["prediction_is_convergence_proof"] is False


def test_json_reader_rejects_checkpoint_data(tmp_path: Path) -> None:
    checkpoint = tmp_path / "state.dat"
    checkpoint.write_bytes(b"not a real state")
    with pytest.raises(ValueError, match="only JSON"):
        diagnostic.read_small_json(checkpoint)


def test_real_ledger_keeps_predicted_and_actual_semantics_separate() -> None:
    payload = diagnostic.build_diagnostic(ROOT)
    scope = payload["scope"]
    assert scope["checkpoint_dat_opened"] is False
    assert scope["checkpoint_dat_hashed"] is False
    assert scope["checkpoint_dat_modified"] is False
    assert all(item["measurement_kind"] == "fresh_map_actual" for item in payload["actual_states"])

    predicted = {item["stage"]: item for item in payload["anderson_predictions"]}
    assert set(predicted) == {"7B9cg", "7B9ck", "7B9co"}
    assert all(item["measurement_kind"] == "predicted" for item in predicted.values())
    assert predicted["7B9co"]["disposition"] == "rejected"
    assert predicted["7B9co"]["fresh_map_actual_available"] is False
    assert payload["decision"]["formal_convergence_demonstrated"] is False
    assert payload["slow_mode_forecast"]["prediction_is_convergence_proof"] is False


def test_script_has_no_checkpoint_content_or_hash_api() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "hashlib" not in imports
    assert "read_bytes" not in attributes
    assert "memmap" not in attributes
    assert all(path.endswith(".json") for _, _, path in diagnostic.SUMMARY_SPECS)
    assert all(path.endswith(".json") for path in diagnostic.SEQUENCE_MANIFESTS.values())
