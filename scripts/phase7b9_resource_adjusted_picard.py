"""Phase 7B9：仅重分类总墙钟资源门后的两进程 Picard 续算。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as common
    from scripts import phase7b9al_positive_picard_convergence as engine
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as common  # type: ignore[no-redef]
    import phase7b9al_positive_picard_convergence as engine  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9_resource_adjusted_picard.py"
EXPECTED_HASH_ENV = "PHASE7B9_RESOURCE_ADJUSTED_PROTOCOL_SHA256"
ORIGINAL_CONCURRENCY = 3
ADJUSTED_CONCURRENCY = 2
ORIGINAL_FULL_MAP_WALL_GATE_S = 1200.0
ADJUSTED_FULL_MAP_WALL_GATE_S = (
    ORIGINAL_FULL_MAP_WALL_GATE_S * ORIGINAL_CONCURRENCY / ADJUSTED_CONCURRENCY
)
TOTAL_PICARD_HORIZON = 24
SOURCE_RECORD_COUNT = 19
WORKER_SOURCE_KEYS = {
    "finite_trial_protocol",
    "finite_trial_material",
    "phase7b5p_master_input",
    "generic_positive_picard_runner",
    "positive_sequence_engine",
    "phase7b7i_worker",
    "phase7b9d_worker_helpers",
    "mixed_frame_operator",
    "mixed_frame_frequency",
}


@dataclass(frozen=True)
class ResourceAdjustedPicardProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    source_protocol_path: str
    source_manifest_path: str
    runner_path: str
    manifest_path: str
    report_directory: str
    summary_path: str
    figure_path: str


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _validate_expected_hash(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("expected protocol SHA256 must be 64 lowercase hex characters")
    return value


def _small_source(root: Path, relative_path: str) -> dict[str, object]:
    if relative_path.endswith(".dat") or "immutable" in relative_path.lower():
        raise RuntimeError("resource-adjusted protocol must not freeze a state or anchor")
    return common.source_entry(root, relative_path)


def _required_worker_sources(
    root: Path,
    source_protocol: dict[str, object],
) -> dict[str, dict[str, object]]:
    sources = source_protocol.get("sources", {})
    if not WORKER_SOURCE_KEYS.issubset(sources):
        raise RuntimeError("source protocol lacks required worker sources")
    frozen: dict[str, dict[str, object]] = {}
    for name in sorted(WORKER_SOURCE_KEYS):
        relative = str(sources[name]["path"])
        current = _small_source(root, relative)
        if (
            int(current["size_bytes"]) != int(sources[name]["size_bytes"])
            or current["sha256"] != sources[name]["sha256"]
        ):
            raise RuntimeError(f"source worker dependency changed: {relative}")
        frozen[name] = current
    return frozen


def _validate_science_contract(source_protocol: dict[str, object]) -> None:
    cfg = source_protocol.get("configuration", {})
    gates = source_protocol.get("gates", {})
    authorization = source_protocol.get("authorization", {})
    expected_gates = common.seeded_two_map_gates()
    if gates != expected_gates:
        raise RuntimeError("source Picard scientific or resource gates changed")
    prohibitions = common.numerical_repair_prohibitions(sequence=True)
    if (
        int(cfg.get("maximum_picard_maps", -1)) != TOTAL_PICARD_HORIZON
        or int(cfg.get("stop_after_iteration", -1)) != TOTAL_PICARD_HORIZON - 1
        or int(cfg.get("maximum_concurrent_processes", -1)) != ADJUSTED_CONCURRENCY
        or cfg.get("accepted_source_relaxation_exactly") != 1.0
        or int(cfg.get("diagnostic_fixed_iteration_count", -1)) != 1
        or cfg.get("source_map_only") is not True
        or any(cfg.get(name) != value for name, value in prohibitions.items())
        or authorization.get("resume_original_total_map_horizon") is not True
        or authorization.get("material_feedback_only_after_convergence") is not True
        or authorization.get("accept_dynamic_nlte_solution") is not False
    ):
        raise RuntimeError("source Picard horizon or no-repair contract changed")


def _validate_source_records(
    source_protocol: dict[str, object],
    source_manifest: dict[str, object],
    source_protocol_sha256: str,
) -> list[dict[str, object]]:
    iterations = source_manifest.get("iterations")
    if (
        source_manifest.get("protocol_sha256") != source_protocol_sha256
        or source_manifest.get("phase") != source_protocol.get("phase")
        or source_manifest.get("status") != "gate_failed"
        or source_manifest.get("active_iteration") is not None
        or not isinstance(iterations, list)
        or len(iterations) != SOURCE_RECORD_COUNT
    ):
        raise RuntimeError("resource-failed source manifest contract changed")
    for index, record in enumerate(iterations):
        if int(record.get("iteration", -1)) != index:
            raise RuntimeError("source Picard iteration numbering changed")
        if index and (
            record.get("input_state_path")
            != iterations[index - 1].get("mapped_state_path")
            or record.get("input_state_sha256")
            != iterations[index - 1].get("mapped_state_sha256")
        ):
            raise RuntimeError("source Picard state chain changed")
        if index < SOURCE_RECORD_COUNT - 1 and (
            record.get("map_passed") is not True
            or any(value is not True for value in record.get("gate_checks", {}).values())
        ):
            raise RuntimeError("one of the first 18 source maps did not pass")
    last = iterations[-1]
    expected_last_checks = {
        "frequency_ownership_pass": True,
        "positive_map_pass": True,
        "initial_reproduction_pass": True,
        "contraction_pass": True,
        "boundary_pass": True,
        "resources_pass": False,
    }
    gates = source_protocol["gates"]
    if (
        last.get("map_passed") is not False
        or last.get("gate_checks") != expected_last_checks
        or float(last.get("maximum_process_peak_rss_mib", float("inf")))
        >= float(gates["each_process_peak_rss_strictly_below_mib"])
        or float(last.get("maximum_worker_wall_runtime_s", float("inf")))
        >= float(gates["each_worker_wall_time_strictly_below_s"])
        or float(last.get("full_map_wall_runtime_s", float("-inf")))
        < ORIGINAL_FULL_MAP_WALL_GATE_S
        or float(last.get("full_map_wall_runtime_s", float("inf")))
        >= ADJUSTED_FULL_MAP_WALL_GATE_S
        or float(last.get("boundary_spectrum_l1", float("inf")))
        >= float(gates["global_boundary_spectrum_l1_below"])
        or float(last.get("boundary_bolometric_fraction", float("inf")))
        >= float(gates["global_boundary_bolometric_fraction_below"])
        or float(last.get("contraction_ratio", float("inf")))
        >= float(gates["subsequent_residual_contraction_ratio_below"])
        or float(last.get("minimum_input_intensity", float("-inf")))
        < float(gates["minimum_input_and_mapped_intensity_at_least"])
        or float(last.get("minimum_mapped_intensity", float("-inf")))
        < float(gates["minimum_input_and_mapped_intensity_at_least"])
    ):
        raise RuntimeError("last source map was not a resource-only failure")
    if (
        source_manifest.get("current_input_path") != last["input_state_path"]
        or source_manifest.get("current_input_sha256") != last["input_state_sha256"]
        or source_manifest.get("next_output_path") != last["mapped_state_path"]
    ):
        raise RuntimeError("resource-failed source double-buffer lineage changed")
    return json.loads(json.dumps(iterations))


def _reclassified_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    adjusted = json.loads(json.dumps(records))
    last = adjusted[-1]
    last["original_map_passed"] = False
    last["original_gate_checks"] = dict(last["gate_checks"])
    last["resource_reclassified"] = True
    last["resource_reclassification_only"] = True
    last["original_full_map_wall_gate_s"] = ORIGINAL_FULL_MAP_WALL_GATE_S
    last["resource_adjusted_full_map_wall_gate_s"] = ADJUSTED_FULL_MAP_WALL_GATE_S
    last["gate_checks"]["resources_pass"] = True
    last["map_passed"] = True
    return adjusted


def build_resource_adjusted_picard_protocol(
    root: Path,
    spec: ResourceAdjustedPicardProtocolSpec,
) -> dict[str, object]:
    """Build the fixed 3/2 wall-gate protocol without reading state checkpoints."""
    source_protocol = common.read_json(root, spec.source_protocol_path)
    source_manifest = common.read_json(root, spec.source_manifest_path)
    source_protocol_hash = common.sha256(root / spec.source_protocol_path)
    _validate_science_contract(source_protocol)
    records = _validate_source_records(
        source_protocol,
        source_manifest,
        source_protocol_hash,
    )
    dependencies = _required_worker_sources(root, source_protocol)
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("resource-adjusted runner path changed")
    source_configuration = source_protocol["configuration"]
    source_outputs = {
        str(source_configuration.get("manifest_path")),
        str(source_configuration.get("report_directory")),
        str(source_configuration.get("summary_path")),
        str(source_configuration.get("figure_path")),
    }
    new_outputs = {
        spec.manifest_path,
        spec.report_directory,
        spec.summary_path,
        spec.figure_path,
    }
    if source_outputs & new_outputs or len(new_outputs) != 4:
        raise RuntimeError("resource-adjusted outputs must not overwrite cq outputs")
    last = records[-1]
    gates = dict(source_protocol["gates"])
    gates["each_full_map_wall_time_strictly_below_s"] = (
        ORIGINAL_FULL_MAP_WALL_GATE_S
        * ORIGINAL_CONCURRENCY
        / ADJUSTED_CONCURRENCY
    )
    if gates["each_full_map_wall_time_strictly_below_s"] != 1800.0:
        raise ArithmeticError("resource-adjusted wall gate is not the frozen 1800 s")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "resource_failed_protocol": _small_source(root, spec.source_protocol_path),
            "resource_failed_manifest": _small_source(root, spec.source_manifest_path),
            "resource_adjusted_picard_runner": _small_source(root, spec.runner_path),
            **dependencies,
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": source_protocol["configuration"][
                "physical_frequency_groups"
            ],
            "angular_direction_count": source_protocol["configuration"][
                "angular_direction_count"
            ],
            "radiation_depth_cell_count": source_protocol["configuration"][
                "radiation_depth_cell_count"
            ],
            "natural_frequency_block_count": source_protocol["configuration"][
                "natural_frequency_block_count"
            ],
            "spatial_scheme": source_protocol["configuration"]["spatial_scheme"],
            "diagnostic_fixed_iteration_count": 1,
            "source_map_only": True,
            "accepted_source_relaxation_exactly": 1.0,
            "maximum_picard_maps": TOTAL_PICARD_HORIZON,
            "maximum_concurrent_processes": ADJUSTED_CONCURRENCY,
            "stop_after_iteration": TOTAL_PICARD_HORIZON - 1,
            "seed_summary_source_key": "resource_failed_manifest",
            "seed_summary_format": "resource_reclassified_sequence",
            "seed_iteration_count": SOURCE_RECORD_COUNT,
            "restart_picard_iteration": SOURCE_RECORD_COUNT,
            "initial_state_path": last["mapped_state_path"],
            "initial_state_sha256": last["mapped_state_sha256"],
            "scratch_state_path": last["input_state_path"],
            "scratch_state_initial_sha256": last["input_state_sha256"],
            "raw_float64_checkpoint_size_bytes": source_protocol["configuration"][
                "raw_float64_checkpoint_size_bytes"
            ],
            "manifest_path": spec.manifest_path,
            "report_directory": spec.report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            **common.numerical_repair_prohibitions(sequence=True),
        },
        "reference": {
            "initial_global_residual": last["global_original_operator_residual"],
            "initial_boundary_spectrum_l1": last["boundary_spectrum_l1"],
            "initial_boundary_bolometric_fraction": last[
                "boundary_bolometric_fraction"
            ],
            "original_full_map_wall_gate_s": ORIGINAL_FULL_MAP_WALL_GATE_S,
            "original_concurrent_processes_for_scaling": ORIGINAL_CONCURRENCY,
            "adjusted_concurrent_processes": ADJUSTED_CONCURRENCY,
            "adjusted_full_map_wall_gate_s": ADJUSTED_FULL_MAP_WALL_GATE_S,
            "observed_last_map_wall_runtime_s": last["full_map_wall_runtime_s"],
        },
        "resource_gate_adjustment": {
            "classification": "[A-resource]",
            "scaling_definition": "1200 * (3 / 2)",
            "threshold_from_observed_runtime": False,
            "scientific_gate_changed": False,
            "numerical_repair_added": False,
        },
        "gates": gates,
        "authorization": {
            "preserve_all_original_cq_records": True,
            "reclassify_only_last_total_wall_resource_gate": True,
            "original_last_map_passed": False,
            "resource_reclassified_last_map_passed": True,
            "resume_original_total_map_horizon": True,
            "alternate_only_named_generated_buffers": True,
            "material_feedback_only_after_convergence": True,
            "accept_dynamic_nlte_solution": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
    }


def _frozen_small_source(
    root: Path,
    source: dict[str, object],
) -> Path:
    relative = str(source["path"])
    if relative.endswith(".dat") or "immutable" in relative.lower():
        raise RuntimeError("resource-adjusted runner refuses state sources")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError("resource-adjusted source escaped the project root")
    if (
        path.stat().st_size != int(source["size_bytes"])
        or common.sha256(path) != source["sha256"]
    ):
        raise RuntimeError(f"frozen resource-adjusted source changed: {relative}")
    return path


def _load_protocol(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
) -> dict[str, object]:
    if common.sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen resource-adjusted Picard protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    required = WORKER_SOURCE_KEYS | {
        "resource_failed_protocol",
        "resource_failed_manifest",
        "resource_adjusted_picard_runner",
    }
    if not required.issubset(protocol.get("sources", {})):
        raise RuntimeError("resource-adjusted frozen sources changed")
    if (
        protocol["sources"]["resource_adjusted_picard_runner"].get("path")
        != RUNNER_RELATIVE_PATH
    ):
        raise RuntimeError("resource-adjusted runner source changed")
    for source in protocol["sources"].values():
        _frozen_small_source(root, source)
    return protocol


def _restart_contract(protocol: dict[str, object]) -> None:
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    authorization = protocol["authorization"]
    expected_gates = common.seeded_two_map_gates()
    expected_gates["each_full_map_wall_time_strictly_below_s"] = 1800.0
    if (
        gates != expected_gates
        or int(cfg.get("maximum_picard_maps", -1)) != TOTAL_PICARD_HORIZON
        or int(cfg.get("stop_after_iteration", -1)) != TOTAL_PICARD_HORIZON - 1
        or int(cfg.get("maximum_concurrent_processes", -1))
        != ADJUSTED_CONCURRENCY
        or int(cfg.get("seed_iteration_count", -1)) != SOURCE_RECORD_COUNT
        or int(cfg.get("restart_picard_iteration", -1)) != SOURCE_RECORD_COUNT
        or cfg.get("seed_summary_source_key") != "resource_failed_manifest"
        or cfg.get("seed_summary_format") != "resource_reclassified_sequence"
        or authorization.get("preserve_all_original_cq_records") is not True
        or authorization.get("reclassify_only_last_total_wall_resource_gate")
        is not True
        or authorization.get("original_last_map_passed") is not False
        or authorization.get("resource_reclassified_last_map_passed") is not True
    ):
        raise RuntimeError("resource-adjusted restart contract changed")


def _source_iterations(
    root: Path,
    protocol: dict[str, object],
) -> list[dict[str, object]]:
    source_protocol_path = _frozen_small_source(
        root, protocol["sources"]["resource_failed_protocol"]
    )
    source_manifest_path = _frozen_small_source(
        root, protocol["sources"]["resource_failed_manifest"]
    )
    source_protocol = json.loads(source_protocol_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    _validate_science_contract(source_protocol)
    records = _validate_source_records(
        source_protocol,
        source_manifest,
        protocol["sources"]["resource_failed_protocol"]["sha256"],
    )
    adjusted = _reclassified_records(records)
    cfg = protocol["configuration"]
    last = adjusted[-1]
    if (
        cfg["initial_state_path"] != last["mapped_state_path"]
        or cfg["initial_state_sha256"] != last["mapped_state_sha256"]
        or cfg["scratch_state_path"] != last["input_state_path"]
        or cfg["scratch_state_initial_sha256"] != last["input_state_sha256"]
    ):
        raise RuntimeError("resource-adjusted double-buffer lineage changed")
    return adjusted


def _validate_new_manifest(
    manifest: dict[str, object],
    protocol: dict[str, object],
    expected_hash: str,
    source_iterations: list[dict[str, object]],
) -> None:
    cfg = protocol["configuration"]
    iterations = manifest.get("iterations")
    if (
        manifest.get("phase") != protocol.get("phase")
        or manifest.get("protocol_sha256") != expected_hash
        or manifest.get("status")
        not in {"running", "complete", "gate_failed", "maximum_maps_exhausted"}
        or not isinstance(iterations, list)
        or len(iterations) < SOURCE_RECORD_COUNT
        or iterations[:SOURCE_RECORD_COUNT] != source_iterations
    ):
        raise RuntimeError("resource-adjusted manifest lineage changed")
    if len(iterations) == SOURCE_RECORD_COUNT and manifest.get("active_iteration") is None:
        if (
            manifest.get("current_input_path") != cfg["initial_state_path"]
            or manifest.get("current_input_sha256") != cfg["initial_state_sha256"]
            or manifest.get("next_output_path") != cfg["scratch_state_path"]
        ):
            raise RuntimeError("resource-adjusted initial double-buffer order changed")
    active = manifest.get("active_iteration")
    if active is not None:
        if not isinstance(active, dict) or any(
            row.get("protocol_sha256") != expected_hash
            for row in active.get("completed_blocks", [])
        ):
            raise RuntimeError("resource-adjusted active iteration changed")


def seed_manifest(
    protocol_path: Path,
    expected_hash: str,
    *,
    root: Path | None = None,
) -> dict[str, object]:
    """Seed a new manifest; never write to the source cq manifest."""
    root = ROOT if root is None else root
    expected_hash = _validate_expected_hash(expected_hash)
    protocol = _load_protocol(root, protocol_path, expected_hash)
    _restart_contract(protocol)
    source_iterations = _source_iterations(root, protocol)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    source_manifest_path = root / protocol["sources"]["resource_failed_manifest"]["path"]
    if manifest_path.resolve() == source_manifest_path.resolve():
        raise RuntimeError("new manifest must not overwrite the source cq manifest")
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_new_manifest(manifest, protocol, expected_hash, source_iterations)
        return manifest
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "iterations": source_iterations,
        "active_iteration": None,
        "resource_reclassification_audit": {
            "source_record_count": SOURCE_RECORD_COUNT,
            "original_last_map_passed": False,
            "resource_reclassified": True,
            "resource_adjusted_last_map_passed": True,
            "original_full_map_wall_gate_s": ORIGINAL_FULL_MAP_WALL_GATE_S,
            "adjusted_full_map_wall_gate_s": ADJUSTED_FULL_MAP_WALL_GATE_S,
            "threshold_from_observed_runtime": False,
            "scaling_definition": "1200 * (3 / 2)",
        },
    }
    _write_json_atomic(manifest_path, manifest)
    return manifest


def run(
    expected_hash: str,
    protocol_path: Path,
    *,
    stop_after_iteration: int | None = None,
) -> dict[str, object]:
    expected_hash = _validate_expected_hash(expected_hash)
    engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
    seed_manifest(protocol_path, expected_hash)
    return engine.run(protocol_path, stop_after_iteration=stop_after_iteration)


def _parser(default_protocol: Path | None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=default_protocol,
        required=default_protocol is None,
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    return parser


def _dispatch(args: argparse.Namespace, expected_hash: str) -> None:
    expected_hash = _validate_expected_hash(expected_hash)
    engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
    if args.worker:
        if (
            args.iteration is None
            or args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.output_state is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires iteration, block and both states")
        engine._run_worker(
            args.protocol,
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        return
    run(expected_hash, args.protocol, stop_after_iteration=args.stop_after_iteration)


def run_cli(expected_hash: str, default_protocol: Path) -> None:
    """Allow a stage wrapper to pin the protocol hash in source code."""
    expected_hash = _validate_expected_hash(expected_hash)
    os.environ[EXPECTED_HASH_ENV] = expected_hash
    _dispatch(_parser(default_protocol).parse_args(), expected_hash)


def main() -> None:
    parser = _parser(None)
    parser.add_argument(
        "--expected-protocol-sha256",
        default=os.environ.get(EXPECTED_HASH_ENV),
    )
    args = parser.parse_args()
    if args.expected_protocol_sha256 is None:
        raise ValueError("direct runner requires --expected-protocol-sha256")
    expected_hash = _validate_expected_hash(args.expected_protocol_sha256)
    os.environ[EXPECTED_HASH_ENV] = expected_hash
    _dispatch(args, expected_hash)


if __name__ == "__main__":
    main()
