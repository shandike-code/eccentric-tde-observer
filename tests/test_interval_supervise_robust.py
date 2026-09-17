import pytest

from operations.interval_supervise_robust import _job_id, queue_state, terminal_accounting


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_expired_job_record_is_not_an_error():
    # squeue 对过期/未知作业返回非零——必须解释成"已不在队列"，而不是异常。
    calls = []

    def runner(cmd, **kwargs):
        calls.append(cmd)
        return Result(returncode=1, stderr="slurm_load_jobs error: Invalid job id specified")

    assert queue_state("72208", runner=runner) is None
    assert calls[0][:3] == ["squeue", "-h", "-j"]


def test_queued_and_empty_listing():
    assert queue_state("1", runner=lambda c, **k: Result(0, "R\n")) == "R"
    assert queue_state("1", runner=lambda c, **k: Result(0, "PD\n")) == "PD"
    assert queue_state("1", runner=lambda c, **k: Result(0, "\n")) is None


def test_accounting_prefers_scontrol_then_sacct():
    def scontrol_ok(cmd, **kwargs):
        if cmd[0] == "scontrol":
            return Result(0, "JobId=9 JobState=COMPLETED ExitCode=0:0\n")
        raise AssertionError("sacct must not be queried when scontrol answers")

    assert terminal_accounting("9", runner=scontrol_ok) == ("COMPLETED", "0:0", "scontrol")

    def sacct_only(cmd, **kwargs):
        if cmd[0] == "scontrol":
            return Result(1, "")
        return Result(0, "FAILED|1:0\n")

    assert terminal_accounting("9", runner=sacct_only) == ("FAILED", "1:0", "sacct")


def test_unknown_job_reports_none_instead_of_raising():
    def nothing(cmd, **kwargs):
        return Result(1, "", "Invalid job id")

    assert terminal_accounting("9", runner=nothing) is None

    def empty_sacct(cmd, **kwargs):
        return Result(0, "\n") if cmd[0] == "sacct" else Result(1, "")

    assert terminal_accounting("9", runner=empty_sacct) is None


def test_non_terminal_scontrol_state_falls_through_to_sacct():
    def running_scontrol(cmd, **kwargs):
        if cmd[0] == "scontrol":
            return Result(0, "JobId=9 JobState=RUNNING\n")
        return Result(0, "\n")

    assert terminal_accounting("9", runner=running_scontrol) is None


def test_job_id_parsing_rejects_garbage():
    assert _job_id("72219;cluster\n") == "72219"
    with pytest.raises(ValueError):
        _job_id("sbatch: error: Invalid qos specification")
