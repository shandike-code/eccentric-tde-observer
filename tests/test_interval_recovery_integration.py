"""Exercise real round/ledger glue; fake only expensive physics and child work."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "diagnostics")]
import interval_diagnostic as d
import interval_supervise as supervisor
import material_energy_ledger as ledger
from scripts import phase7b9_formal_feedback_pair_adapter as pair


@pytest.fixture
def round_run(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    run = tmp_path / "outputs/hpc/run"
    run.mkdir(parents=True)
    config = {"workers": 2, "sources": [], "maximum_maps": 8, "radiation_threshold": .00025}
    d.pipeline.write_json(run / "config.json", config)
    state = {"status": "radiation", "history": [
        {"iteration": i, "input_path": f"state{i}", "input_sha256": f"radiation{i}",
         "output_path": f"state{i+1}", "output_sha256": f"radiation{i+1}"}
        for i in range(1, 5)], "config_sha256": d.pipeline.sha256(run / "config.json")}
    state_path = run / "state.json"
    d.pipeline.write_json(state_path, state)
    pending = d.start_round(run, config, state, state_path)
    folder = tmp_path / pending["round_dir"]
    protocol = {"configuration": {}, "sources": {
        label + "_radiation": {"path": pending[label]["input_path"],
                               "sha256": pending[label]["input_sha256"]}
        for label in ("previous", "final")}}
    protocol_path = folder / "feedback_protocol.json"
    d.pipeline.write_json(protocol_path, protocol)
    pending.update(stage="feedback", protocol_path=d.relative(protocol_path),
                   protocol_sha256=d.pipeline.sha256(protocol_path))
    d.pipeline.write_json(state_path, state)
    events = []

    def fake_physics(path, digest):
        events.append("physics")
        report = {"protocol_sha256": digest, "gate_checks": {"physical": True},
                  "decision": {"finite_trial_accepted_as_one_nonlinear_step": True}}
        for label in ("previous", "final"):
            artifact = folder / f"{label}_feedback.npz"
            artifact.write_bytes(label.encode())
            info = {"feedback_artifact_path": d.relative(artifact),
                    "feedback_artifact_sha256": d.pipeline.sha256(artifact)}
            report[label + "_feedback"] = info
            manifest = {**info, "protocol_sha256": digest, "status": "complete",
                        "state_path": pending[label]["input_path"],
                        "state_sha256": pending[label]["input_sha256"]}
            d.pipeline.write_json(folder / "feedback" / f"{label}_manifest.json", manifest)
        d.pipeline.write_json(folder / "feedback_summary.json", report)
        return report

    def child(command, **kwargs):
        assert isinstance(command, list) and kwargs["check"]
        events.append("ledger")
        report = {"inputs": {label + "_feedback": {
            "sha256": d.pipeline.sha256(folder / f"{label}_feedback.npz")}
            for label in ("previous", "final")},
            "heating_stability": {"metrics": {"atomic_rate_heating_erg_s_cm3": {"ratio": 0.}}}}
        d.pipeline.write_json(Path(command[command.index("--json") + 1]), report)

    monkeypatch.setattr(pair, "run_pair", fake_physics)
    monkeypatch.setattr(d.subprocess, "run", child)
    return run, config, state, state_path, folder, events, child


def test_complete_round_passes_feedback_npz_hashes_to_real_ledger(round_run):
    run, config, state, path, folder, events, _ = round_run
    result = d.complete_round(run, config, state, path)
    assert result["accepted"]
    assert state["status"] == "one_material_trial_accepted"
    assert "pending_feedback" not in state
    assert events == ["physics", "ledger"]
    assert len(d.pipeline.read(path)["diagnostic"]["rounds"]) == 1


def test_nonzero_ledger_is_recovered_without_rerunning_physics(round_run, monkeypatch):
    run, config, state, path, folder, events, child = round_run
    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, ["ledger"])
    monkeypatch.setattr(d.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        d.complete_round(run, config, state, path)
    state = d.pipeline.read(path)
    assert state["status"] == "diagnosis_incomplete"
    monkeypatch.setattr(d.subprocess, "run", child)
    d.complete_round(run, config, state, path)
    assert events == ["physics", "ledger"]


def test_crash_after_round_summary_recovers_without_duplicate_commit(round_run, monkeypatch):
    run, config, state, path, folder, events, child = round_run
    write = d.pipeline.write_json
    def interrupted(target, value):
        if target == path and "pending_feedback" not in value:
            raise OSError("interrupted before final state commit")
        return write(target, value)
    monkeypatch.setattr(d.pipeline, "write_json", interrupted)
    with pytest.raises(OSError):
        d.complete_round(run, config, state, path)
    before = (folder / "round_summary.json").read_bytes()
    monkeypatch.setattr(d.pipeline, "write_json", write)
    d.complete_round(run, config, d.pipeline.read(path), path)
    assert events == ["physics", "ledger", "ledger"]
    assert (folder / "round_summary.json").read_bytes() == before
    assert len(d.pipeline.read(path)["diagnostic"]["rounds"]) == 1


def test_directory_creation_interrupt_leaves_recoverable_registered_intent(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    run = tmp_path / "run"
    run.mkdir()
    state = {"history": [{"iteration": i, "input_path": f"state{i}",
                          "input_sha256": f"in{i}", "output_path": f"state{i+1}",
                          "output_sha256": f"in{i+1}"} for i in (3, 4)]}
    mkdir = Path.mkdir
    def interrupted(path, *a, **kw):
        if path.name == "feedback-round1":
            raise OSError("interrupted before mkdir")
        return mkdir(path, *a, **kw)
    monkeypatch.setattr(Path, "mkdir", interrupted)
    with pytest.raises(OSError):
        d.start_round(run, {}, state, run / "state.json")
    assert not (run / "feedback-round1").exists()
    assert d.pipeline.read(run / "state.json")["pending_feedback"]["stage"] == "protocol"


def test_declaration_rejects_added_runtime_source(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    diag = tmp_path / "diagnostics"
    diag.mkdir()
    (diag / "driver.py").write_text("v1")
    monkeypatch.setattr(d, "DIAGNOSTICS_DIR", diag)
    monkeypatch.setattr(d.pipeline, "environment", lambda: {"git_commit": "test"})
    run = tmp_path / "run"
    run.mkdir()
    args = type("Args", (), {"maps_per_job": 1, "feedback_every": 4})()
    config = {"workers": 2, "maximum_maps": 8, "radiation_threshold": .00025}
    d.ensure_declaration(run, config, args)
    (diag / "new_helper.py").write_text("added after declaration")
    with pytest.raises(RuntimeError, match="sources changed"):
        d.ensure_declaration(run, config, args)


@pytest.mark.parametrize("changed", ["feedback_summary.json", "previous_feedback.npz",
                                     "feedback_protocol.json"])
def test_ledger_recovery_rejects_tampered_completed_inputs(round_run, monkeypatch, changed):
    run, config, state, path, folder, events, child = round_run
    def fail(*a, **k):
        raise subprocess.CalledProcessError(1, ["ledger"])
    monkeypatch.setattr(d.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        d.complete_round(run, config, state, path)
    (folder / changed).write_bytes(b"tampered")
    monkeypatch.setattr(d.subprocess, "run", child)
    with pytest.raises(RuntimeError):
        d.complete_round(run, config, d.pipeline.read(path), path)
    assert events == ["physics"]


def run_main(tmp_path, monkeypatch, completed, accepted=False):
    run = tmp_path / "outputs/hpc/main"
    run.mkdir(parents=True)
    monkeypatch.setattr(d, "ROOT", tmp_path)
    monkeypatch.setattr(d, "STOP", False)
    monkeypatch.setattr(d.pipeline, "safe_path", lambda root, value: root / value)
    monkeypatch.setattr(d.pipeline, "require_allocation", lambda *a: None)
    monkeypatch.setattr(d.pipeline, "verify_claims", lambda *a, **kw: [])
    monkeypatch.setattr(d.pipeline, "environment", lambda: {})
    monkeypatch.setattr(d, "ensure_declaration", lambda *a: {})
    monkeypatch.setenv("SLURM_JOB_ID", "synthetic")
    config = {"workers": 2, "sources": [], "maximum_maps": 8}
    d.pipeline.write_json(run / "config.json", config)
    state = {"status": "radiation", "history": [dict(iteration=i) for i in range(1, completed+1)],
             "config_sha256": d.pipeline.sha256(run / "config.json"),
             "diagnostic": {"rounds": [{}] if completed >= 7 else []}}
    d.pipeline.write_json(run / "state.json", state)
    events = []
    def start(run, config, state, path):
        state["pending_feedback"] = {"round": 1}
        return state["pending_feedback"]
    def finish(run, config, state, path):
        events.append("feedback")
        state.pop("pending_feedback", None)
        state["diagnostic"]["rounds"].append({"accepted": accepted})
        if accepted:
            state["status"] = "one_material_trial_accepted"
    def mapping(run, config, state, path):
        events.append("map")
        state["history"].append({"iteration": len(state["history"])+1})
        return True
    monkeypatch.setattr(d, "start_round", start)
    monkeypatch.setattr(d, "complete_round", finish)
    monkeypatch.setattr(d, "run_one_map", mapping)
    monkeypatch.setattr(sys, "argv", ["driver", "--run", "outputs/hpc/main"])
    d.main()
    return d.pipeline.read(run / "state.json"), events


def test_crash_after_map4_commit_still_settles_feedback_first(tmp_path, monkeypatch):
    state, events = run_main(tmp_path, monkeypatch, 4)
    assert events == ["feedback", "map"]


def test_acceptance_on_last_map_is_not_replaced_by_budget(tmp_path, monkeypatch):
    state, events = run_main(tmp_path, monkeypatch, 7, accepted=True)
    assert events == ["map", "feedback"]
    assert state["status"] == "one_material_trial_accepted"


def test_final_feedback_is_recovered_at_exhausted_map_budget(tmp_path, monkeypatch):
    state, events = run_main(tmp_path, monkeypatch, 8)
    assert events == ["feedback"]
    assert state["status"] == "diagnostic_round_complete"


def test_supervisor_restart_requires_exact_failure_acknowledgement():
    receipt = {"active_job": None, "finished_jobs": [
        {"job_id": "123", "state": "FAILED", "exit_code": "1:0"}]}
    for wrong in (None, "122"):
        with pytest.raises(RuntimeError, match="retry-failed-job"):
            supervisor.acknowledge_failed_job(receipt, wrong)
    supervisor.acknowledge_failed_job(receipt, "123")
    supervisor.acknowledge_failed_job(receipt, None)
    assert receipt["acknowledged_failed_jobs"] == ["123"]
    receipt["finished_jobs"].append({"job_id": "124", "state": "FAILED", "exit_code": "1:0"})
    with pytest.raises(RuntimeError):
        supervisor.acknowledge_failed_job(receipt, "123")


def test_all_zero_feedback_writes_finite_json_and_no_invented_hotspots():
    feedback = {key: np.zeros((4096, 3)) if key in ("photoionization_s1", "total_recombination_cm3_s")
                else np.zeros(4096) for key in ledger.HEATING_METRICS}
    feedback.update(subcell_width_cm=np.ones(4096), absorbed_power_erg_s_cm3=np.zeros(4096),
                    emitted_power_erg_s_cm3=np.zeros(4096))
    with np.errstate(all="raise"):
        result = ledger.heating_decomposition(feedback, feedback)
    assert result["metrics"]["atomic_rate_heating_erg_s_cm3"]["ratio"] == 0
    assert result["numerator_by_depth"]["top_folded_material_layers"] == []
    assert result["absorption_emission_cancellation"]["median_amplification"] is None
    json.dumps(result, allow_nan=False)
