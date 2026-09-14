"""Protect restore destinations and bounded restart semantics without big data."""
import importlib.util
import sys
import tarfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hpc"))
from preflight import safe_path, sha256, verify_claims
from restore_artifacts import validate_member
from resume import next_iteration
from pipeline import aggregate, pair_ready
from supervise import job_id


def test_snapshot_detects_changed_and_missing_data(tmp_path):
    p = tmp_path / "state"
    p.write_bytes(b"original")
    claim = {"path": "state", "size_bytes": 8, "sha256": sha256(p)}
    assert not verify_claims(tmp_path, [claim], hash_files=True)
    p.write_bytes(b"mutated!")
    assert verify_claims(tmp_path, [claim], hash_files=True)[0]["reason"] == "SHA-256 mismatch"
    p.unlink()
    assert verify_claims(tmp_path, [claim], hash_files=True)[0]["reason"] == "missing"


@pytest.mark.parametrize("name", ["../escape", "/absolute", "outputs/../../escape"])
def test_rejects_unsafe_restore_paths(tmp_path, name):
    with pytest.raises(ValueError):
        safe_path(tmp_path, name)


def test_rejects_links_and_large_checkpoint_members(tmp_path):
    member = tarfile.TarInfo("outputs/link")
    member.type = tarfile.SYMTYPE
    member.linkname = "../../outside"
    with pytest.raises(ValueError):
        validate_member(tmp_path, member)
    with pytest.raises(ValueError):
        validate_member(tmp_path, tarfile.TarInfo("outputs/checkpoints/state.dat"))
    assert validate_member(tmp_path, tarfile.TarInfo("outputs/input.npz")) == tmp_path / "outputs/input.npz"


def test_resume_uses_committed_iteration_not_history_length():
    assert next_iteration({"iterations": [{"iteration": 0}, {"iteration": 8}]}) == 9
    with pytest.raises(ValueError):
        next_iteration({"iterations": []})


def row(first, last, *, delta=2e-4):
    return {"core_group_start": first, "core_group_stop": last,
            "minimum_input_intensity": 0.0, "minimum_mapped_intensity": 0.0,
            "maximum_absolute_radiation_change": delta, "maximum_radiation_scale": 1.0,
            "boundary_spectrum_l1_numerator": 1e-6,
            "current_boundary_absolute_scale": 1.0, "mapped_boundary_absolute_scale": 1.0,
            "current_boundary_bolometric": 1.0, "mapped_boundary_bolometric": 1.0,
            "peak_process_rss_mib": 100.0}


def test_residual_uses_global_scale_and_exact_ownership():
    a, b = row(0, 2), row(2, 4)
    b["maximum_radiation_scale"] = 2.0
    result = aggregate([a, b], frequency_groups=4)
    assert result["residual"] == 1e-4
    assert result["boundary_l1"] == 1e-6
    with pytest.raises(ArithmeticError):
        aggregate([a, a], frequency_groups=4)
    b["minimum_mapped_intensity"] = -1e-30
    with pytest.raises(ArithmeticError):
        aggregate([a, b], frequency_groups=4)


def test_relaxed_pair_still_requires_two_states_and_both_boundary_gates():
    good = {"residual": 2.1e-4, "boundary_l1": 1e-6, "boundary_bolometric": 1e-6}
    assert not pair_ready([good], 2.5e-4)
    assert pair_ready([good, good], 2.5e-4)
    assert not pair_ready([good, good], 1e-4)
    assert not pair_ready([good, {**good, "boundary_l1": 1e-3}], 2.5e-4)
    assert not pair_ready([good, {**good, "residual": 2.5e-4}], 2.5e-4)


def test_sbatch_job_id_is_not_arbitrary_shell_text():
    assert job_id("12345;cluster\n") == "12345"
    with pytest.raises(ValueError):
        job_id("error: rejected by QOS")


def test_partial_batch_resume_skips_committed_blocks_and_detects_corruption(tmp_path, monkeypatch):
    import pipeline
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "STOP", False)
    run = tmp_path / "outputs/hpc/test"
    run.mkdir(parents=True)
    pipeline.write_json(run / "config.json", {})
    config = {"run": "outputs/hpc/test", "workers": 2}
    records = [{"block_index": i, "core_group_start": i, "core_group_stop": i + 1,
                "output_block_sha256": "intact"} for i in range(74)]
    state = {"current_sha256": "input", "records": records}
    launched = []
    class Process:
        def __init__(self, cmd, **kwargs):
            index = int(cmd[cmd.index("--block") + 1])
            launched.append(index)
            pipeline.write_json(Path(cmd[cmd.index("--report") + 1]), {
                "block_index": index, "core_group_start": index, "core_group_stop": index + 1,
                "protocol_sha256": pipeline.sha256(run / "config.json"), "input_state_sha256": "input"})
        def wait(self):
            return 0
    monkeypatch.setattr(pipeline.subprocess, "Popen", Process)
    monkeypatch.setattr(pipeline, "block_hash", lambda *args: "intact")
    arguments = (config, state, "map", run / "input", run / "output", records,
                 run / "reports", run / "state.json")
    assert pipeline.batches(*arguments)
    assert launched == [74, 75]
    assert len(pipeline.read(run / "state.json")["records"]) == 76
    monkeypatch.setattr(pipeline, "block_hash", lambda *args: "corrupted")
    with pytest.raises(RuntimeError, match="committed output block changed"):
        pipeline.batches(*arguments)
    assert launched == [74, 75]


def test_stop_signal_does_not_launch_or_commit_a_partial_map(tmp_path, monkeypatch):
    import pipeline
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "STOP", True)
    def unexpected(*args, **kwargs):
        raise AssertionError("worker launched after stop request")
    monkeypatch.setattr(pipeline.subprocess, "Popen", unexpected)
    state_path = tmp_path / "state.json"
    assert not pipeline.batches({"run": "run", "workers": 2}, {}, "map",
        tmp_path / "input", tmp_path / "output", [], tmp_path / "reports", state_path)
    assert not state_path.exists()
