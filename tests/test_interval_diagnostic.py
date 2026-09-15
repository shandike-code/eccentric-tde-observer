"""Run-control guarantees of the diagnostic driver.

Each test pins one guarantee that a Mac-side review found missing in revision
6423e4c. They use synthetic state and monkeypatched pipeline hooks; no worker,
no solver and no Slurm allocation is started.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "diagnostics"))

import interval_diagnostic as driver  # noqa: E402
import pipeline  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
def history_row(iteration):
    return {
        "iteration": iteration,
        "input_path": f"outputs/hpc/run/state_{iteration % 3}.dat",
        "input_sha256": f"in{iteration}",
        "output_path": f"outputs/hpc/run/state_{(iteration + 1) % 3}.dat",
        "output_sha256": f"out{iteration}",
        "wall_s": 1.0, "residual": 2.0e-4,
        "boundary_l1": 3.0e-6, "boundary_bolometric": 2.0e-6,
        "maximum_worker_rss_mib": 3500.0,
    }


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    """A minimal run tree with the driver rooted at tmp_path."""
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    run = tmp_path / "outputs/hpc/run"
    run.mkdir(parents=True)
    (run / "config.json").write_text(json.dumps({
        "run": "outputs/hpc/run", "workers": 2, "radiation_threshold": 2.5e-4,
        "maximum_maps": 8, "sources": [],
    }))
    state = {
        "config_sha256": "cfg", "status": "radiation", "history": [],
        "slots": [f"outputs/hpc/run/state_{i}.dat" for i in range(3)],
        "current_slot": 0, "current_sha256": "in0", "active_map": None,
    }
    (run / "state.json").write_text(json.dumps(state))
    return run


def read_state(run):
    return json.loads((run / "state.json").read_text())


# --------------------------------------------------------------------------- #
# cadence
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "completed,rounds_done,expected",
    [(0, 0, False), (1, 0, False), (3, 0, False), (4, 0, True), (4, 1, False),
     (5, 1, False), (8, 1, True), (8, 2, False), (12, 2, True)],
)
def test_feedback_cadence(completed, rounds_done, expected):
    assert driver.should_run_feedback(completed, 4, rounds_done, False) is expected


def test_feedback_never_fires_after_a_stop_request():
    assert driver.should_run_feedback(4, 4, 0, True) is False


def test_cadence_is_checked_after_every_map_not_only_at_job_end():
    """With maps_per_job > 1 the boundary must be caught at the map that crosses it.

    The driver checks after each map, so a job that runs maps 1..8 fires at 4 and
    again at 8 -- the earlier revision only looked after the whole job, and a job
    ending on map 5 would have skipped the map-4 boundary entirely.
    """
    rounds_done, fired = 0, []
    for completed in range(1, 9):
        if driver.should_run_feedback(completed, 4, rounds_done, False):
            fired.append(completed)
            rounds_done += 1
    assert fired == [4, 8]

    # The same loop stopping at map 5 still catches map 4.
    rounds_done, fired = 0, []
    for completed in range(1, 6):
        if driver.should_run_feedback(completed, 4, rounds_done, False):
            fired.append(completed)
            rounds_done += 1
    assert fired == [4]


# --------------------------------------------------------------------------- #
# stop propagation
# --------------------------------------------------------------------------- #
def test_stop_request_reaches_the_flag_pipeline_batches_reads(monkeypatch):
    """`pipeline.batches` consults `pipeline.STOP`; the driver's own flag is not enough."""
    monkeypatch.setattr(pipeline, "STOP", False)
    monkeypatch.setattr(driver, "STOP", False)
    driver.signal_stop(None, None)
    assert driver.STOP is True
    assert pipeline.STOP is True, "batches would have kept dispatching workers"


# --------------------------------------------------------------------------- #
# round ownership: nothing moved, nothing overwritten, nothing rmtree'd
# --------------------------------------------------------------------------- #
def test_start_round_refuses_an_existing_round_directory(run_dir):
    state = read_state(run_dir)
    state["history"] = [history_row(3), history_row(4)]
    (run_dir / "feedback-round1").mkdir()
    with pytest.raises(RuntimeError, match="already exists"):
        driver.start_round(run_dir, {}, state, run_dir / "state.json")


def test_start_round_persists_both_endpoints_before_any_work(run_dir):
    state = read_state(run_dir)
    state["history"] = [history_row(3), history_row(4)]
    pending = driver.start_round(run_dir, {}, state, run_dir / "state.json")
    on_disk = read_state(run_dir)["pending_feedback"]
    assert on_disk["endpoints"] == [3, 4]
    assert on_disk["previous"]["output_sha256"] == "out3"
    assert on_disk["final"]["output_sha256"] == "out4"
    assert on_disk["stage"] == "protocol"
    assert on_disk == pending


def test_build_round_protocol_puts_every_output_inside_the_round(run_dir, monkeypatch):
    """Moved artifacts invalidate the paths recorded inside generated manifests."""
    state = read_state(run_dir)
    state["history"] = [history_row(3), history_row(4)]
    round_dir = run_dir / "feedback-round1"
    round_dir.mkdir()

    base = run_dir / "feedback_protocol.json"
    monkeypatch.setattr(pipeline, "feedback_protocol",
                        lambda config, state: base)
    base.write_text(json.dumps({"configuration": {}, "sources": {}}))

    protocol = driver.build_round_protocol(run_dir, {}, state, round_dir)
    cfg = json.loads(protocol.read_text())["configuration"]
    for key in ("feedback_work_directory", "summary_path", "figure_path",
                "previous_feedback_output", "final_feedback_output"):
        assert cfg[key].startswith("outputs/hpc/run/feedback-round1/"), key
    # The run-root copy must not survive for a later round to pick up.
    assert not base.exists()
    index = json.loads((run_dir / driver.MIGRATION_INDEX).read_text())
    assert index["entries"][0]["old_path"] == "outputs/hpc/run/feedback_protocol.json"


def test_migration_index_is_append_only(run_dir):
    legacy = run_dir / "feedback_summary.json"
    legacy.write_text("{}")
    driver.record_legacy(run_dir, legacy, "first")
    legacy.write_text('{"changed": true}')
    driver.record_legacy(run_dir, legacy, "second")
    entries = json.loads((run_dir / driver.MIGRATION_INDEX).read_text())["entries"]
    assert [e["reason"] for e in entries] == ["first", "second"]
    assert entries[0]["sha256"] != entries[1]["sha256"]
    # An earlier entry is never rewritten to match later content.
    assert entries[0]["sha256"] == hashlib.sha256(b"{}").hexdigest()


# --------------------------------------------------------------------------- #
# ledger failure must not register a completed round
# --------------------------------------------------------------------------- #
def test_ledger_failure_leaves_the_round_incomplete(run_dir, monkeypatch):
    state = read_state(run_dir)
    state["history"] = [history_row(3), history_row(4)]
    pending = driver.start_round(run_dir, {}, state, run_dir / "state.json")
    pending.update({"stage": "ledger", "protocol_path": "p", "protocol_sha256": "h"})
    state["pending_feedback"] = pending
    (run_dir / "state.json").write_text(json.dumps(state))
    (run_dir / "feedback-round1" / "feedback_summary.json").write_text(json.dumps({
        "gate_checks": {"a": True},
        "decision": {"finite_trial_accepted_as_one_nonlinear_step": True},
    }))

    def boom(*a, **k):
        raise RuntimeError("ledger exited 256")

    monkeypatch.setattr(driver, "run_ledger", boom)
    with pytest.raises(RuntimeError, match="ledger exited 256"):
        driver.complete_round(run_dir, {}, state, run_dir / "state.json")

    after = read_state(run_dir)
    assert after["status"] == "diagnosis_incomplete"
    assert after["pending_feedback"]["stage"] == "ledger"   # resumable, physics kept
    assert "rounds" not in after.get("diagnostic", {})      # nothing registered


def test_ledger_verifies_the_inputs_belong_to_this_round(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    round_dir = run / "feedback-round1"
    round_dir.mkdir()
    endpoints = {"previous": {"path": "p", "size_bytes": 1, "sha256": "aaa"},
                 "final": {"path": "f", "size_bytes": 1, "sha256": "bbb"}}

    def fake_run(command, **kwargs):
        assert isinstance(command, list) and kwargs["check"] is True
        (round_dir / "material_energy_ledger.json").write_text(json.dumps({
            "inputs": {"previous_feedback": {"sha256": "aaa"},
                       "final_feedback": {"sha256": "WRONG"}},
            "heating_stability": {"metrics": {}},
        }))

    monkeypatch.setattr(driver.subprocess, "run", fake_run)
    monkeypatch.setattr(driver, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="input hash mismatch"):
        driver.run_ledger(run, round_dir, endpoints)


# --------------------------------------------------------------------------- #
# diagnostic declaration
# --------------------------------------------------------------------------- #
def test_declaration_pins_diagnostics_and_refuses_tampering(run_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "DIAGNOSTICS_DIR", tmp_path / "diag")
    (tmp_path / "diag").mkdir()
    module = tmp_path / "diag" / "driver.py"
    module.write_text("v1")
    monkeypatch.setattr(pipeline, "environment", lambda: {"git_commit": "abc"})
    config = {"workers": 2, "maximum_maps": 8, "radiation_threshold": 2.5e-4}
    args = type("A", (), {"maps_per_job": 1, "feedback_every": 4})()

    driver.ensure_declaration(run_dir, config, args)
    driver.ensure_declaration(run_dir, config, args)          # idempotent

    module.write_text("v2")                                    # tampered
    with pytest.raises(RuntimeError, match="diagnostic sources changed"):
        driver.ensure_declaration(run_dir, config, args)


def test_declaration_refuses_changed_execution_parameters(run_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(driver, "DIAGNOSTICS_DIR", tmp_path / "diag")
    (tmp_path / "diag").mkdir()
    (tmp_path / "diag" / "driver.py").write_text("v1")
    monkeypatch.setattr(pipeline, "environment", lambda: {"git_commit": "abc"})
    config = {"workers": 2, "maximum_maps": 8, "radiation_threshold": 2.5e-4}
    driver.ensure_declaration(run_dir, config,
                              type("A", (), {"maps_per_job": 1, "feedback_every": 4})())
    with pytest.raises(RuntimeError, match="parameter feedback_every changed"):
        driver.ensure_declaration(run_dir, config,
                                  type("A", (), {"maps_per_job": 1, "feedback_every": 8})())


# --------------------------------------------------------------------------- #
# main() control flow
# --------------------------------------------------------------------------- #
def drive_main(run_dir, monkeypatch, argv):
    """Run the driver's main() against synthetic state with the heavy hooks mocked."""
    root = run_dir.parents[2]                       # tmp_path in the fixture
    monkeypatch.setattr(driver, "ROOT", root)
    monkeypatch.setattr(pipeline, "safe_path", lambda _root, path: root / path)
    monkeypatch.setattr(pipeline, "require_allocation", lambda workers: None)
    monkeypatch.setattr(pipeline, "verify_claims", lambda *a, **k: [])
    monkeypatch.setattr(pipeline, "sha256", lambda path: "cfg")
    monkeypatch.setattr(driver, "ensure_declaration", lambda *a: {})
    monkeypatch.setenv("SLURM_JOB_ID", "999")
    monkeypatch.setattr(sys, "argv", ["interval_diagnostic.py"] + argv)
    driver.main()


def test_pending_feedback_is_settled_before_any_new_map(run_dir, monkeypatch):
    """A map must never overtake an owed feedback and rotate a slot under it."""
    state = read_state(run_dir)
    state["history"] = [history_row(3), history_row(4)]
    state["pending_feedback"] = {"round": 1,
                                 "round_dir": "outputs/hpc/run/feedback-round1",
                                 "stage": "ledger"}
    (run_dir / "state.json").write_text(json.dumps(state))
    order = []
    monkeypatch.setattr(driver, "complete_round", lambda *a: order.append("feedback"))
    monkeypatch.setattr(driver, "run_one_map", lambda *a: order.append("map") or True)
    drive_main(run_dir, monkeypatch, ["--run", "outputs/hpc/run", "--maps-per-job", "2"])
    assert order[0] == "feedback", order
    assert "map" in order


def test_accepted_status_is_terminal(run_dir, monkeypatch):
    state = read_state(run_dir)
    state["status"] = "one_material_trial_accepted"
    state["history"] = [history_row(3), history_row(4)]
    (run_dir / "state.json").write_text(json.dumps(state))
    order = []
    monkeypatch.setattr(driver, "run_one_map", lambda *a: order.append("map") or True)
    monkeypatch.setattr(driver, "complete_round", lambda *a: order.append("feedback"))
    drive_main(run_dir, monkeypatch, ["--run", "outputs/hpc/run", "--maps-per-job", "2"])
    assert order == []
    assert read_state(run_dir)["status"] == "one_material_trial_accepted"


def test_resource_failure_is_not_overwritten_by_budget_completion(run_dir, monkeypatch):
    """Fault outranks budget: exhausting the map budget must not relabel a fault."""
    state = read_state(run_dir)
    state["status"] = "resource_gate_failed"
    state["history"] = [history_row(i) for i in range(1, 9)]   # budget also spent
    (run_dir / "state.json").write_text(json.dumps(state))
    order = []
    monkeypatch.setattr(driver, "run_one_map", lambda *a: order.append("map") or True)
    monkeypatch.setattr(driver, "complete_round", lambda *a: order.append("feedback"))
    drive_main(run_dir, monkeypatch, ["--run", "outputs/hpc/run", "--maps-per-job", "1"])
    assert order == []
    assert read_state(run_dir)["status"] == "resource_gate_failed"
