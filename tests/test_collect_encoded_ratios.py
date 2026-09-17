import json
import shutil
from pathlib import Path
import uuid

import numpy as np
import pytest

from operations.collect_encoded_ratios import ROOT, collect_run


def _write_run(name: str, *, rounds=True, residual=None, status="radiation"):
    root = ROOT / "outputs/hpc"
    root.mkdir(parents=True, exist_ok=True)
    run = root / name
    (run / "feedback-round1").mkdir(parents=True)
    values = np.full(8, 2.0) if residual is None else np.asarray(residual, dtype=float)
    np.save(run / "feedback-round1" / "material_residual.npy", values)
    summary = {
        "encoded_residual_path": f"outputs/hpc/{name}/feedback-round1/material_residual.npy",
        "comparison": {"atomic_heating_volume_l1": 0.003},
        "gate_checks": {"candidate_l2_contraction_pass": False, "other": "not-a-bool"},
    }
    (run / "feedback-round1" / "feedback_summary.json").write_text(json.dumps(summary) + "\n")
    ledger = f"outputs/hpc/{name}/feedback-round1/material_energy_ledger.json"
    (run / "feedback-round1" / "material_energy_ledger.json").write_text("{}\n")
    state = {"config_sha256": "x", "status": status, "history": [{"iteration": 1, "residual": 1e-4}],
             "slots": ["a", "b", "c"], "current_slot": 0, "active_map": None,
             "diagnostic": {"rounds": [{"round": 1, "endpoints": [3, 4], "ledger": ledger}]}
             if rounds else {"rounds": []}}
    (run / "state.json").write_text(json.dumps(state) + "\n")
    return run


def _scratch():
    return f"ratio-selftest-{uuid.uuid4().hex[:8]}"


def test_ratio_uses_base_l2_and_reports_gates():
    name = _scratch()
    try:
        _write_run(name)
        result = collect_run(f"outputs/hpc/{name}", base_l2=4.0)
        row = result["rounds"][0]
        assert row["round"] == 1 and row["endpoints"] == [3, 4]
        assert row["l2"] == pytest.approx(float(np.linalg.norm(np.full(8, 2.0))))
        assert row["ratio_to_base"] == pytest.approx(row["l2"] / 4.0)
        assert row["gates"] == {"candidate_l2_contraction_pass": False}   # 非布尔被丢弃
        assert row["atomic_heating_volume_l1"] == 0.003
        assert result["status"] == "radiation" and result["maps"] == 1
    finally:
        shutil.rmtree(ROOT / f"outputs/hpc/{name}", ignore_errors=True)


def test_root_level_summary_is_used_when_no_rounds_exist():
    name = _scratch()
    try:
        run = _write_run(name, rounds=False)
        np.save(run / "material_residual.npy", np.full(4, 1.0))
        (run / "feedback_summary.json").write_text(json.dumps({
            "encoded_residual_path": f"outputs/hpc/{name}/material_residual.npy",
            "comparison": {"atomic_heating_volume_l1": 0.001},
            "gate_checks": {"candidate_l2_contraction_pass": True}}) + "\n")
        result = collect_run(f"outputs/hpc/{name}", base_l2=4.0)
        assert result["rounds"][0]["round"] is None
        assert result["rounds"][0]["ratio_to_base"] == pytest.approx(2.0 / 4.0)
    finally:
        shutil.rmtree(ROOT / f"outputs/hpc/{name}", ignore_errors=True)


def test_missing_round_summary_is_reported_not_guessed():
    name = _scratch()
    try:
        run = _write_run(name)
        (run / "feedback-round1" / "feedback_summary.json").unlink()
        with pytest.raises(SystemExit):
            collect_run(f"outputs/hpc/{name}", base_l2=4.0)
    finally:
        shutil.rmtree(ROOT / f"outputs/hpc/{name}", ignore_errors=True)


def test_non_finite_residual_is_rejected():
    name = _scratch()
    try:
        _write_run(name, residual=[1.0, np.nan])
        with pytest.raises(ValueError):
            collect_run(f"outputs/hpc/{name}", base_l2=4.0)
    finally:
        shutil.rmtree(ROOT / f"outputs/hpc/{name}", ignore_errors=True)
