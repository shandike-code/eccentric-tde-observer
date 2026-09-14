"""7B9dp post-streaming pure-Picard 的纯 tmp_path 测试。"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "scripts", ROOT / "tests"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from scripts import phase7b9_half_trial_positive_sequence_engine as engine
from scripts import phase7b9_half_trial_radiation_continuation as storage
from scripts import phase7b9dp_post_streaming_picard as picard
from scripts import phase7b9dp_preregister_post_streaming_picard as preregister
from test_phase7b9dn_repeat_streaming_anderson import _fixture as cycle_fixture


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prepare_cycle(
    root: Path, *, source_collision: bool | str = False, dat_source: bool = False
) -> dict[str, str]:
    paths = cycle_fixture(
        root, source_collision=source_collision, dat_source=dat_source
    )
    for relative in (
        picard.RUNNER_RELATIVE_PATH,
        picard.PREREGISTER_RELATIVE_PATH,
        storage.SEQUENCE_ENGINE_RELATIVE_PATH,
        storage.RUNNER_RELATIVE_PATH,
        picard.progression.RUNNER_RELATIVE_PATH,
        picard.repeat.BUILDER_RELATIVE_PATH,
        storage.common.MAP_WORKER,
        storage.common.WORKER_HELPERS,
        storage.common.GENERIC_MAP_RUNNER,
    ):
        _write(root / relative, f"small executable: {relative}".encode())
    return paths


def _spec(paths: dict[str, str]) -> picard.PostStreamingPicardSpec:
    return picard.PostStreamingPicardSpec(
        phase="7B9dp test post-streaming pure Picard",
        phase_index=1435,
        classification="[A]+[V]+[O]",
        prior_protocol_path=paths["protocol"],
        prior_pass1_manifest_path=paths["pass1"],
        prior_pass2_manifest_path=paths["pass2"],
        prior_candidate_commit_manifest_path=paths["commit"],
        prior_fresh_manifest_path=paths["fresh"],
        prior_fresh_summary_path=paths["summary"],
        runner_path=picard.RUNNER_RELATIVE_PATH,
        manifest_path="outputs/checkpoints/dp/manifest.json",
        transient_report_directory=(
            "outputs/checkpoints/phase7b9dp_transient_reports"
        ),
        summary_path="outputs/dp_summary.json",
        figure_path="outputs/dp_convergence.png",
    )


def test_builder_seeds_fresh_lineage_and_freezes_40_map_horizon(
    tmp_path: Path,
) -> None:
    paths = _prepare_cycle(tmp_path)
    protocol = picard.build_post_streaming_picard_protocol(
        tmp_path, _spec(paths)
    )
    summary = json.loads((tmp_path / paths["summary"]).read_text())
    seed = protocol["seed_iteration"]
    cfg = protocol["configuration"]
    assert seed["input_state_path"] == summary["candidate_state_path"]
    assert seed["input_state_sha256"] == summary["candidate_state_sha256"]
    assert seed["mapped_state_path"] == summary["mapped_state_path"]
    assert seed["mapped_state_sha256"] == summary["mapped_state_sha256"]
    assert seed["global_original_operator_residual"] == summary[
        "fresh_input_global_original_operator_residual"
    ]
    assert seed["progression_passed"] is True
    assert cfg["initial_state_path"] == seed["mapped_state_path"]
    assert cfg["scratch_state_path"] == seed["input_state_path"]
    assert cfg["seed_completed_picard_maps"] == 1
    assert cfg["maximum_additional_picard_maps"] == 40
    assert cfg["maximum_picard_maps"] == 41
    assert (cfg["first_runtime_iteration"], cfg["last_runtime_iteration"]) == (
        1,
        40,
    )
    assert cfg["maximum_concurrent_processes"] == 2
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert protocol["authorization"]["pure_picard_only"] is True
    assert protocol["authorization"]["anderson_after_seed"] is False
    assert protocol["authorization"]["material_feedback_authorized"] is False
    assert protocol["storage_plan"]["additional_full_state_allocation_count"] == 0


def test_builder_pins_prior_artifacts_runner_engine_and_workers(
    tmp_path: Path,
) -> None:
    paths = _prepare_cycle(tmp_path)
    protocol = picard.build_post_streaming_picard_protocol(
        tmp_path, _spec(paths)
    )
    expected_keys = {
        "post_streaming_prior_protocol",
        "post_streaming_prior_pass1_manifest",
        "post_streaming_prior_pass2_manifest",
        "post_streaming_prior_candidate_commit_manifest",
        "post_streaming_prior_fresh_manifest",
        "post_streaming_prior_fresh_summary",
        "post_streaming_picard_runner",
        "post_streaming_picard_preregister",
        "post_streaming_sequence_engine",
        "post_streaming_storage_helper",
        "post_streaming_progression_gate_helper",
        "post_streaming_cycle_validator",
        "post_streaming_map_worker",
        "post_streaming_worker_helpers",
        "post_streaming_generic_map_runner",
    }
    assert expected_keys <= set(protocol["sources"])
    assert all(
        not source["path"].lower().endswith(".dat")
        for source in protocol["sources"].values()
    )
    assert all(
        claim["path"].lower().endswith(".dat")
        for claim in protocol["full_state_claims"].values()
    )


def test_preregister_cli_writes_only_a_small_protocol(tmp_path: Path) -> None:
    paths = _prepare_cycle(tmp_path)
    output = "outputs/phase7b9dp_protocol.json"
    payload, digest = preregister.main(
        [
            "--phase",
            "7B9dp test",
            "--phase-index",
            "1435",
            "--classification",
            "[A]+[V]+[O]",
            "--prior-protocol",
            paths["protocol"],
            "--prior-pass1-manifest",
            paths["pass1"],
            "--prior-pass2-manifest",
            paths["pass2"],
            "--prior-candidate-commit-manifest",
            paths["commit"],
            "--prior-fresh-manifest",
            paths["fresh"],
            "--prior-fresh-summary",
            paths["summary"],
            "--manifest",
            "outputs/checkpoints/dp/manifest.json",
            "--transient-report-directory",
            "outputs/checkpoints/phase7b9dp_transient_reports",
            "--summary",
            "outputs/dp_summary.json",
            "--figure",
            "outputs/dp.png",
            "--output",
            output,
        ],
        root=tmp_path,
    )
    assert digest == _sha(tmp_path / output)
    assert payload == json.loads((tmp_path / output).read_text())
    assert not (tmp_path / f"{output}.tmp").exists()


def _runtime_protocol(
    root: Path,
) -> tuple[Path, str, dict[str, object], np.ndarray, np.ndarray]:
    paths = _prepare_cycle(root)
    protocol = picard.build_post_streaming_picard_protocol(root, _spec(paths))
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    candidate = np.full(76, 0.9, dtype=np.float64)
    mapped = np.full(76, 1.0, dtype=np.float64)
    candidate_path = root / protocol["seed_iteration"]["input_state_path"]
    mapped_path = root / protocol["seed_iteration"]["mapped_state_path"]
    _write(candidate_path, candidate.tobytes())
    _write(mapped_path, mapped.tobytes())
    candidate_hash = _sha(candidate_path)
    mapped_hash = _sha(mapped_path)
    cfg.update(
        {
            "physical_frequency_groups": 76,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
            "natural_frequency_block_count": 76,
            "diagnostic_frequency_block": 1,
            "raw_float64_checkpoint_size_bytes": 76 * 8,
            "initial_state_sha256": mapped_hash,
            "scratch_state_initial_sha256": candidate_hash,
        }
    )
    gates["owned_frequency_group_count_exactly"] = 76
    seed = protocol["seed_iteration"]
    seed.update(
        {
            "input_state_sha256": candidate_hash,
            "mapped_state_sha256": mapped_hash,
            "global_original_operator_residual": 1.0e-2,
            "boundary_spectrum_l1": 2.0e-3,
            "boundary_bolometric_fraction": 2.0e-3,
            "convergence_gate_checks": {
                "residual_pass": False,
                "boundary_spectrum_pass": False,
                "boundary_bolometric_pass": False,
            },
            "convergence_passed": False,
            "map_passed": False,
            "original_map_passed": False,
        }
    )
    protocol["full_state_claims"]["current_initial_is_prior_mapped"].update(
        {"size_bytes": 76 * 8, "sha256": mapped_hash}
    )
    protocol["full_state_claims"]["scratch_initial_is_prior_candidate"].update(
        {"size_bytes": 76 * 8, "sha256": candidate_hash}
    )
    protocol_path = root / "outputs/dp_runtime_protocol.json"
    _write(protocol_path, protocol)
    return protocol_path, _sha(protocol_path), protocol, candidate, mapped


def _executor(
    protocol_hash: str,
    metrics_by_iteration: dict[int, tuple[float, float, float]],
    seen: list[tuple[int, int]],
    *,
    fail_once_at: tuple[int, int] | None = None,
):
    failed = False

    def execute(
        iteration: int,
        indices: list[int],
        input_path: Path,
        input_hash: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        nonlocal failed
        if fail_once_at == (iteration, indices[0]) and not failed:
            failed = True
            raise RuntimeError("simulated worker crash")
        residual, boundary, bolometric = metrics_by_iteration[iteration]
        input_values = np.frombuffer(input_path.read_bytes(), dtype=np.float64)
        rows = []
        for index in indices:
            seen.append((iteration, index))
            mapped_value = float(input_values[index] + 0.01)
            with output_path.open("r+b") as stream:
                stream.seek(index * 8)
                stream.write(np.asarray([mapped_value], dtype=np.float64).tobytes())
                stream.flush()
            rows.append(
                {
                    "protocol_sha256": protocol_hash,
                    "input_state_sha256": input_hash,
                    "picard_iteration": iteration,
                    "block_index": index,
                    "core_group_start": index,
                    "core_group_stop": index + 1,
                    "maximum_absolute_radiation_change": residual,
                    "maximum_radiation_scale": 1.0,
                    "boundary_spectrum_l1_numerator": boundary,
                    "current_boundary_absolute_scale": 1.0,
                    "mapped_boundary_absolute_scale": 1.0,
                    "current_boundary_bolometric": 1.0,
                    "mapped_boundary_bolometric": 1.0 / (1.0 - bolometric),
                    "minimum_input_intensity": 0.5,
                    "minimum_mapped_intensity": 0.5,
                    "peak_process_rss_mib": 100.0,
                    "wall_runtime_s": 1.0,
                }
            )
        return rows

    return execute


def test_nonconverged_map_continues_then_first_low_residual_pauses(
    tmp_path: Path,
) -> None:
    protocol_path, digest, protocol, candidate, _ = _runtime_protocol(tmp_path)
    seen: list[tuple[int, int]] = []
    executor = _executor(
        digest,
        {1: (5.0e-3, 2.0e-3, 2.0e-3), 2: (5.0e-5, 5.0e-4, 5.0e-4)},
        seen,
    )
    first = picard.run_continuation(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=executor,
        stop_after_iteration=1,
    )
    assert first["status"] == "running"
    assert first["completed_additional_picard_maps"] == 1
    assert first["iterations"][-1]["boundary_spectrum_l1"] > 1.0e-3
    assert first["iterations"][-1]["progression_passed"] is True
    assert [index for iteration, index in seen if iteration == 1] == list(range(76))
    scratch = tmp_path / protocol["configuration"]["scratch_state_path"]
    assert not np.array_equal(np.frombuffer(scratch.read_bytes(), dtype=np.float64), candidate)

    second = picard.run_continuation(
        tmp_path, protocol_path, digest, batch_executor=executor
    )
    assert second["status"] == "provisional_pause"
    assert second["completed_additional_picard_maps"] == 2
    assert second["decision"]["provisional_feedback_extraction_authorized"] is True
    assert second["decision"]["provisional_feedback_is_formal_pair_authority"] is False
    assert second["decision"]["material_feedback_authorized"] is False
    assert second["decision"]["anderson_used_after_seed"] is False
    assert second["accepted_state_path"] == second["iterations"][-1][
        "input_state_path"
    ]


def test_crash_recovery_keeps_completed_blocks_and_compacts_transient(
    tmp_path: Path,
) -> None:
    protocol_path, digest, protocol, _, _ = _runtime_protocol(tmp_path)
    seen_before: list[tuple[int, int]] = []
    failing = _executor(
        digest,
        {1: (5.0e-3, 2.0e-3, 2.0e-3)},
        seen_before,
        fail_once_at=(1, 2),
    )
    with pytest.raises(RuntimeError, match="simulated worker crash"):
        picard.run_continuation(
            tmp_path, protocol_path, digest, batch_executor=failing
        )
    manifest_path = tmp_path / protocol["configuration"]["manifest_path"]
    interrupted = json.loads(manifest_path.read_text())
    assert [
        row["block_index"]
        for row in interrupted["active_iteration"]["completed_blocks"]
    ] == [0, 1]

    seen_after: list[tuple[int, int]] = []
    summary = picard.run_continuation(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=_executor(
            digest,
            {1: (5.0e-3, 2.0e-3, 2.0e-3)},
            seen_after,
        ),
        stop_after_iteration=1,
    )
    assert summary["status"] == "running"
    assert [index for _, index in seen_after] == list(range(2, 76))
    assert summary["iterations"][-1]["block_report_audit"]["record_count"] == 76
    transient = tmp_path / protocol["configuration"]["report_directory"]
    assert [path.name for path in transient.iterdir()] == [
        ".phase7b9_transient_owner.json"
    ]


def test_builder_rejects_source_collision_dat_and_does_not_modify_engine(
    tmp_path: Path,
) -> None:
    engine_path = Path(engine.__file__)
    original_engine_hash = _sha(engine_path)

    collision = tmp_path / "collision"
    paths = _prepare_cycle(
        collision, source_collision="post_streaming_prior_protocol"
    )
    with pytest.raises(RuntimeError, match="source-key collision"):
        picard.build_post_streaming_picard_protocol(collision, _spec(paths))

    forbidden = tmp_path / "dat"
    paths = _prepare_cycle(forbidden, dat_source=True)
    with pytest.raises(RuntimeError, match=r"\.dat source"):
        picard.build_post_streaming_picard_protocol(forbidden, _spec(paths))

    clean = tmp_path / "clean"
    paths = _prepare_cycle(clean)
    spec = replace(_spec(paths), prior_fresh_summary_path="outputs/missing.dat")
    with pytest.raises(RuntimeError, match="only prior JSON"):
        picard.build_post_streaming_picard_protocol(clean, spec)
    assert _sha(engine_path) == original_engine_hash
