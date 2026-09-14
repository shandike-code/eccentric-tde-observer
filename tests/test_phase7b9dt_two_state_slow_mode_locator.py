from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import phase7b9dt_preregister_two_state_slow_mode_locator as prereg
import phase7b9dt_two_state_slow_mode_locator as locator


EDGES = np.asarray([1.0e14, 2.0e14, 4.0e14, 8.0e14, 1.6e15, 3.2e15])


def _bytes_sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": locator.sha256(path),
    }


def _states() -> tuple[np.ndarray, np.ndarray]:
    input_state = np.ones((5, 2, 3), dtype=np.float64)
    input_state[1, 0, 0] = 100.0
    mapped_state = input_state.copy()
    mapped_state[3, 1, 2] += 20.0
    return input_state, mapped_state


def _fixture(root: Path) -> locator.TwoStateSlowModeLocatorSpec:
    frequency = root / "outputs/frequency.npz"
    frequency.parent.mkdir(parents=True, exist_ok=True)
    np.savez(frequency, active_edge_hz=EDGES)
    _write(root, "scripts/upstream_helper.py", b"# upstream\n")
    input_state, mapped_state = _states()
    input_bytes = input_state.tobytes(order="C")
    mapped_bytes = mapped_state.tobytes(order="C")
    brute = float(np.max(np.abs(mapped_state - input_state))) / max(
        float(np.max(np.abs(input_state))), float(np.max(np.abs(mapped_state)))
    )
    ending_protocol_path = "outputs/ending_protocol.json"
    ending_manifest_path = "outputs/ending_manifest.json"
    ending_summary_path = "outputs/ending_summary.json"
    ending_protocol = {
        "phase": "end",
        "sources": {
            "phase7b5p_master_input": _source(root, "outputs/frequency.npz"),
            "upstream_helper": _source(root, "scripts/upstream_helper.py"),
        },
        "configuration": {
            "physical_frequency_groups": 5,
            "angular_direction_count": 2,
            "radiation_depth_cell_count": 3,
            "raw_float64_checkpoint_size_bytes": len(input_bytes),
            "core_frequency_groups": 2,
            "natural_frequency_block_count": 3,
        },
        "gates": {"global_original_operator_residual_below": 1.0e-4},
    }
    _write_json(root, ending_protocol_path, ending_protocol)
    protocol_sha = locator.sha256(root / ending_protocol_path)
    iterations = [
        {
            "iteration": 8,
            "input_state_path": "outputs/checkpoints/older.dat",
            "input_state_sha256": "a" * 64,
            "mapped_state_path": "outputs/checkpoints/older-mapped.dat",
            "mapped_state_sha256": "b" * 64,
            "global_original_operator_residual": 0.25,
            "progression_passed": True,
        },
        {
            "iteration": 9,
            "input_state_path": "outputs/checkpoints/input.dat",
            "input_state_sha256": _bytes_sha(input_bytes),
            "mapped_state_path": "outputs/checkpoints/mapped.dat",
            "mapped_state_sha256": _bytes_sha(mapped_bytes),
            "global_original_operator_residual": brute,
            "progression_passed": True,
            "map_passed": False,
        },
    ]
    manifest = {
        "protocol_sha256": protocol_sha,
        "status": "maximum_maps_exhausted",
        "active_iteration": None,
        "current_input_path": iterations[-1]["input_state_path"],
        "current_input_sha256": iterations[-1]["input_state_sha256"],
        "next_output_path": iterations[-1]["mapped_state_path"],
        "next_output_sha256": iterations[-1]["mapped_state_sha256"],
        "iterations": iterations,
    }
    summary = {
        "protocol_sha256": protocol_sha,
        "status": manifest["status"],
        "iterations": iterations,
    }
    _write_json(root, ending_manifest_path, manifest)
    _write_json(root, ending_summary_path, summary)
    for source in (
        locator.RUNNER_RELATIVE_PATH,
        locator.PREREGISTER_RELATIVE_PATH,
        locator.RESIDUAL_DEFINITION_RELATIVE_PATH,
    ):
        destination = root / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((PROJECT_ROOT / source).read_bytes())
    return locator.TwoStateSlowModeLocatorSpec(
        phase="7B9dt test",
        phase_index=209,
        classification="[A-preregistered]+[V-diagnostic]+[O]",
        ending_protocol_path=ending_protocol_path,
        ending_manifest_path=ending_manifest_path,
        ending_summary_path=ending_summary_path,
        analyzer_runner_path=locator.RUNNER_RELATIVE_PATH,
        preregister_runner_path=locator.PREREGISTER_RELATIVE_PATH,
        block_json_path="outputs/dt_blocks.json",
        block_csv_path="outputs/dt_blocks.csv",
        summary_path="outputs/dt_summary.json",
        figure_path="outputs/dt.png",
    )


def _update_protocol_hash(root: Path, spec: locator.TwoStateSlowModeLocatorSpec) -> None:
    digest = locator.sha256(root / spec.ending_protocol_path)
    for relative in (spec.ending_manifest_path, spec.ending_summary_path):
        payload = json.loads((root / relative).read_text(encoding="utf-8"))
        payload["protocol_sha256"] = digest
        _write_json(root, relative, payload)


def test_array_recomputation_matches_brute_force_and_maps_indices() -> None:
    input_state, mapped_state = _states()
    result = locator.analyze_arrays(input_state, mapped_state, EDGES, 2)
    brute = float(np.max(np.abs(mapped_state - input_state))) / max(
        float(np.max(np.abs(input_state))), float(np.max(np.abs(mapped_state)))
    )
    assert result["global_original_operator_residual"] == brute == 0.2
    assert result["frequency_ownership_exact"] is True
    assert result["natural_frequency_block_count"] == 3
    assert result["numerator_control"]["block_index"] == 1
    assert result["numerator_control"]["controlling_frequency_group"] == 3
    assert result["numerator_control"]["controlling_angle_index"] == 1
    assert result["numerator_control"]["controlling_depth_index"] == 2
    assert result["numerator_control"]["frequency_lower_hz"] == EDGES[3]
    assert result["scale_control"]["source_state"] == "input"
    assert result["scale_control"]["block_index"] == 0
    assert result["scale_control"]["frequency_group"] == 1
    assert result["scale_control"]["angle_index"] == 0
    assert result["scale_control"]["depth_index"] == 0
    assert result["scale_control"]["absolute_scale"] == 100.0
    assert result["scale_control"]["frequency_lower_hz"] == EDGES[1]


def test_nonfinite_state_fails_without_repair() -> None:
    input_state, mapped_state = _states()
    mapped_state[2, 0, 1] = np.nan
    with pytest.raises(ArithmeticError, match="non-finite"):
        locator.analyze_arrays(input_state, mapped_state, EDGES, 2)


def test_builder_pins_only_small_sources_and_does_not_open_dat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    original_sha = locator.sha256

    def guarded_sha(path: Path) -> str:
        assert path.suffix.lower() != ".dat"
        return original_sha(path)

    monkeypatch.setattr(locator, "sha256", guarded_sha)
    protocol = locator.build_two_state_slow_mode_locator_protocol(tmp_path, spec)
    assert all(not source["path"].endswith(".dat") for source in protocol["sources"].values())
    assert set(protocol["full_state_claims"]) == {"input_state", "mapped_state"}
    assert not (tmp_path / "outputs/checkpoints/input.dat").exists()
    assert not (tmp_path / "outputs/checkpoints/mapped.dat").exists()
    assert protocol["gates"]["global_original_operator_residual_below"] == 1.0e-4
    assert protocol["gates"]["residual_reproduction_absolute_tolerance"] == 0.0
    assert protocol["builder_audit"]["threshold_changed"] is False


def test_builder_accepts_post_streaming_frequency_block_field(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    path = tmp_path / spec.ending_protocol_path
    protocol = json.loads(path.read_text(encoding="utf-8"))
    protocol["configuration"]["diagnostic_frequency_block"] = protocol[
        "configuration"
    ].pop("core_frequency_groups")
    _write_json(tmp_path, spec.ending_protocol_path, protocol)
    _update_protocol_hash(tmp_path, spec)

    result = locator.build_two_state_slow_mode_locator_protocol(tmp_path, spec)
    assert result["configuration"]["core_frequency_groups"] == 2
    assert result["configuration"]["natural_frequency_block_count"] == 3


@pytest.mark.parametrize("failure", ["threshold", "active", "lineage", "dat_source"])
def test_builder_rejects_changed_terminal_evidence(
    tmp_path: Path, failure: str
) -> None:
    spec = _fixture(tmp_path)
    if failure in {"threshold", "dat_source"}:
        path = tmp_path / spec.ending_protocol_path
        protocol = json.loads(path.read_text(encoding="utf-8"))
        if failure == "threshold":
            protocol["gates"]["global_original_operator_residual_below"] = 2.0e-4
        else:
            protocol["sources"]["forbidden"] = {
                "path": "outputs/checkpoints/forbidden.dat",
                "size_bytes": 8,
                "sha256": "c" * 64,
            }
        _write_json(tmp_path, spec.ending_protocol_path, protocol)
        _update_protocol_hash(tmp_path, spec)
    else:
        path = tmp_path / spec.ending_manifest_path
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if failure == "active":
            manifest["active_iteration"] = {"iteration": 10}
        else:
            manifest["next_output_sha256"] = "f" * 64
        _write_json(tmp_path, spec.ending_manifest_path, manifest)
    match = {
        "threshold": "threshold changed",
        "active": "atomic terminal",
        "lineage": "lineage changed",
        "dat_source": "small sources cannot contain .dat",
    }[failure]
    with pytest.raises(RuntimeError, match=match):
        locator.build_two_state_slow_mode_locator_protocol(tmp_path, spec)


def test_runtime_hashes_each_state_once_and_writes_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _fixture(tmp_path)
    protocol_path = tmp_path / "outputs/dt_protocol.json"
    protocol, digest = locator.write_two_state_slow_mode_locator_protocol(
        tmp_path, spec, protocol_path
    )
    input_state, mapped_state = _states()
    _write(tmp_path, protocol["full_state_claims"]["input_state"]["path"], input_state.tobytes())
    _write(tmp_path, protocol["full_state_claims"]["mapped_state"]["path"], mapped_state.tobytes())
    original_sha = locator.sha256
    counts: dict[str, int] = {}

    def counted_sha(path: Path) -> str:
        if path.suffix.lower() == ".dat":
            counts[path.name] = counts.get(path.name, 0) + 1
        return original_sha(path)

    monkeypatch.setattr(locator, "sha256", counted_sha)
    summary = locator.run_locator(tmp_path, protocol_path, digest)
    assert counts == {"input.dat": 1, "mapped.dat": 1}
    assert summary["status"] == "complete"
    assert summary["global_original_operator_residual"] == 0.2
    assert summary["gate_checks"] == {
        "frequency_ownership_pass": True,
        "original_operator_residual_exactly_reproduced": True,
        "target_unchanged_pass": True,
    }
    assert summary["decision"]["convergence_proven"] is False
    for relative in (
        spec.block_json_path,
        spec.block_csv_path,
        spec.summary_path,
        spec.figure_path,
    ):
        assert (tmp_path / relative).is_file()


def test_preregister_cli_writes_protocol_atomically(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    argv = [
        "--phase", spec.phase,
        "--phase-index", str(spec.phase_index),
        "--classification", spec.classification,
        "--ending-protocol", spec.ending_protocol_path,
        "--ending-manifest", spec.ending_manifest_path,
        "--ending-summary", spec.ending_summary_path,
        "--block-json", spec.block_json_path,
        "--block-csv", spec.block_csv_path,
        "--summary", spec.summary_path,
        "--figure", spec.figure_path,
        "--output", "outputs/dt_protocol.json",
    ]
    protocol, digest = prereg.main(argv, root=tmp_path)
    output = tmp_path / "outputs/dt_protocol.json"
    assert digest == locator.sha256(output)
    assert json.loads(output.read_text(encoding="utf-8")) == protocol
    assert not output.with_name(f"{output.name}.tmp").exists()
