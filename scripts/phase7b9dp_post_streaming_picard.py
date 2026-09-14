"""Phase 7B9dp：streaming 周期后的双缓冲 pure-Picard 续算。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
from typing import Callable

try:
    from scripts import phase7b9_half_trial_positive_sequence_engine as engine
    from scripts import phase7b9_half_trial_radiation_continuation as storage
    from scripts import phase7b9di_progression_continuation as progression
    from scripts import phase7b9dn_repeat_streaming_anderson as repeat
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_half_trial_positive_sequence_engine as engine  # type: ignore[no-redef]
    import phase7b9_half_trial_radiation_continuation as storage  # type: ignore[no-redef]
    import phase7b9di_progression_continuation as progression  # type: ignore[no-redef]
    import phase7b9dn_repeat_streaming_anderson as repeat  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
RUNNER_RELATIVE_PATH = "scripts/phase7b9dp_post_streaming_picard.py"
PREREGISTER_RELATIVE_PATH = "scripts/phase7b9dp_preregister_post_streaming_picard.py"
MAXIMUM_ADDITIONAL_PICARD_MAPS = 40
SEED_COMPLETED_MAPS = 1
MAXIMUM_TOTAL_PICARD_MAPS = SEED_COMPLETED_MAPS + MAXIMUM_ADDITIONAL_PICARD_MAPS


@dataclass(frozen=True)
class PostStreamingPicardSpec:
    phase: str
    phase_index: int
    classification: str
    prior_protocol_path: str
    prior_pass1_manifest_path: str
    prior_pass2_manifest_path: str
    prior_candidate_commit_manifest_path: str
    prior_fresh_manifest_path: str
    prior_fresh_summary_path: str
    runner_path: str
    manifest_path: str
    transient_report_directory: str
    summary_path: str
    figure_path: str


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _small_source(root: Path, relative: str) -> dict[str, object]:
    logical = PurePosixPath(relative)
    path = root / relative
    if logical.is_absolute() or ".." in logical.parts:
        raise RuntimeError("post-streaming source escaped the repository")
    if path.suffix.lower() == ".dat":
        raise RuntimeError("post-streaming builder refuses any .dat source")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _repeat_validation_spec(spec: PostStreamingPicardSpec) -> repeat.RepeatStreamingCycleSpec:
    return repeat.RepeatStreamingCycleSpec(
        phase="validation only",
        phase_index=spec.phase_index,
        classification="validation only",
        prior_protocol_path=spec.prior_protocol_path,
        prior_pass1_manifest_path=spec.prior_pass1_manifest_path,
        prior_pass2_manifest_path=spec.prior_pass2_manifest_path,
        prior_candidate_commit_manifest_path=spec.prior_candidate_commit_manifest_path,
        prior_fresh_manifest_path=spec.prior_fresh_manifest_path,
        prior_fresh_summary_path=spec.prior_fresh_summary_path,
        coefficient_report_directory="outputs/checkpoints/validation_unused",
        evaluation_report_directory="outputs/checkpoints/validation_unused",
        coefficient_manifest_path="outputs/checkpoints/validation_unused.json",
        evaluation_manifest_path="outputs/checkpoints/validation_unused.json",
        candidate_summary_path="outputs/validation_unused.json",
        candidate_figure_path="outputs/validation_unused.png",
    )


def _validate_completed_cycle(
    root: Path, spec: PostStreamingPicardSpec
) -> tuple[
    dict[str, object],
    str,
    dict[str, object],
    dict[str, object],
]:
    validation = _repeat_validation_spec(spec)
    prior, protocol_hash = repeat._validate_prior_protocol(root, validation)
    first, second = repeat._validate_dry_manifests(
        root, prior, protocol_hash, validation
    )
    commit = repeat._validate_commit(
        root, prior, protocol_hash, first, second, validation
    )
    fresh, summary = repeat._validate_fresh(
        root, prior, protocol_hash, commit, second, validation
    )
    return prior, protocol_hash, fresh, summary


def _seed_record(
    gates: dict[str, object],
    fresh: dict[str, object],
    summary: dict[str, object],
) -> dict[str, object]:
    reports = fresh["completed_blocks"]
    metrics = {
        "block_report_count": len(reports),
        "frequency_ownership_count": 9632,
        "frequency_ownership_exact": True,
        "global_original_operator_residual": summary[
            "fresh_input_global_original_operator_residual"
        ],
        "boundary_spectrum_l1": summary["fresh_input_boundary_spectrum_l1"],
        "boundary_bolometric_fraction": summary[
            "fresh_input_boundary_bolometric_fraction"
        ],
        "minimum_input_intensity": min(
            float(row["minimum_input_intensity"]) for row in reports
        ),
        "minimum_mapped_intensity": min(
            float(row["minimum_mapped_intensity"]) for row in reports
        ),
        "maximum_process_peak_rss_mib": summary[
            "maximum_process_peak_rss_mib"
        ],
        "maximum_worker_wall_runtime_s": summary[
            "maximum_worker_wall_runtime_s"
        ],
        "full_map_wall_runtime_s": summary["full_map_wall_runtime_s"],
    }
    progression_checks = {
        "frequency_ownership_pass": True,
        "positive_map_pass": True,
        # 中文：seed 已由完整 fresh map 审计，没有前一 pure-Picard 残差可作收缩比。
        "contraction_pass": True,
        "resources_pass": True,
    }
    convergence_checks = progression._convergence_checks(gates, metrics)
    convergence_passed = all(convergence_checks.values())
    boundary_passed = bool(
        convergence_checks["boundary_spectrum_pass"]
        and convergence_checks["boundary_bolometric_pass"]
    )
    return {
        "iteration": 0,
        "input_state_path": summary["candidate_state_path"],
        "input_state_sha256": summary["candidate_state_sha256"],
        "mapped_state_path": summary["mapped_state_path"],
        "mapped_state_sha256": summary["mapped_state_sha256"],
        **metrics,
        "contraction_ratio": None,
        "contraction_applicable": False,
        "initial_reproduction_applicable": False,
        "gate_checks": {
            "frequency_ownership_pass": True,
            "positive_map_pass": True,
            "initial_reproduction_pass": True,
            "contraction_pass": True,
            "boundary_pass": boundary_passed,
            "resources_pass": True,
        },
        "original_map_passed": boundary_passed,
        "progression_gate_checks": progression_checks,
        "progression_passed": True,
        "convergence_gate_checks": convergence_checks,
        "convergence_passed": convergence_passed,
        "map_passed": convergence_passed,
        "seed_classification": "accepted_prior_streaming_fresh_map",
        "block_report_audit": {
            "record_count": 76,
            "block_indices": list(range(76)),
            "full_reports_retained_in_prior_streaming_cycle": True,
        },
    }


def build_post_streaming_picard_protocol(
    root: Path, spec: PostStreamingPicardSpec
) -> dict[str, object]:
    """Freeze a 40-map pure-Picard tail without opening either full state."""
    artifacts = (
        spec.prior_protocol_path,
        spec.prior_pass1_manifest_path,
        spec.prior_pass2_manifest_path,
        spec.prior_candidate_commit_manifest_path,
        spec.prior_fresh_manifest_path,
        spec.prior_fresh_summary_path,
    )
    if any(Path(relative).suffix.lower() != ".json" for relative in artifacts):
        raise RuntimeError("post-streaming builder accepts only prior JSON artifacts")
    if spec.runner_path != RUNNER_RELATIVE_PATH:
        raise RuntimeError("post-streaming runner path changed")
    transient = PurePosixPath(spec.transient_report_directory)
    if (
        transient.is_absolute()
        or ".." in transient.parts
        or transient.parts[:2] != ("outputs", "checkpoints")
        or "transient" not in transient.name
    ):
        raise RuntimeError("post-streaming transient directory is not stage-owned")
    prior, prior_hash, fresh, summary = _validate_completed_cycle(root, spec)
    if "finite_trial_protocol" not in prior["sources"] or "finite_trial_material" not in prior["sources"]:
        raise RuntimeError("post-streaming fixed-material sources are missing")
    fixed = _read(root, str(prior["sources"]["finite_trial_protocol"]["path"]))
    if fixed.get("sources", {}).get("current_material_state") != prior["sources"][
        "finite_trial_material"
    ]:
        raise RuntimeError("post-streaming fixed material changed")
    gates = storage.common.memory_safe_seeded_two_map_gates()
    if (
        gates["global_original_operator_residual_below"] != 1.0e-4
        or gates["global_boundary_spectrum_l1_below"] != 1.0e-3
        or gates["global_boundary_bolometric_fraction_below"] != 1.0e-3
        or gates["subsequent_residual_contraction_ratio_below"] != 1.01
        or gates["each_full_map_wall_time_strictly_below_s"] != 1800.0
    ):
        raise RuntimeError("post-streaming Picard gates changed")
    seed = _seed_record(gates, fresh, summary)
    direct = {
        "post_streaming_prior_protocol": _small_source(root, spec.prior_protocol_path),
        "post_streaming_prior_pass1_manifest": _small_source(
            root, spec.prior_pass1_manifest_path
        ),
        "post_streaming_prior_pass2_manifest": _small_source(
            root, spec.prior_pass2_manifest_path
        ),
        "post_streaming_prior_candidate_commit_manifest": _small_source(
            root, spec.prior_candidate_commit_manifest_path
        ),
        "post_streaming_prior_fresh_manifest": _small_source(
            root, spec.prior_fresh_manifest_path
        ),
        "post_streaming_prior_fresh_summary": _small_source(
            root, spec.prior_fresh_summary_path
        ),
        "post_streaming_picard_runner": _small_source(root, spec.runner_path),
        "post_streaming_picard_preregister": _small_source(
            root, PREREGISTER_RELATIVE_PATH
        ),
        "post_streaming_sequence_engine": _small_source(
            root, storage.SEQUENCE_ENGINE_RELATIVE_PATH
        ),
        "post_streaming_storage_helper": _small_source(
            root, storage.RUNNER_RELATIVE_PATH
        ),
        "post_streaming_progression_gate_helper": _small_source(
            root, progression.RUNNER_RELATIVE_PATH
        ),
        "post_streaming_cycle_validator": _small_source(
            root, repeat.BUILDER_RELATIVE_PATH
        ),
        "post_streaming_map_worker": _small_source(root, storage.common.MAP_WORKER),
        "post_streaming_worker_helpers": _small_source(
            root, storage.common.WORKER_HELPERS
        ),
        "post_streaming_generic_map_runner": _small_source(
            root, storage.common.GENERIC_MAP_RUNNER
        ),
    }
    collisions = set(direct).intersection(prior["sources"])
    if collisions:
        raise RuntimeError(f"post-streaming source-key collision: {sorted(collisions)}")
    sources = dict(direct)
    for name, claim in prior["sources"].items():
        current = _small_source(root, str(claim["path"]))
        if current != claim:
            raise RuntimeError(f"prior streaming source changed: {claim['path']}")
        sources[name] = current
    if any(str(claim["path"]).lower().endswith(".dat") for claim in sources.values()):
        raise RuntimeError("post-streaming source set contains a full-state dat")
    configuration = deepcopy(prior["configuration"])
    for name in (
        "coefficient_report_directory",
        "evaluation_report_directory",
        "coefficient_manifest_path",
        "evaluation_manifest_path",
        "candidate_summary_path",
        "candidate_figure_path",
        "candidate_commit_manifest_path",
        "candidate_transient_backup_path",
        "fresh_map_manifest_path",
        "fresh_map_report_directory",
        "fresh_map_summary_path",
        "candidate_output_path",
        "fresh_map_output_path",
    ):
        configuration.pop(name, None)
    configuration.update(
        {
            "phase_index": spec.phase_index,
            "maximum_picard_maps": MAXIMUM_TOTAL_PICARD_MAPS,
            "maximum_additional_picard_maps": MAXIMUM_ADDITIONAL_PICARD_MAPS,
            "seed_completed_picard_maps": SEED_COMPLETED_MAPS,
            "first_runtime_iteration": 1,
            "last_runtime_iteration": 40,
            "maximum_concurrent_processes": 2,
            "initial_state_path": seed["mapped_state_path"],
            "initial_state_sha256": seed["mapped_state_sha256"],
            "scratch_state_path": seed["input_state_path"],
            "scratch_state_initial_sha256": seed["input_state_sha256"],
            "manifest_path": spec.manifest_path,
            "report_directory": spec.transient_report_directory,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "runner_path": spec.runner_path,
            "initial_reference_mode": "accepted_post_streaming_fresh_seed",
            "copy_or_initialize_full_state": False,
            "transient_report_budget_bytes": storage.TRANSIENT_REPORT_BUDGET_BYTES,
            "material_feedback_authorization_mode": (
                "after_two_consecutive_and_formal_pair"
            ),
        }
    )
    if configuration["maximum_concurrent_processes"] != 2:
        raise RuntimeError("post-streaming worker count changed")
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": sources,
        "full_state_claims": {
            "current_initial_is_prior_mapped": {
                "path": seed["mapped_state_path"],
                "size_bytes": configuration["raw_float64_checkpoint_size_bytes"],
                "sha256": seed["mapped_state_sha256"],
            },
            "scratch_initial_is_prior_candidate": {
                "path": seed["input_state_path"],
                "size_bytes": configuration["raw_float64_checkpoint_size_bytes"],
                "sha256": seed["input_state_sha256"],
            },
        },
        "configuration": configuration,
        "reference": {
            "seed_source": "accepted prior streaming fresh map",
            "seed_global_original_operator_residual": seed[
                "global_original_operator_residual"
            ],
            "seed_boundary_spectrum_l1": seed["boundary_spectrum_l1"],
            "seed_boundary_bolometric_fraction": seed[
                "boundary_bolometric_fraction"
            ],
        },
        "gates": gates,
        "progression_gate_definition": {
            "frequency_ownership_exact": True,
            "minimum_input_and_mapped_intensity_at_least": gates[
                "minimum_input_and_mapped_intensity_at_least"
            ],
            "subsequent_residual_contraction_ratio_below": gates[
                "subsequent_residual_contraction_ratio_below"
            ],
            "each_process_peak_rss_strictly_below_mib": gates[
                "each_process_peak_rss_strictly_below_mib"
            ],
            "each_worker_wall_time_strictly_below_s": gates[
                "each_worker_wall_time_strictly_below_s"
            ],
            "each_full_map_wall_time_strictly_below_s": gates[
                "each_full_map_wall_time_strictly_below_s"
            ],
        },
        "convergence_gate_definition": {
            "global_original_operator_residual_below": gates[
                "global_original_operator_residual_below"
            ],
            "global_boundary_spectrum_l1_below": gates[
                "global_boundary_spectrum_l1_below"
            ],
            "global_boundary_bolometric_fraction_below": gates[
                "global_boundary_bolometric_fraction_below"
            ],
        },
        "seed_iteration": seed,
        "storage_plan": {
            "current_buffer_role": "prior mapped input, then alternating",
            "scratch_buffer_role": "prior candidate output, then alternating",
            "additional_full_state_allocation_count": 0,
            "copy_initial_source": False,
            "single_stage_owned_transient_report_directory": True,
            "block_reports_compacted_after_each_committed_map": True,
        },
        "authorization": {
            "pure_picard_only": True,
            "anderson_after_seed": False,
            "continue_only_if_progression_gate_passes": True,
            "pause_at_first_low_residual_and_boundary_input": True,
            "provisional_feedback_extraction_at_pause": True,
            "provisional_feedback_is_formal_pair_authority": False,
            "material_feedback_authorized": False,
            "formal_pair_requires_next_consecutive_fresh_residual": True,
            "overwrite_only_two_claimed_buffers": True,
            "start_every_map_from_block_zero": True,
            "delete_only_stage_owned_transient_reports": True,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "intensity_floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
            "accept_dynamic_nlte_solution": False,
        },
    }


def write_protocol(
    root: Path, spec: PostStreamingPicardSpec, output_path: Path
) -> tuple[dict[str, object], str]:
    protocol = build_post_streaming_picard_protocol(root, spec)
    _write_json_atomic(output_path, protocol)
    return protocol, _sha256(output_path)


def _load_runtime_protocol(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    if len(expected_hash) != 64 or _sha256(protocol_path) != expected_hash:
        raise RuntimeError("frozen post-streaming Picard protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    cfg = protocol.get("configuration", {})
    if (
        cfg.get("runner_path") != RUNNER_RELATIVE_PATH
        or int(cfg.get("maximum_additional_picard_maps", -1)) != 40
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or protocol.get("authorization", {}).get("pure_picard_only") is not True
        or protocol.get("authorization", {}).get("anderson_after_seed") is not False
    ):
        raise RuntimeError("post-streaming Picard runtime schema changed")
    for source in protocol["sources"].values():
        if str(source["path"]).lower().endswith(".dat"):
            raise RuntimeError("post-streaming runtime source contains dat")
        path = root / source["path"]
        if (
            path.stat().st_size != int(source["size_bytes"])
            or _sha256(path) != source["sha256"]
        ):
            raise RuntimeError(f"post-streaming source changed: {source['path']}")
    return protocol


def initialize_manifest(
    root: Path, protocol_path: Path, expected_hash: str
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    cfg = protocol["configuration"]
    manifest_path = root / cfg["manifest_path"]
    expected_size = int(cfg["raw_float64_checkpoint_size_bytes"])
    if manifest_path.exists():
        manifest = _read(root, str(cfg["manifest_path"]))
        if manifest.get("protocol_sha256") != expected_hash:
            raise RuntimeError("post-streaming manifest belongs to another protocol")
        current = root / manifest["current_input_path"]
        output = root / manifest["next_output_path"]
        if current.stat().st_size != expected_size or output.stat().st_size != expected_size:
            raise RuntimeError("post-streaming recovery buffer size changed")
        if _sha256(current) != manifest["current_input_sha256"]:
            raise RuntimeError("post-streaming recovery current input changed")
        if manifest.get("active_iteration") is None and _sha256(output) != manifest[
            "next_output_sha256"
        ]:
            raise RuntimeError("post-streaming recovery scratch changed")
        return manifest
    current = root / cfg["initial_state_path"]
    output = root / cfg["scratch_state_path"]
    if (
        current.resolve() == output.resolve()
        or current.stat().st_size != expected_size
        or output.stat().st_size != expected_size
        or _sha256(current) != cfg["initial_state_sha256"]
        or _sha256(output) != cfg["scratch_state_initial_sha256"]
    ):
        raise RuntimeError("post-streaming initial double buffers changed")
    seed = deepcopy(protocol["seed_iteration"])
    paused = seed["convergence_passed"] is True
    manifest = {
        "phase": protocol["phase"],
        "protocol_sha256": expected_hash,
        "status": "provisional_pause" if paused else "running",
        "current_input_path": cfg["initial_state_path"],
        "current_input_sha256": cfg["initial_state_sha256"],
        "next_output_path": cfg["scratch_state_path"],
        "next_output_sha256": cfg["scratch_state_initial_sha256"],
        "iterations": [seed],
        "active_iteration": None,
    }
    if paused:
        manifest["accepted_state_path"] = seed["input_state_path"]
        manifest["accepted_state_sha256"] = seed["input_state_sha256"]
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _run_worker(
    protocol_path: Path,
    expected_hash: str,
    iteration: int,
    block_index: int,
    input_state: Path,
    input_sha256: str,
    output_state: Path,
    report_path: Path,
) -> None:
    protocol = _load_runtime_protocol(ROOT, protocol_path, expected_hash)
    fixed = _read(ROOT, protocol["sources"]["finite_trial_protocol"]["path"])
    if fixed["sources"]["current_material_state"] != protocol["sources"][
        "finite_trial_material"
    ]:
        raise RuntimeError("post-streaming fixed material changed")
    generic = engine.generic
    original = generic.base.phase7b9i._load_protocol
    try:
        generic.base.phase7b9i._load_protocol = lambda _path, validate_sources=False: fixed
        engine.EXPECTED_PROTOCOL_SHA256 = expected_hash
        generic.EXPECTED_PROTOCOL_SHA256 = expected_hash
        engine._run_worker(
            protocol_path,
            iteration,
            block_index,
            input_state,
            input_sha256,
            output_state,
            report_path,
        )
    finally:
        generic.base.phase7b9i._load_protocol = original


BatchExecutor = Callable[
    [int, list[int], Path, str, Path, list[Path]], list[dict[str, object]]
]


def _default_batch_executor(
    root: Path, protocol_path: Path, expected_hash: str
) -> BatchExecutor:
    def execute(
        iteration: int,
        indices: list[int],
        input_path: Path,
        input_hash: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(root / RUNNER_RELATIVE_PATH),
                    "--worker",
                    "--protocol",
                    str(protocol_path),
                    "--expected-protocol-sha256",
                    expected_hash,
                    "--iteration",
                    str(iteration),
                    "--block-index",
                    str(index),
                    "--input-state",
                    str(input_path),
                    "--input-sha256",
                    input_hash,
                    "--output-state",
                    str(output_path),
                    "--worker-report",
                    str(report_path),
                ],
                cwd=root,
            )
            for index, report_path in zip(indices, report_paths, strict=True)
        ]
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"post-streaming worker batch failed: {codes}")
        return [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]

    return execute


def _expected_ranges(protocol: dict[str, object]) -> list[tuple[int, int]]:
    cfg = protocol["configuration"]
    groups = int(cfg["physical_frequency_groups"])
    count = int(cfg["natural_frequency_block_count"])
    width = int(cfg["diagnostic_frequency_block"])
    ranges = [
        (index * width, min((index + 1) * width, groups))
        for index in range(count)
    ]
    if count != 76 or ranges[-1][1] != groups:
        raise RuntimeError("post-streaming frequency partition changed")
    return ranges


def _run_one_map(
    root: Path,
    protocol_path: Path,
    protocol: dict[str, object],
    expected_hash: str,
    manifest: dict[str, object],
    executor: BatchExecutor,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = engine._shape(protocol)
    manifest_path = root / cfg["manifest_path"]
    iteration = len(manifest["iterations"])
    if iteration < 1 or iteration > int(cfg["last_runtime_iteration"]):
        raise RuntimeError("post-streaming runtime iteration escaped 1..40")
    input_state = root / manifest["current_input_path"]
    output_state = root / manifest["next_output_path"]
    active = manifest.get("active_iteration")
    if active is None:
        active = {
            "iteration": iteration,
            "input_state_path": manifest["current_input_path"],
            "input_state_sha256": manifest["current_input_sha256"],
            "output_state_path": manifest["next_output_path"],
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        manifest["active_iteration"] = active
        _write_json_atomic(manifest_path, manifest)
    if (
        int(active["iteration"]) != iteration
        or active["input_state_path"] != manifest["current_input_path"]
        or active["input_state_sha256"] != manifest["current_input_sha256"]
        or active["output_state_path"] != manifest["next_output_path"]
    ):
        raise RuntimeError("post-streaming active-map lineage changed")
    completed = {int(row["block_index"]): row for row in active["completed_blocks"]}
    ranges = _expected_ranges(protocol)
    if any(index < 0 or index >= 76 for index in completed) or len(completed) != len(
        active["completed_blocks"]
    ):
        raise RuntimeError("post-streaming completed-block ownership changed")
    for index, row in completed.items():
        start, stop = ranges[index]
        if (row.get("core_group_start"), row.get("core_group_stop")) != (start, stop):
            raise RuntimeError("post-streaming completed-block range changed")
        digest = engine.base.phase7b9d._block_sha256(output_state, shape, start, stop)
        if digest != row["output_block_sha256"]:
            raise RuntimeError("post-streaming completed output block changed")
    pending = [index for index in range(76) if index not in completed]
    report_root = storage._transient_root(root, protocol, expected_hash)
    report_dir = report_root / f"iteration_{iteration:02d}"
    report_dir.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(pending), 2):
        batch = pending[offset : offset + 2]
        paths = [report_dir / f"phase7b9dp_block{index:02d}.json" for index in batch]
        started = time.perf_counter()
        rows = executor(
            iteration,
            batch,
            input_state,
            str(manifest["current_input_sha256"]),
            output_state,
            paths,
        )
        if len(rows) != len(batch):
            raise RuntimeError("post-streaming worker report count changed")
        for index, path, row in zip(batch, paths, rows, strict=True):
            start, stop = ranges[index]
            if (
                row.get("protocol_sha256") != expected_hash
                or int(row.get("block_index", -1)) != index
                or int(row.get("picard_iteration", -1)) != iteration
                or row.get("input_state_sha256") != manifest["current_input_sha256"]
                or (row.get("core_group_start"), row.get("core_group_stop"))
                != (start, stop)
            ):
                raise RuntimeError("post-streaming worker report changed")
            row["output_block_sha256"] = engine.base.phase7b9d._block_sha256(
                output_state, shape, start, stop
            )
            _write_json_atomic(path, row)
            active["completed_blocks"].append(row)
        active["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        active["accumulated_wall_runtime_s"] += time.perf_counter() - started
        _write_json_atomic(manifest_path, manifest)
    reports = list(active["completed_blocks"])
    metrics = engine._aggregate(reports, shape)
    metrics["block_report_count"] = len(reports)
    metrics["full_map_wall_runtime_s"] = float(active["accumulated_wall_runtime_s"])
    previous_residual = float(
        manifest["iterations"][-1]["global_original_operator_residual"]
    )
    if previous_residual <= 0.0:
        raise ArithmeticError("post-streaming previous residual cannot define contraction")
    contraction = float(metrics["global_original_operator_residual"]) / previous_residual
    progression_checks = progression._progression_checks(gates, metrics, contraction)
    convergence_checks = progression._convergence_checks(gates, metrics)
    progression_passed = all(progression_checks.values())
    convergence_passed = progression_passed and all(convergence_checks.values())
    boundary_passed = bool(
        convergence_checks["boundary_spectrum_pass"]
        and convergence_checks["boundary_bolometric_pass"]
    )
    output_hash = _sha256(output_state)
    record = {
        "iteration": iteration,
        "input_state_path": manifest["current_input_path"],
        "input_state_sha256": manifest["current_input_sha256"],
        "mapped_state_path": manifest["next_output_path"],
        "mapped_state_sha256": output_hash,
        **metrics,
        "contraction_ratio": contraction,
        "contraction_applicable": True,
        "initial_reproduction_applicable": False,
        "gate_checks": {
            "frequency_ownership_pass": progression_checks[
                "frequency_ownership_pass"
            ],
            "positive_map_pass": progression_checks["positive_map_pass"],
            "initial_reproduction_pass": True,
            "contraction_pass": progression_checks["contraction_pass"],
            "boundary_pass": boundary_passed,
            "resources_pass": progression_checks["resources_pass"],
        },
        "original_map_passed": bool(progression_passed and boundary_passed),
        "progression_gate_checks": progression_checks,
        "progression_passed": progression_passed,
        "convergence_gate_checks": convergence_checks,
        "convergence_passed": convergence_passed,
        "map_passed": convergence_passed,
        "reports": reports,
    }
    manifest["iterations"].append(record)
    manifest["active_iteration"] = None
    if convergence_passed:
        manifest["status"] = "provisional_pause"
        manifest["accepted_state_path"] = manifest["current_input_path"]
        manifest["accepted_state_sha256"] = manifest["current_input_sha256"]
        manifest["next_output_sha256"] = output_hash
    elif not progression_passed:
        manifest["status"] = "gate_failed"
        manifest["next_output_sha256"] = output_hash
    elif len(manifest["iterations"]) >= int(cfg["maximum_picard_maps"]):
        manifest["status"] = "maximum_maps_exhausted"
        manifest["next_output_sha256"] = output_hash
    else:
        previous_path = manifest["current_input_path"]
        previous_hash = manifest["current_input_sha256"]
        manifest["current_input_path"] = manifest["next_output_path"]
        manifest["current_input_sha256"] = output_hash
        manifest["next_output_path"] = previous_path
        manifest["next_output_sha256"] = previous_hash
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _summary(
    root: Path,
    protocol: dict[str, object],
    manifest: dict[str, object],
    expected_hash: str,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    records = manifest["iterations"]
    figure = root / cfg["figure_path"]
    if records:
        engine._plot(figure, records)
    paused = manifest["status"] == "provisional_pause"
    payload = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V-pure-Picard]+[O]",
        "protocol_sha256": expected_hash,
        "status": manifest["status"],
        "completed_picard_maps": len(records),
        "completed_additional_picard_maps": len(records) - 1,
        "residual_history": [
            row["global_original_operator_residual"] for row in records
        ],
        "contraction_ratio_history": [row["contraction_ratio"] for row in records],
        "boundary_spectrum_l1_history": [
            row["boundary_spectrum_l1"] for row in records
        ],
        "accepted_state_path": manifest.get("accepted_state_path"),
        "accepted_state_sha256": manifest.get("accepted_state_sha256"),
        "iterations": records,
        "decision": {
            "positive_picard_sequence_reached_first_low_residual": paused,
            "first_low_residual_and_boundary_input_audited": paused,
            "provisional_feedback_extraction_authorized": paused,
            "provisional_feedback_is_formal_pair_authority": False,
            "next_consecutive_fresh_residual_required": paused,
            "formal_h_he_feedback_pair_authorized": False,
            "material_feedback_authorized": False,
            "anderson_used_after_seed": False,
            "dynamic_nlte_solution_accepted": False,
        },
        "figures": [figure.name] if records else [],
    }
    if paused:
        accepted = next(
            row for row in reversed(records) if row["convergence_passed"] is True
        )
        payload.update(
            {
                "first_low_residual_input_path": accepted["input_state_path"],
                "first_low_residual_input_sha256": accepted["input_state_sha256"],
                "next_consecutive_input_path": accepted["mapped_state_path"],
                "next_consecutive_input_sha256": accepted["mapped_state_sha256"],
            }
        )
    _write_json_atomic(root / cfg["summary_path"], payload)
    return payload


def run_continuation(
    root: Path,
    protocol_path: Path,
    expected_hash: str,
    *,
    batch_executor: BatchExecutor | None = None,
    stop_after_iteration: int | None = None,
) -> dict[str, object]:
    protocol = _load_runtime_protocol(root, protocol_path, expected_hash)
    manifest = initialize_manifest(root, protocol_path, expected_hash)
    storage._transient_root(root, protocol, expected_hash)
    executor = batch_executor or _default_batch_executor(
        root, protocol_path, expected_hash
    )
    while manifest["status"] == "running":
        manifest = _run_one_map(
            root,
            protocol_path,
            protocol,
            expected_hash,
            manifest,
            executor,
        )
        manifest = storage.compact_committed_reports(
            root, protocol, expected_hash
        )
        summary = _summary(root, protocol, manifest, expected_hash)
        if (
            stop_after_iteration is not None
            and len(manifest["iterations"]) - 1 >= stop_after_iteration
        ):
            return summary
    return _summary(root, protocol, manifest, expected_hash)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--iteration", type=int)
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--output-state", type=Path)
    parser.add_argument("--worker-report", type=Path)
    parser.add_argument("--stop-after-iteration", type=int)
    args = parser.parse_args()
    if args.worker:
        required = (
            args.iteration,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.output_state,
            args.worker_report,
        )
        if any(value is None for value in required):
            raise ValueError("worker mode requires iteration, block and both states")
        _run_worker(
            args.protocol,
            args.expected_protocol_sha256,
            int(args.iteration),
            int(args.block_index),
            args.input_state,
            str(args.input_sha256),
            args.output_state,
            args.worker_report,
        )
        return
    summary = run_continuation(
        ROOT,
        args.protocol,
        args.expected_protocol_sha256,
        stop_after_iteration=args.stop_after_iteration,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
