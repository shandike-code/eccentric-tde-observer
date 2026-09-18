from operations.prepare_extension_run import recorded_hashes


def test_recorded_hashes_collects_history_and_round_endpoints():
    state = {
        "history": [
            {"input_path": "a.dat", "input_sha256": "h1", "output_path": "b.dat", "output_sha256": "h2"},
            {"input_path": "b.dat", "input_sha256": "h2", "output_path": "c.dat", "output_sha256": "h3"},
        ],
        "diagnostic": {"rounds": [
            {"endpoints_claim": {"previous": {"path": "a.dat", "sha256": "h1"},
                                 "final": {"path": "c.dat", "sha256": "h3"}}},
        ]},
    }
    recorded = recorded_hashes(state)
    assert recorded == {"a.dat": "h1", "b.dat": "h2", "c.dat": "h3"}


def test_last_write_wins_so_a_rotating_slot_uses_its_final_bytes():
    # 轮换槽位 s.dat 先被 map1 写、后被 map2 写；只有最后写入能与磁盘现状比较。
    # 用首次记录会把完好的 run 误判成被覆盖（曾真实发生）。
    state = {"history": [
        {"input_path": "s.dat", "input_sha256": "old", "output_path": "t.dat", "output_sha256": "t0"},
        {"input_path": "t.dat", "input_sha256": "t0", "output_path": "s.dat", "output_sha256": "new"},
    ]}
    recorded = recorded_hashes(state)
    assert recorded["s.dat"] == "new"
    assert recorded["t.dat"] == "t0"


def test_round_endpoints_only_fill_paths_the_history_never_wrote():
    state = {
        "history": [{"output_path": "s.dat", "output_sha256": "latest"}],
        "diagnostic": {"rounds": [{"endpoints_claim": {
            "previous": {"path": "s.dat", "sha256": "older-input"},
            "final": {"path": "z.dat", "sha256": "only-in-round"}}}]},
    }
    recorded = recorded_hashes(state)
    assert recorded["s.dat"] == "latest"
    assert recorded["z.dat"] == "only-in-round"


def test_missing_keys_are_tolerated_for_incomplete_states():
    assert recorded_hashes({}) == {}
    assert recorded_hashes({"history": [{"input_path": "a.dat"}]}) == {}


def test_carry_trial_copies_and_verifies_identity():
    import shutil as _shutil
    import uuid
    import numpy as np
    import pytest
    from operations.collect_encoded_ratios import ROOT as REPO
    from operations.prepare_extension_run import carry_trial

    name = f"carry-selftest-{uuid.uuid4().hex[:8]}"
    source = REPO / "outputs/hpc" / name / "source"
    run = REPO / "outputs/hpc" / name / "run"
    try:
        source.mkdir(parents=True)
        run.mkdir(parents=True)
        base = np.arange(8, dtype=float)
        direction = np.linspace(-0.1, 0.1, 8)
        np.savez(source / "trial_material.npz",
                 encoded_state=base + 0.0078125 * direction,
                 base_encoded_state=base, finite_direction=direction,
                 base_residual=np.full(8, 0.5), relaxation=np.array(0.0078125))
        report = carry_trial(source, run)
        assert report["relaxation"] == 0.0078125 and report["encoded_vector_size"] == 8
        with np.load(run / "trial_material.npz") as copied:
            assert np.array_equal(copied["encoded_state"], base + 0.0078125 * direction)
        # 负面：源缺 trial 时必须拒绝，而不是让 pipeline 去复制 MATERIAL
        (source / "trial_material.npz").unlink()
        with pytest.raises(SystemExit):
            carry_trial(source, run)
    finally:
        _shutil.rmtree(REPO / "outputs/hpc" / name, ignore_errors=True)


def test_carry_trial_rejects_tampered_copy(monkeypatch):
    import shutil as _shutil
    import uuid
    import numpy as np
    import pytest
    from operations.collect_encoded_ratios import ROOT as REPO
    import operations.prepare_extension_run as module

    name = f"carry-tamper-{uuid.uuid4().hex[:8]}"
    source = REPO / "outputs/hpc" / name / "source"
    run = REPO / "outputs/hpc" / name / "run"
    try:
        source.mkdir(parents=True)
        run.mkdir(parents=True)
        base = np.zeros(4)
        direction = np.ones(4)
        np.savez(source / "trial_material.npz", encoded_state=base + 0.01 * direction,
                 base_encoded_state=base, finite_direction=direction,
                 base_residual=np.zeros(4), relaxation=np.array(0.01))
        real_copy = _shutil.copyfile

        def tampering_copy(src, dst, **kwargs):
            real_copy(src, dst, **kwargs)
            with np.load(dst, allow_pickle=True) as data:
                payload = {key: np.asarray(data[key]) for key in data.files}
            payload["encoded_state"] = payload["encoded_state"] + 1.0
            np.savez(dst, **payload)

        monkeypatch.setattr(module.shutil, "copyfile", tampering_copy)
        with pytest.raises(SystemExit):
            module.carry_trial(source, run)
    finally:
        _shutil.rmtree(REPO / "outputs/hpc" / name, ignore_errors=True)
