import json
import shutil
import uuid

import numpy as np
import pytest

from operations.collect_encoded_ratios import ROOT
from operations.small_step_verdict import endpoint_residuals, qualifying, verdict_for


def test_endpoint_residuals_reads_history_iterations():
    state = {"history": [{"iteration": 3, "residual": 1.3e-3}, {"iteration": 4, "residual": 1.1e-3}]}
    assert endpoint_residuals(state) == {3: 1.3e-3, 4: 1.1e-3}


def test_qualifying_requires_both_endpoints_below_threshold():
    residuals = {3: 1.3e-3, 4: 1.1e-3, 7: 7.5e-4, 8: 6.8e-4, 23: 2.4e-4, 24: 2.2e-4}
    assert qualifying({"endpoints": [3, 4]}, residuals) is False
    assert qualifying({"endpoints": [7, 8]}, residuals) is False
    assert qualifying({"endpoints": [23, 24]}, residuals) is True


def test_qualifying_rejects_missing_or_malformed_endpoints():
    residuals = {23: 2.4e-4, 24: 2.2e-4}
    assert qualifying({"endpoints": [23]}, residuals) is False
    assert qualifying({"endpoints": [23, 99]}, residuals) is False
    assert qualifying({"endpoints": None}, residuals) is False


def test_verdict_is_pending_without_a_qualifying_round():
    rows = [{"round": 1, "qualifies": False, "ratio_to_base": 1.16},
            {"round": 2, "qualifies": False, "ratio_to_base": 1.11}]
    result = verdict_for(rows)
    assert result["verdict"] == "pending" and result["qualifying_rounds"] == 0
    assert "never used" not in json.dumps(result)   # 结果里不带叙述性内容


def test_last_qualifying_round_decides_and_above_one_is_not_descending():
    rows = [{"round": 3, "qualifies": True, "ratio_to_base": 1.05, "endpoints": [15, 16],
             "endpoint_residuals": [2.4e-4, 2.2e-4]},
            {"round": 4, "qualifies": True, "ratio_to_base": 0.98, "endpoints": [23, 24],
             "endpoint_residuals": [2.0e-4, 1.9e-4]}]
    result = verdict_for(rows)
    assert result["verdict"] == "descending" and result["deciding_round"] == 4
    assert result["ratio_to_base"] == 0.98
    above = verdict_for([{"round": 3, "qualifies": True, "ratio_to_base": 1.05,
                          "endpoints": [15, 16], "endpoint_residuals": [2.4e-4, 2.2e-4]}])
    assert above["verdict"] == "not_descending" and above["deciding_round"] == 3


def test_analyse_joins_rounds_with_history_end_to_end():
    from operations.small_step_verdict import analyse
    name = f"verdict-selftest-{uuid.uuid4().hex[:8]}"
    run = ROOT / "outputs/hpc" / name
    try:
        (run / "feedback-round3").mkdir(parents=True)
        np.save(run / "feedback-round3" / "material_residual.npy", np.full(8, 2.0))
        (run / "feedback-round3" / "feedback_summary.json").write_text(json.dumps({
            "encoded_residual_path": f"outputs/hpc/{name}/feedback-round3/material_residual.npy",
            "comparison": {"atomic_heating_volume_l1": 0.0009},
            "gate_checks": {"candidate_l2_contraction_pass": False}}) + "\n")
        (run / "feedback-round3" / "material_energy_ledger.json").write_text("{}\n")
        (run / "state.json").write_text(json.dumps({
            "config_sha256": "x", "status": "radiation",
            "history": [{"iteration": 15, "residual": 2.4e-4}, {"iteration": 16, "residual": 2.2e-4}],
            "slots": ["a", "b", "c"], "current_slot": 0, "active_map": None,
            "diagnostic": {"rounds": [{"round": 3, "endpoints": [15, 16],
                            "ledger": f"outputs/hpc/{name}/feedback-round3/material_energy_ledger.json"}]}}) + "\n")
        result = analyse(f"outputs/hpc/{name}", base_l2=4.0, threshold=2.5e-4)
        assert result["verdict"] == "not_descending"
        assert result["deciding_endpoint_residuals"] == [2.4e-4, 2.2e-4]
        assert result["rounds"][0]["ratio_to_base"] == pytest.approx(
            float(np.linalg.norm(np.full(8, 2.0))) / 4.0)
    finally:
        shutil.rmtree(run, ignore_errors=True)
