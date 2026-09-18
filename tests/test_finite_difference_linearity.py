import json
import shutil
import uuid

import numpy as np
import pytest

from operations.collect_encoded_ratios import ROOT
from operations.finite_difference_linearity import (
    candidate_measurement, linearity_check, recommendation, round_vectors)


def _make_run(alpha, vectors, endpoints=None):
    name = f"fdlin-selftest-{uuid.uuid4().hex[:8]}"
    run = ROOT / "outputs/hpc" / name
    state_history, rounds = [], []
    for index, vector in enumerate(vectors):
        folder = run / f"feedback-round{index + 1}"
        folder.mkdir(parents=True, exist_ok=True)
        np.save(folder / "material_residual.npy", np.asarray(vector, dtype=float))
        (folder / "feedback_summary.json").write_text(json.dumps({
            "encoded_residual_path":
                f"outputs/hpc/{name}/feedback-round{index + 1}/material_residual.npy"}) + "\n")
        (folder / "material_energy_ledger.json").write_text("{}\n")
        pairs = endpoints if endpoints is not None else [
            (2 * i + 1, 2 * i + 2) for i in range(len(vectors))]
        pair = pairs[index]
        for iteration in pair:
            state_history.append({"iteration": iteration, "residual": 1.0e-4})
        rounds.append({"round": index + 1, "endpoints": list(pair),
                       "ledger": f"outputs/hpc/{name}/feedback-round{index+1}/"
                                 "material_energy_ledger.json"})
    (run / "config.json").write_text(json.dumps({"candidate_relaxation": alpha}) + "\n")
    (run / "state.json").write_text(json.dumps({
        "config_sha256": "x", "status": "radiation", "history": state_history,
        "slots": ["a", "b", "c"], "current_slot": 0, "active_map": None,
        "diagnostic": {"rounds": rounds}}) + "\n")
    return name, run


def test_round_vectors_and_signal_noise():
    base = np.zeros(4)
    name, run = _make_run(0.015625, [base + np.array([3.0, 0, 0, 0]),
                                     base + np.array([3.2, 0, 0, 0])])
    try:
        data = round_vectors(f"outputs/hpc/{name}")
        assert data["alpha"] == 0.015625 and len(data["rounds"]) == 2
        row = candidate_measurement(f"outputs/hpc/{name}", base)
        assert row["signal_last"] == pytest.approx(3.2)
        assert row["noise_last"] == pytest.approx(0.2)
        assert row["signal_to_noise_last"] == pytest.approx(16.0)
        assert row["signal_per_step_last"] == pytest.approx(3.2 / 0.015625)
    finally:
        shutil.rmtree(run, ignore_errors=True)


def test_linearity_pairs_require_half_ratio_and_agreement():
    linear = linearity_check([
        {"alpha": 0.0078125, "signal_per_step_last": 800.0},
        {"alpha": 0.015625, "signal_per_step_last": 810.0}])
    assert linear["pairs"][0]["linear"] is True
    nonlinear = linearity_check([
        {"alpha": 0.015625, "signal_per_step_last": 811.0},
        {"alpha": 0.0625, "signal_per_step_last": 201.0}])
    assert nonlinear["pairs"][0]["linear"] is False
    not_halved = linearity_check([
        {"alpha": 0.01, "signal_per_step_last": 800.0},
        {"alpha": 0.04, "signal_per_step_last": 800.0}])
    assert not_halved["pairs"][0]["linear"] is False   # 步长比不是 1/2，不算自洽对


def test_recommendation_picks_the_smallest_qualifying_step():
    measurements = [
        {"alpha": 0.0078125, "signal_to_noise_last": 40.0, "signal_per_step_last": 800.0},
        {"alpha": 0.015625, "signal_to_noise_last": 52.0, "signal_per_step_last": 810.0}]
    linearity = linearity_check(measurements)
    result = recommendation(measurements, linearity)
    assert result["usable_step"] == 0.0078125
    assert result["signal_to_noise"] == 40.0


def test_recommendation_refuses_when_noise_dominates_or_nonlinear():
    noisy = [{"alpha": 0.0078125, "signal_to_noise_last": 2.0, "signal_per_step_last": 800.0},
             {"alpha": 0.015625, "signal_to_noise_last": 3.0, "signal_per_step_last": 810.0}]
    assert recommendation(noisy, linearity_check(noisy))["usable_step"] is None
    nonlinear = [{"alpha": 0.015625, "signal_to_noise_last": 50.0, "signal_per_step_last": 811.0},
                 {"alpha": 0.0625, "signal_to_noise_last": 50.0, "signal_per_step_last": 201.0}]
    assert recommendation(nonlinear, linearity_check(nonlinear))["usable_step"] is None


def test_run_without_rounds_reports_status_instead_of_guessing():
    name, run = _make_run(0.015625, [np.zeros(4)])
    try:
        (run / "state.json").write_text(json.dumps({
            "config_sha256": "x", "status": "radiation", "history": [],
            "slots": ["a", "b", "c"], "current_slot": 0, "active_map": None,
            "diagnostic": {"rounds": []}}) + "\n")
        row = candidate_measurement(f"outputs/hpc/{name}", np.zeros(4))
        assert row["status"] == "no completed round" and row["rounds"] == 0
    finally:
        shutil.rmtree(run, ignore_errors=True)


def test_run_without_candidate_relaxation_is_reported_not_guessed():
    name, run = _make_run(0.015625, [np.zeros(4), np.full(4, 1.0)])
    try:
        (run / "config.json").write_text(json.dumps({}) + "\n")
        row = candidate_measurement(f"outputs/hpc/{name}", np.zeros(4))
        assert row["rounds"] == 2 and row["alpha"] is None
        assert "candidate_relaxation" in row["status"]
        assert "signal_last" not in row          # 步长未知就不报每步量
    finally:
        shutil.rmtree(run, ignore_errors=True)
