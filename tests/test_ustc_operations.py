import copy
import pytest

from operations.cpu_scaling_benchmark import compare_cases
from operations.claude_watch import event_key, retain_scheduler_terminal


def test_scaling_requires_equal_output_and_reports_real_speedup():
    cases = [dict(workers=w, output_sha256="same", wall_s=120/w, total_wall_s=120/w+20)
             for w in (2, 4, 8)]
    compare_cases(cases)
    assert cases[-1]["map_speedup_vs_workers2"] == 4
    assert cases[-1]["total_speedup_vs_workers2"] == 80/35


def test_scaling_rejects_changed_output_even_when_faster():
    cases = [dict(output_sha256=digest, wall_s=wall, total_wall_s=wall+10)
             for digest, wall in (("a", 100), ("b", 20))]
    with pytest.raises(RuntimeError, match="output differs"):
        compare_cases(cases)


def test_watch_does_not_call_model_for_each_block_or_map():
    state = {"status": "radiation", "rounds": 14, "maps": 58, "committed_active_blocks": 2}
    updated = {**state, "maps": 59, "committed_active_blocks": 70}
    assert event_key(state) == event_key(updated)


@pytest.mark.parametrize("update", [
    {"rounds": 15}, {"status": "diagnostic_round_complete"},
    {"benchmark": {"status": "failed"}}, {"science_progress_stalled": True},
    {"supervisor": {"finished_jobs": [{"job_id": "42", "state": "FAILED", "exit_code": "1:0"}]}},
])
def test_watch_notices_meaningful_events(update):
    state = {"status": "radiation", "rounds": 14}
    assert event_key(state) != event_key({**state, **update})


def test_scheduler_terminal_survives_scontrol_record_expiry(tmp_path):
    state = {"benchmark_job": "123", "observed_at": "time1",
             "benchmark_slurm": "JobId=123 JobState=COMPLETED ExitCode=0:0"}
    retain_scheduler_terminal(tmp_path, state)
    original = (tmp_path / "scheduler-123.json").read_bytes()
    expired = {**state, "observed_at": "time2", "benchmark_slurm": "Invalid job id specified"}
    retain_scheduler_terminal(tmp_path, expired)
    assert "JobState=COMPLETED" in expired["benchmark_slurm"]
    assert expired["benchmark_slurm_current_lookup"] == "Invalid job id specified"
    assert (tmp_path / "scheduler-123.json").read_bytes() == original


def test_completed_artifact_is_not_invented_scheduler_evidence(tmp_path):
    state = {"benchmark_job": "123", "observed_at": "time1", "benchmark": {"status": "complete"},
             "benchmark_slurm": "Invalid job id specified"}
    retain_scheduler_terminal(tmp_path, state)
    assert state["benchmark_terminal_observation"] is None
    assert not (tmp_path / "scheduler-123.json").exists()
