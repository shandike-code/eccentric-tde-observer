import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_phase7b5y_retains_failed_batch_and_later_source_migration_is_audited():
    protocol = OUTPUT / "phase7b5y_preregistered_remap_batch_performance.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "539c6dab827e1e501e36be1ae39d4795a8c56a93e8051fdd82db169f4c6e0c85"
    )
    report = _load("phase7b5y_remap_batch_performance_summary.json")
    assert report["decision"]["all_output_hashes_exact"] is True
    assert report["decision"]["operator_runtime_gate_passed"] is False
    assert report["decision"]["phase7b5y_gate_passed"] is False
    assert report["decision"]["candidate_accepted"] is False
    legacy_hash = (
        "363c179e8aae73ea74f9ed15c17c24a6efc84be580ac37436ec7a6b85a4dc08c"
    )
    protocol_payload = json.loads(protocol.read_text(encoding="utf-8"))
    assert protocol_payload["sources"]["mixed_frame_frequency_baseline"][
        "sha256"
    ] == legacy_hash

    # 后续 signed-ALI 接口扩展不应伪装成 7B5y 的源回退；迁移审计必须证明
    # 正值反馈路径逐数组保持一致，同时保留旧版本的精确可重建哈希。
    source = ROOT / "src/eccentric_tde_observer/mixed_frame_frequency.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "ef27fc8b433ad84788c984f387f25ee025026a1bec5841e9ce087082da421689"
    )
    migration = _load("phase7b9cy_feedback_dependency_migration_audit.json")
    assert migration["legacy_frequency"]["sha256"] == legacy_hash
    assert migration["legacy_frequency"]["exactly_reconstructed_in_memory"] is True
    assert migration["positive_path_parity"]["angle_intensity_density"][
        "array_equal"
    ] is True
    assert migration["positive_path_parity"]["mean_intensity_density"][
        "array_equal"
    ] is True
    assert migration["positive_path_parity"]["comoving_angular_measure"][
        "array_equal"
    ] is True


def test_phase7b5z_lean_map_is_exact_and_faster():
    protocol = OUTPUT / "phase7b5z_preregistered_lean_source_map.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "32a819d7dbc6d2b9dce296bca62ed5e250e549b496ff388fe9619ca38c5a7655"
    )
    report = _load("phase7b5z_lean_source_map_summary.json")
    assert report["decision"]["all_output_hashes_exact"] is True
    assert report["decision"]["all_scalar_errors_passed"] is True
    assert report["operator_speedup"] > 1.0
    assert report["maximum_peak_rss_mib"] < 6144.0
    assert report["decision"]["phase7b5z_gate_passed"] is True
    assert report["decision"]["candidate_accepted"] is True


def test_phase7b6a_covers_full_frequency_grid_and_cleans_temporary_state():
    protocol = OUTPUT / "phase7b6a_preregistered_full_frequency_source_iteration.json"
    assert hashlib.sha256(protocol.read_bytes()).hexdigest() == (
        "0db832f868d56e8c4495a5e59e979b7bd5f4195b241003f6ff5797788d25ffaa"
    )
    report = _load("phase7b6a_full_frequency_source_iteration_summary.json")
    rows = report["all_block_rows"]
    assert len(rows) == 76
    assert rows[0]["core_group_start"] == 0
    assert rows[-1]["core_group_stop"] == 9632
    assert all(
        first["core_group_stop"] == second["core_group_start"]
        for first, second in zip(rows[:-1], rows[1:], strict=True)
    )
    assert report["temporary_output_file_size_bytes"] == 10_099_884_032
    assert report["temporary_output_removed"] is True
    assert report["wall_runtime_s"] < 900.0
    assert max(worker["peak_process_rss_mib"] for worker in report["workers"]) < 6144.0
    assert report["decision"]["phase7b6a_gate_passed"] is True
    assert report["decision"]["full_column_fixed_point_authorized"] is False


def test_phase7b6a_outputs_exist_but_large_memmap_does_not():
    for name in (
        "phase7b6a_worker1.json",
        "phase7b6a_worker2.json",
        "phase7b6a_full_frequency_source_iteration_summary.json",
        "phase7b6a_full_frequency_source_iteration.png",
    ):
        path = OUTPUT / name
        assert path.exists() and path.stat().st_size > 0
    assert not list(OUTPUT.glob("phase7b6a_*.dat"))
