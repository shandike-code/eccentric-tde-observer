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


def test_first_record_wins_so_a_rotation_cannot_rewrite_an_endpoint():
    # 同一路径先作为 map1 输出、后作为 map2 输入被记录；两者必须一致，
    # 若不一致（槽位被覆盖）以先记录者为准，由主流程的比对来拒绝。
    state = {"history": [
        {"input_path": "s.dat", "input_sha256": "old", "output_path": "t.dat", "output_sha256": "t0"},
        {"input_path": "t.dat", "input_sha256": "t0", "output_path": "s.dat", "output_sha256": "new"},
    ]}
    recorded = recorded_hashes(state)
    assert recorded["s.dat"] == "old"
    assert recorded["t.dat"] == "t0"


def test_missing_keys_are_tolerated_for_incomplete_states():
    assert recorded_hashes({}) == {}
    assert recorded_hashes({"history": [{"input_path": "a.dat"}]}) == {}
