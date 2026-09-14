"""Resource-adjusted Picard builder and seed-manifest small-file tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_resource_adjusted_picard.py"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("phase7b9_resource_adjusted_picard", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not import resource-adjusted Picard")
adjusted = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adjusted
SPEC.loader.exec_module(adjusted)
common = adjusted.common


def _write(root: Path, relative: str, content: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    _write(root, relative, json.dumps(payload, indent=2).encode())


def _source(root: Path, relative: str) -> dict[str, object]:
    return common.source_entry(root, relative)


def _records() -> list[dict[str, object]]:
    records = []
    for index in range(19):
        input_path = f"outputs/checkpoints/state_{index:02d}.dat"
        mapped_path = f"outputs/checkpoints/state_{index + 1:02d}.dat"
        checks = {
            "frequency_ownership_pass": True,
            "positive_map_pass": True,
            "initial_reproduction_pass": True,
            "contraction_pass": True,
            "boundary_pass": True,
            "resources_pass": index < 18,
        }
        records.append(
            {
                "iteration": index,
                "input_state_path": input_path,
                "input_state_sha256": f"input-{index:02d}",
                "mapped_state_path": mapped_path,
                "mapped_state_sha256": f"input-{index + 1:02d}",
                "global_original_operator_residual": 2.0e-4 - index * 3.0e-6,
                "boundary_spectrum_l1": 2.0e-6,
                "boundary_bolometric_fraction": 8.0e-7,
                "contraction_ratio": None if index == 0 else 0.99,
                "frequency_ownership_count": 9632,
                "frequency_ownership_exact": True,
                "minimum_input_intensity": 0.0,
                "minimum_mapped_intensity": 0.0,
                "maximum_process_peak_rss_mib": 2800.0,
                "maximum_worker_wall_runtime_s": 50.0 if index == 18 else 13.0,
                "full_map_wall_runtime_s": 1211.0 if index == 18 else 240.0,
                "gate_checks": checks,
                "map_passed": index < 18,
                "reports": [],
            }
        )
    return records


def _fixture(root: Path) -> adjusted.ResourceAdjustedPicardProtocolSpec:
    worker_paths = {
        "finite_trial_protocol": "outputs/finite_protocol.json",
        "finite_trial_material": "outputs/finite_material.npz",
        "phase7b5p_master_input": "outputs/master.npz",
        "generic_positive_picard_runner": "scripts/generic.py",
        "positive_sequence_engine": "scripts/engine.py",
        "phase7b7i_worker": "scripts/worker.py",
        "phase7b9d_worker_helpers": "scripts/helpers.py",
        "mixed_frame_operator": "src/operator.py",
        "mixed_frame_frequency": "src/frequency.py",
    }
    for index, relative in enumerate(worker_paths.values()):
        _write(root, relative, f"worker-{index}".encode())
    _write(root, adjusted.RUNNER_RELATIVE_PATH, b"resource-runner")
    source_protocol_path = "outputs/cq_protocol.json"
    source_protocol = {
        "phase": "7B9cq source",
        "sources": {
            name: _source(root, relative) for name, relative in worker_paths.items()
        },
        "configuration": {
            "phase_index": 1418,
            "physical_frequency_groups": 9632,
            "angular_direction_count": 32,
            "radiation_depth_cell_count": 4096,
            "natural_frequency_block_count": 76,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": 24,
            "maximum_concurrent_processes": 2,
            "stop_after_iteration": 23,
            "raw_float64_checkpoint_size_bytes": 128,
            **common.numerical_repair_prohibitions(sequence=True),
        },
        "gates": common.seeded_two_map_gates(),
        "authorization": {
            "resume_original_total_map_horizon": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
        },
    }
    _write_json(root, source_protocol_path, source_protocol)
    source_manifest_path = "outputs/cq_manifest.json"
    records = _records()
    _write_json(
        root,
        source_manifest_path,
        {
            "phase": source_protocol["phase"],
            "protocol_sha256": common.sha256(root / source_protocol_path),
            "status": "gate_failed",
            "current_input_path": records[-1]["input_state_path"],
            "current_input_sha256": records[-1]["input_state_sha256"],
            "next_output_path": records[-1]["mapped_state_path"],
            "iterations": records,
            "active_iteration": None,
        },
    )
    return adjusted.ResourceAdjustedPicardProtocolSpec(
        phase="7B9 resource-adjusted test",
        phase_index=1419,
        classification="[A-preregistered]+[V]+[O]",
        source_protocol_path=source_protocol_path,
        source_manifest_path=source_manifest_path,
        runner_path=adjusted.RUNNER_RELATIVE_PATH,
        manifest_path="outputs/new_manifest.json",
        report_directory="outputs/new_reports",
        summary_path="outputs/new_summary.json",
        figure_path="outputs/new_figure.png",
    )


def _freeze(root: Path, spec: adjusted.ResourceAdjustedPicardProtocolSpec) -> tuple[Path, str]:
    protocol = adjusted.build_resource_adjusted_picard_protocol(root, spec)
    path = root / "outputs/new_protocol.json"
    _write_json(root, "outputs/new_protocol.json", protocol)
    return path, common.sha256(path)


def test_builder_uses_fixed_concurrency_scaled_wall_gate_without_states(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    protocol = adjusted.build_resource_adjusted_picard_protocol(tmp_path, spec)
    cfg = protocol["configuration"]
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert protocol["reference"]["observed_last_map_wall_runtime_s"] == 1211.0
    assert protocol["reference"]["adjusted_full_map_wall_gate_s"] == 1800.0
    assert protocol["resource_gate_adjustment"] == {
        "classification": "[A-resource]",
        "scaling_definition": "1200 * (3 / 2)",
        "threshold_from_observed_runtime": False,
        "scientific_gate_changed": False,
        "numerical_repair_added": False,
    }
    assert cfg["maximum_concurrent_processes"] == 2
    assert cfg["maximum_picard_maps"] == 24
    assert cfg["initial_state_path"].endswith("state_19.dat")
    assert cfg["scratch_state_path"].endswith("state_18.dat")
    assert all(not source["path"].endswith(".dat") for source in protocol["sources"].values())
    assert all("immutable" not in source["path"] for source in protocol["sources"].values())
    unchanged = common.seeded_two_map_gates()
    unchanged["each_full_map_wall_time_strictly_below_s"] = 1800.0
    assert protocol["gates"] == unchanged


def test_seed_reclassifies_only_last_resource_gate_and_preserves_source(
    tmp_path: Path,
) -> None:
    spec = _fixture(tmp_path)
    source_manifest = tmp_path / spec.source_manifest_path
    original_bytes = source_manifest.read_bytes()
    protocol_path, digest = _freeze(tmp_path, spec)
    manifest = adjusted.seed_manifest(protocol_path, digest, root=tmp_path)
    assert source_manifest.read_bytes() == original_bytes
    assert len(manifest["iterations"]) == 19
    assert all(row["map_passed"] for row in manifest["iterations"])
    last = manifest["iterations"][-1]
    assert last["original_map_passed"] is False
    assert last["original_gate_checks"]["resources_pass"] is False
    assert last["resource_reclassified"] is True
    assert last["gate_checks"]["resources_pass"] is True
    assert last["map_passed"] is True
    assert manifest["current_input_path"] == last["mapped_state_path"]
    assert manifest["next_output_path"] == last["input_state_path"]
    assert manifest["resource_reclassification_audit"][
        "threshold_from_observed_runtime"
    ] is False


@pytest.mark.parametrize(
    "failure",
    (
        "status",
        "record_count",
        "early_failure",
        "physics_failure",
        "rss_failure",
        "worker_failure",
        "new_wall_failure",
        "chain_failure",
        "science_gate_change",
    ),
)
def test_builder_rejects_non_resource_only_source(tmp_path: Path, failure: str) -> None:
    root = tmp_path / failure
    spec = _fixture(root)
    protocol_path = root / spec.source_protocol_path
    manifest_path = root / spec.source_manifest_path
    protocol = json.loads(protocol_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if failure == "status":
        manifest["status"] = "running"
    elif failure == "record_count":
        manifest["iterations"].pop()
    elif failure == "early_failure":
        manifest["iterations"][4]["map_passed"] = False
    elif failure == "physics_failure":
        manifest["iterations"][-1]["gate_checks"]["boundary_pass"] = False
    elif failure == "rss_failure":
        manifest["iterations"][-1]["maximum_process_peak_rss_mib"] = 6144.0
    elif failure == "worker_failure":
        manifest["iterations"][-1]["maximum_worker_wall_runtime_s"] = 60.0
    elif failure == "new_wall_failure":
        manifest["iterations"][-1]["full_map_wall_runtime_s"] = 1800.0
    elif failure == "chain_failure":
        manifest["iterations"][8]["input_state_sha256"] = "broken"
    else:
        protocol["gates"]["global_boundary_spectrum_l1_below"] = 2.0e-3
        _write_json(root, spec.source_protocol_path, protocol)
        manifest["protocol_sha256"] = common.sha256(root / spec.source_protocol_path)
    _write_json(root, spec.source_manifest_path, manifest)
    with pytest.raises(RuntimeError):
        adjusted.build_resource_adjusted_picard_protocol(root, spec)


def test_runner_rejects_state_sources_and_source_manifest_target(tmp_path: Path) -> None:
    spec = _fixture(tmp_path)
    protocol_path, digest = _freeze(tmp_path, spec)
    protocol = json.loads(protocol_path.read_text())
    protocol["sources"]["forbidden_state"] = {
        "path": "outputs/checkpoints/state.dat",
        "size_bytes": 0,
        "sha256": "0" * 64,
    }
    _write_json(tmp_path, "outputs/new_protocol.json", protocol)
    with pytest.raises(RuntimeError):
        adjusted.seed_manifest(
            protocol_path,
            common.sha256(protocol_path),
            root=tmp_path,
        )

    spec = _fixture(tmp_path / "overwrite")
    spec = adjusted.ResourceAdjustedPicardProtocolSpec(
        **{**spec.__dict__, "manifest_path": spec.source_manifest_path}
    )
    protocol_path, digest = _freeze(tmp_path / "overwrite", spec)
    with pytest.raises(RuntimeError):
        adjusted.seed_manifest(protocol_path, digest, root=tmp_path / "overwrite")
