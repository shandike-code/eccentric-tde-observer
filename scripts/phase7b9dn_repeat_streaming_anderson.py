"""Phase 7B9dn：由一个完整 streaming Anderson 周期冻结下一重复周期。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path, PurePosixPath
from typing import Sequence

try:
    from scripts import phase7b9di_streaming_anderson_tail as streaming
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9di_streaming_anderson_tail as streaming  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
BUILDER_RELATIVE_PATH = "scripts/phase7b9dn_repeat_streaming_anderson.py"
DIRECT_SOURCE_KEYS = {
    "prior_streaming_protocol",
    "prior_pass1_manifest",
    "prior_pass2_manifest",
    "prior_candidate_commit_manifest",
    "prior_fresh_manifest",
    "prior_fresh_summary",
    "repeat_cycle_preregister_builder",
}


@dataclass(frozen=True)
class RepeatStreamingCycleSpec:
    phase: str
    phase_index: int
    classification: str
    prior_protocol_path: str
    prior_pass1_manifest_path: str
    prior_pass2_manifest_path: str
    prior_candidate_commit_manifest_path: str
    prior_fresh_manifest_path: str
    prior_fresh_summary_path: str
    coefficient_report_directory: str
    evaluation_report_directory: str
    coefficient_manifest_path: str
    evaluation_manifest_path: str
    candidate_summary_path: str
    candidate_figure_path: str


def _read_json(root: Path, relative: str) -> dict[str, object]:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def _small_source(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    logical = PurePosixPath(relative)
    if logical.is_absolute() or ".." in logical.parts:
        raise RuntimeError("repeat-cycle source path escaped the repository")
    if path.suffix.lower() == ".dat":
        raise RuntimeError("repeat-cycle builder refuses any .dat source")
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": streaming._sha256(path),
    }


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _expected_ranges(protocol: dict[str, object]) -> list[tuple[int, int]]:
    cfg = protocol["configuration"]
    groups = int(cfg["physical_frequency_groups"])
    count = int(cfg["natural_frequency_block_count"])
    width = int(cfg["diagnostic_frequency_block"])
    ranges = [
        (index * width, min((index + 1) * width, groups))
        for index in range(count)
    ]
    if count != 76 or groups != 9632 or ranges[-1][1] != groups:
        raise RuntimeError("prior streaming block partition changed")
    return ranges


def _validate_prior_protocol(
    root: Path, spec: RepeatStreamingCycleSpec
) -> tuple[dict[str, object], str]:
    protocol = _read_json(root, spec.prior_protocol_path)
    digest = streaming._sha256(root / spec.prior_protocol_path)
    cfg = protocol.get("configuration", {})
    algebraic = protocol.get("algebraic_gates", {})
    fresh = protocol.get("fresh_map_gates", {})
    authorization = protocol.get("authorization", {})
    execution = protocol.get("execution_plan", {})
    expected_algebraic = {
        **streaming.frozen.protected_anderson_tail_gates(),
        "predicted_boundary_spectrum_ratio_to_x24_below": 1.0,
        "predicted_boundary_bolometric_ratio_to_x24_below": 1.0,
        "pass1_pass2_each_mapped_block_sha256_must_match": True,
        "pass1_pass2_block_ownership_exactly_once": True,
        "each_dry_process_peak_rss_strictly_below_mib": 6144.0,
        "each_dry_worker_wall_time_strictly_below_s": 60.0,
        "each_dry_full_map_wall_time_strictly_below_s": 1800.0,
    }
    expected_fresh = streaming.frozen.memory_safe_candidate_map_gates()
    expected_fresh["each_worker_wall_time_strictly_below_s"] = 60.0
    if (
        cfg.get("runner_path") != streaming.RUNNER_RELATIVE_PATH
        or cfg.get("orchestrator_path") != streaming.ORCHESTRATOR_RELATIVE_PATH
        or cfg.get("dry_pass_parent_path")
        != streaming.DRY_PASS_PARENT_RELATIVE_PATH
        or int(cfg.get("maximum_concurrent_processes", -1)) != 2
        or int(cfg.get("natural_frequency_block_count", -1)) != 76
        or int(cfg.get("physical_frequency_groups", -1)) != 9632
        or int(cfg.get("angular_direction_count", -1)) != 32
        or int(cfg.get("radiation_depth_cell_count", -1)) != 4096
        or int(cfg.get("scan_frequency_chunk", -1)) != 16
        or int(cfg.get("diagnostic_frequency_block", -1)) != 128
        or float(cfg.get("minimum_forward_picard_fraction", -1)) != 1.0
        or float(cfg.get("maximum_forward_picard_fraction", -1)) != 96.0
        or algebraic != expected_algebraic
        or fresh != expected_fresh
        or authorization.get("pass1_may_write_full_state") is not False
        or authorization.get("pass2_may_write_full_state") is not False
        or authorization.get("fresh_full_original_operator_map_required") is not True
        or authorization.get("predicted_metrics_are_acceptance_authority")
        is not False
        or authorization.get("material_feedback_authorized") is not False
        or authorization.get("accept_dynamic_nlte_solution") is not False
        or execution.get("additional_full_state_count") != 0
        or execution.get("transport_equivalent_full_map_count") != 3
        or execution.get("dry_map_count") != 2
        or execution.get("fresh_residual_map_count") != 1
        or execution.get("dry_maps_count_as_fresh_residuals") is not False
    ):
        raise RuntimeError("prior streaming protocol changed its frozen schema")
    _expected_ranges(protocol)
    expected_executables = {
        "streaming_anderson_worker": streaming.RUNNER_RELATIVE_PATH,
        "streaming_anderson_orchestrator": streaming.ORCHESTRATOR_RELATIVE_PATH,
        "streaming_anderson_dry_pass_parent": (
            streaming.DRY_PASS_PARENT_RELATIVE_PATH
        ),
    }
    sources = protocol.get("sources", {})
    if not isinstance(sources, dict):
        raise RuntimeError("prior streaming sources are missing")
    for name, claim in sources.items():
        if not isinstance(claim, dict) or "path" not in claim:
            raise RuntimeError(f"prior streaming source is malformed: {name}")
        relative = str(claim["path"])
        if Path(relative).suffix.lower() == ".dat":
            raise RuntimeError("prior streaming protocol contains a .dat source")
        if _small_source(root, relative) != claim:
            raise RuntimeError(f"prior streaming source changed: {relative}")
    for name, relative in expected_executables.items():
        if sources.get(name, {}).get("path") != relative:
            raise RuntimeError(f"prior streaming executable pin changed: {name}")
    if any(bool(cfg.get(name)) for name in (
        "cellwise_clipping",
        "nan_to_num",
        "intensity_floor",
        "point_deletion",
        "posthoc_renormalization",
        "kkt_regularization",
        "matter_feedback",
    )):
        raise RuntimeError("prior streaming protocol enabled a forbidden repair")
    return protocol, digest


def _validate_dry_report(
    protocol: dict[str, object],
    protocol_hash: str,
    report: dict[str, object],
    pass_index: int,
    index: int,
) -> None:
    cfg = protocol["configuration"]
    gates = protocol["algebraic_gates"]
    start, stop = _expected_ranges(protocol)[index]
    if (
        report.get("protocol_sha256") != protocol_hash
        or int(report.get("pass_index", -1)) != pass_index
        or int(report.get("block_index", -1)) != index
        or (report.get("core_group_start"), report.get("core_group_stop"))
        != (start, stop)
        or report.get("x23_state_sha256") != cfg["x23_state_sha256"]
        or report.get("x24_state_sha256") != cfg["x24_state_sha256"]
        or report.get("full_state_write_performed") is not False
        or float(report.get("peak_process_rss_mib", math.inf))
        >= float(gates["each_dry_process_peak_rss_strictly_below_mib"])
        or float(report.get("wall_runtime_s", math.inf))
        >= float(gates["each_dry_worker_wall_time_strictly_below_s"])
        or not _valid_sha256(report.get("mapped_block_sha256"))
    ):
        raise RuntimeError(f"prior dry pass {pass_index} block {index} failed")


def _validate_report_files(
    root: Path,
    manifest: dict[str, object],
    reports: list[dict[str, object]],
) -> None:
    files = manifest.get("report_files")
    if not isinstance(files, list) or len(files) != 76:
        raise RuntimeError("prior dry report-file audit is incomplete")
    by_index = {int(row["block_index"]): row for row in files}
    if set(by_index) != set(range(76)):
        raise RuntimeError("prior dry report-file ownership changed")
    for report in reports:
        index = int(report["block_index"])
        claim = by_index[index]
        relative = str(claim.get("path", ""))
        if Path(relative).suffix == ".dat" or _small_source(root, relative) != {
            "path": relative,
            "size_bytes": claim.get("size_bytes"),
            "sha256": claim.get("sha256"),
        }:
            raise RuntimeError("prior dry report-file pin changed")
        if _read_json(root, relative) != report:
            raise RuntimeError("prior dry embedded report differs from its file")


def _validate_dry_manifests(
    root: Path,
    protocol: dict[str, object],
    protocol_hash: str,
    spec: RepeatStreamingCycleSpec,
) -> tuple[dict[str, object], dict[str, object]]:
    cfg = protocol["configuration"]
    if (
        spec.prior_pass1_manifest_path != cfg["coefficient_manifest_path"]
        or spec.prior_pass2_manifest_path != cfg["evaluation_manifest_path"]
    ):
        raise RuntimeError("explicit dry manifests do not match prior protocol")
    first = _read_json(root, spec.prior_pass1_manifest_path)
    second = _read_json(root, spec.prior_pass2_manifest_path)
    for pass_index, manifest in ((1, first), (2, second)):
        reports = manifest.get("reports")
        if (
            manifest.get("protocol_sha256") != protocol_hash
            or manifest.get("status") != "complete"
            or int(manifest.get("pass_index", -1)) != pass_index
            or manifest.get("full_state_write_performed") is not False
            or manifest.get("active_blocks") not in (None, [])
            or not isinstance(reports, list)
            or len(reports) != 76
            or float(manifest.get("full_map_wall_runtime_s", math.inf))
            >= float(
                protocol["algebraic_gates"][
                    "each_dry_full_map_wall_time_strictly_below_s"
                ]
            )
        ):
            raise RuntimeError(f"prior dry pass {pass_index} is incomplete")
        ordered = sorted(reports, key=lambda row: int(row["block_index"]))
        if [int(row["block_index"]) for row in ordered] != list(range(76)):
            raise RuntimeError("prior dry block ownership changed")
        for index, report in enumerate(ordered):
            _validate_dry_report(
                protocol, protocol_hash, report, pass_index, index
            )
        _validate_report_files(root, manifest, ordered)
        manifest["reports"] = ordered
    if not all(first.get("resource_gate_checks", {}).values()):
        raise RuntimeError("prior coefficient-pass resource gate failed")
    coefficient = streaming.aggregate_coefficient_statistics(
        first["reports"],
        minimum_fraction=float(cfg["minimum_forward_picard_fraction"]),
        maximum_fraction=float(cfg["maximum_forward_picard_fraction"]),
    )
    if first.get("aggregate") != coefficient:
        raise RuntimeError("prior coefficient aggregate changed")
    coefficient_hash = streaming._sha256(root / spec.prior_pass1_manifest_path)
    if (
        second.get("coefficient_manifest_sha256") != coefficient_hash
        or second.get("selected_forward_fraction")
        != coefficient["selected_forward_fraction"]
    ):
        raise RuntimeError("prior evaluation consumed another coefficient")
    if any(
        first_report["mapped_block_sha256"]
        != second_report["mapped_block_sha256"]
        for first_report, second_report in zip(
            first["reports"], second["reports"], strict=True
        )
    ):
        raise RuntimeError("prior two dry passes are not blockwise reproducible")
    evaluation = streaming.aggregate_evaluation_statistics(
        second["reports"], first["reports"]
    )
    if second.get("aggregate") != evaluation:
        raise RuntimeError("prior evaluation aggregate changed")
    checks = streaming.algebraic_gate_checks(protocol, coefficient, evaluation)
    checks.update(
        {
            "pass1_resources_pass": True,
            "pass2_resources_pass": True,
            "block_ownership_pass": True,
        }
    )
    if second.get("gate_checks") != checks or not all(checks.values()):
        raise RuntimeError("prior algebraic gate failed")
    return first, second


def _validate_commit(
    root: Path,
    protocol: dict[str, object],
    protocol_hash: str,
    first: dict[str, object],
    second: dict[str, object],
    spec: RepeatStreamingCycleSpec,
) -> dict[str, object]:
    cfg = protocol["configuration"]
    if spec.prior_candidate_commit_manifest_path != cfg[
        "candidate_commit_manifest_path"
    ]:
        raise RuntimeError("explicit candidate commit does not match prior protocol")
    commit = _read_json(root, spec.prior_candidate_commit_manifest_path)
    completed = commit.get("completed_blocks")
    if (
        commit.get("protocol_sha256") != protocol_hash
        or commit.get("status") != "complete"
        or commit.get("selected_forward_fraction")
        != first["aggregate"]["selected_forward_fraction"]
        or commit.get("algebraic_prediction") != second["aggregate"]
        or commit.get("algebraic_gate_checks") != second["gate_checks"]
        or not all(commit.get("algebraic_gate_checks", {}).values())
        or commit.get("active_block") is not None
        or not isinstance(completed, list)
        or len(completed) != 76
        or len(commit.get("original_x23_block_sha256", [])) != 76
        or len(commit.get("frozen_x24_block_sha256", [])) != 76
        or commit.get("candidate_state_path") != cfg["candidate_output_path"]
        or not _valid_sha256(commit.get("candidate_state_sha256"))
        or commit.get("candidate_write_resources_pass") is not True
        or commit.get("fresh_original_operator_map_authorized") is not True
        or commit.get("prediction_used_as_fresh_residual") is not False
        or float(commit.get("accumulated_write_wall_runtime_s", math.inf))
        >= float(protocol["algebraic_gates"]["write_wall_time_strictly_below_s"])
    ):
        raise RuntimeError("prior candidate commit is incomplete")
    ordered = sorted(completed, key=lambda row: int(row["block_index"]))
    for index, (row, expected_range) in enumerate(
        zip(ordered, _expected_ranges(protocol), strict=True)
    ):
        if (
            int(row.get("block_index", -1)) != index
            or (row.get("core_group_start"), row.get("core_group_stop"))
            != expected_range
            or not _valid_sha256(row.get("candidate_block_sha256"))
        ):
            raise RuntimeError("prior candidate block commit changed")
    if not all(
        _valid_sha256(value)
        for value in (
            commit["original_x23_block_sha256"]
            + commit["frozen_x24_block_sha256"]
        )
    ):
        raise RuntimeError("prior candidate basis block hashes changed")
    return commit


def _fresh_metrics(reports: list[dict[str, object]]) -> dict[str, float]:
    maximum_change = max(
        float(row["maximum_absolute_radiation_change"]) for row in reports
    )
    maximum_scale = max(float(row["maximum_radiation_scale"]) for row in reports)
    boundary_numerator = sum(
        float(row["boundary_spectrum_l1_numerator"]) for row in reports
    )
    current_scale = sum(
        float(row["current_boundary_absolute_scale"]) for row in reports
    )
    mapped_scale = sum(
        float(row["mapped_boundary_absolute_scale"]) for row in reports
    )
    current_bolometric = sum(
        float(row["current_boundary_bolometric"]) for row in reports
    )
    mapped_bolometric = sum(
        float(row["mapped_boundary_bolometric"]) for row in reports
    )
    return {
        "global_original_operator_residual": (
            maximum_change / maximum_scale
            if maximum_scale > 0.0
            else maximum_change
        ),
        "boundary_spectrum_l1": boundary_numerator
        / max(current_scale, mapped_scale),
        "boundary_bolometric_fraction": abs(
            mapped_bolometric - current_bolometric
        )
        / max(abs(current_bolometric), abs(mapped_bolometric)),
        "maximum_process_peak_rss_mib": max(
            float(row["peak_process_rss_mib"]) for row in reports
        ),
        "maximum_worker_wall_runtime_s": max(
            float(row["wall_runtime_s"]) for row in reports
        ),
    }


def _validate_fresh(
    root: Path,
    protocol: dict[str, object],
    protocol_hash: str,
    commit: dict[str, object],
    second: dict[str, object],
    spec: RepeatStreamingCycleSpec,
) -> tuple[dict[str, object], dict[str, object]]:
    cfg = protocol["configuration"]
    gates = protocol["fresh_map_gates"]
    if (
        spec.prior_fresh_manifest_path != cfg["fresh_map_manifest_path"]
        or spec.prior_fresh_summary_path != cfg["fresh_map_summary_path"]
    ):
        raise RuntimeError("explicit fresh artifacts do not match prior protocol")
    manifest = _read_json(root, spec.prior_fresh_manifest_path)
    reports = manifest.get("completed_blocks")
    if (
        manifest.get("protocol_sha256") != protocol_hash
        or manifest.get("status") != "complete"
        or manifest.get("candidate_state_path") != commit["candidate_state_path"]
        or manifest.get("candidate_state_sha256") != commit["candidate_state_sha256"]
        or manifest.get("output_state_path") != cfg["fresh_map_output_path"]
        or not _valid_sha256(manifest.get("output_state_sha256"))
        or not isinstance(reports, list)
        or len(reports) != 76
        or set(manifest.get("fresh_gate_checks", {}))
        != {
            "frequency_ownership_pass",
            "positive_map_pass",
            "resources_pass",
            "prediction_reproduction_pass",
        }
        or not all(manifest["fresh_gate_checks"].values())
        or float(manifest.get("accumulated_wall_runtime_s", math.inf))
        >= float(gates["full_map_wall_time_strictly_below_s"])
    ):
        raise RuntimeError("prior fresh map is incomplete")
    ordered = sorted(reports, key=lambda row: int(row["block_index"]))
    for index, (row, expected_range) in enumerate(
        zip(ordered, _expected_ranges(protocol), strict=True)
    ):
        if (
            int(row.get("block_index", -1)) != index
            or row.get("protocol_sha256") != protocol_hash
            or row.get("input_state_sha256") != commit["candidate_state_sha256"]
            or (row.get("core_group_start"), row.get("core_group_stop"))
            != expected_range
            or not _valid_sha256(row.get("output_block_sha256"))
            or float(row.get("minimum_input_intensity", -math.inf))
            < float(gates["minimum_input_and_mapped_intensity_at_least"])
            or float(row.get("minimum_mapped_intensity", -math.inf))
            < float(gates["minimum_input_and_mapped_intensity_at_least"])
            or float(row.get("peak_process_rss_mib", math.inf))
            >= float(gates["each_process_peak_rss_strictly_below_mib"])
            or float(row.get("wall_runtime_s", math.inf))
            >= float(gates["each_worker_wall_time_strictly_below_s"])
        ):
            raise RuntimeError(f"prior fresh block {index} failed")
    metrics = _fresh_metrics(ordered)
    prediction = second["aggregate"]
    if (
        abs(
            metrics["global_original_operator_residual"]
            - float(prediction["predicted_global_original_operator_residual"])
        )
        > float(gates["input_global_residual_matches_phase7b9ab_absolute_tolerance"])
        or abs(
            metrics["boundary_spectrum_l1"]
            - float(prediction["predicted_boundary_spectrum_l1"])
        )
        > float(gates["input_boundary_metrics_match_phase7b9ab_absolute_tolerance"])
        or abs(
            metrics["boundary_bolometric_fraction"]
            - float(prediction["predicted_boundary_bolometric_fraction"])
        )
        > float(gates["input_boundary_metrics_match_phase7b9ab_absolute_tolerance"])
    ):
        raise RuntimeError("prior fresh map does not reproduce its prediction")
    summary = _read_json(root, spec.prior_fresh_summary_path)
    if (
        summary.get("protocol_sha256") != protocol_hash
        or summary.get("status") != "complete"
        or summary.get("candidate_state_path") != commit["candidate_state_path"]
        or summary.get("candidate_state_sha256") != commit["candidate_state_sha256"]
        or summary.get("mapped_state_path") != manifest["output_state_path"]
        or summary.get("mapped_state_sha256") != manifest["output_state_sha256"]
        or summary.get("algebraic_prediction") != prediction
        or summary.get("fresh_input_global_original_operator_residual")
        != metrics["global_original_operator_residual"]
        or summary.get("fresh_input_boundary_spectrum_l1")
        != metrics["boundary_spectrum_l1"]
        or summary.get("fresh_input_boundary_bolometric_fraction")
        != metrics["boundary_bolometric_fraction"]
        or summary.get("maximum_process_peak_rss_mib")
        != metrics["maximum_process_peak_rss_mib"]
        or summary.get("maximum_worker_wall_runtime_s")
        != metrics["maximum_worker_wall_runtime_s"]
        or summary.get("full_map_wall_runtime_s")
        != manifest["accumulated_wall_runtime_s"]
        or summary.get("gate_checks") != manifest["fresh_gate_checks"]
        or summary.get("decision", {}).get("fresh_original_operator_map_completed")
        is not True
        or summary.get("decision", {}).get("prediction_used_as_fresh_residual")
        is not False
        or summary.get("decision", {}).get(
            "fresh_residual_measured_from_candidate_map"
        )
        is not True
        or summary.get("decision", {}).get("material_feedback_authorized")
        is not False
        or summary.get("decision", {}).get("accept_dynamic_nlte_solution")
        is not False
    ):
        raise RuntimeError("prior fresh summary changed or broke lineage")
    return manifest, summary


def build_repeat_streaming_protocol(
    root: Path, spec: RepeatStreamingCycleSpec
) -> dict[str, object]:
    """Freeze the next cycle using only six prior small artifacts."""
    prior_artifacts = (
        spec.prior_protocol_path,
        spec.prior_pass1_manifest_path,
        spec.prior_pass2_manifest_path,
        spec.prior_candidate_commit_manifest_path,
        spec.prior_fresh_manifest_path,
        spec.prior_fresh_summary_path,
    )
    if any(Path(relative).suffix.lower() != ".json" for relative in prior_artifacts):
        raise RuntimeError("repeat-cycle builder accepts only prior JSON artifacts")
    prior, prior_hash = _validate_prior_protocol(root, spec)
    first, second = _validate_dry_manifests(root, prior, prior_hash, spec)
    commit = _validate_commit(root, prior, prior_hash, first, second, spec)
    fresh_manifest, summary = _validate_fresh(
        root, prior, prior_hash, commit, second, spec
    )
    direct = {
        "prior_streaming_protocol": _small_source(root, spec.prior_protocol_path),
        "prior_pass1_manifest": _small_source(
            root, spec.prior_pass1_manifest_path
        ),
        "prior_pass2_manifest": _small_source(
            root, spec.prior_pass2_manifest_path
        ),
        "prior_candidate_commit_manifest": _small_source(
            root, spec.prior_candidate_commit_manifest_path
        ),
        "prior_fresh_manifest": _small_source(
            root, spec.prior_fresh_manifest_path
        ),
        "prior_fresh_summary": _small_source(root, spec.prior_fresh_summary_path),
        "repeat_cycle_preregister_builder": _small_source(
            root, BUILDER_RELATIVE_PATH
        ),
    }
    if set(direct) != DIRECT_SOURCE_KEYS:
        raise RuntimeError("repeat-cycle direct source set changed")
    inherited = prior["sources"]
    collisions = set(direct).intersection(inherited)
    if collisions:
        raise RuntimeError(
            f"repeat-cycle source-key collision: {sorted(collisions)}"
        )
    sources = dict(direct)
    for name, claim in inherited.items():
        current = _small_source(root, str(claim["path"]))
        if current != claim:
            raise RuntimeError(f"prior streaming source changed: {claim['path']}")
        sources[name] = current
    if any(str(claim["path"]).endswith(".dat") for claim in sources.values()):
        raise RuntimeError("repeat-cycle source set contains a .dat file")

    candidate = {
        "path": summary["candidate_state_path"],
        "sha256": summary["candidate_state_sha256"],
    }
    mapped = {
        "path": summary["mapped_state_path"],
        "sha256": summary["mapped_state_sha256"],
    }
    if candidate["path"] == mapped["path"]:
        raise RuntimeError("repeat cycle requires two distinct buffers")
    protocol = deepcopy(prior)
    protocol.update(
        {
            "phase": spec.phase,
            "protocol_version": 1,
            "classification": spec.classification,
            "sources": sources,
            "full_state_claims": {
                "x23_retained_until_all_algebraic_gates_pass": {
                    **candidate,
                    "size_bytes": prior["configuration"][
                        "raw_float64_checkpoint_size_bytes"
                    ],
                },
                "x24_retained_through_both_dry_maps": {
                    **mapped,
                    "size_bytes": prior["configuration"][
                        "raw_float64_checkpoint_size_bytes"
                    ],
                },
            },
            "repeat_cycle_lineage": {
                "prior_protocol_sha256": prior_hash,
                "x23_is_prior_candidate": True,
                "x24_is_prior_fresh_mapped_state": True,
                "prediction_used_as_fresh_residual": False,
                "prior_candidate_state_path": candidate["path"],
                "prior_candidate_state_sha256": candidate["sha256"],
                "prior_mapped_state_path": mapped["path"],
                "prior_mapped_state_sha256": mapped["sha256"],
                "prior_fresh_manifest_sha256": streaming._sha256(
                    root / spec.prior_fresh_manifest_path
                ),
            },
        }
    )
    cfg = protocol["configuration"]
    work_root = Path(spec.coefficient_manifest_path).parent
    fresh_summary = Path(spec.candidate_summary_path).with_name(
        f"{Path(spec.candidate_summary_path).stem}_fresh_map.json"
    )
    cfg.update(
        {
            "phase_index": spec.phase_index,
            "x23_state_path": candidate["path"],
            "x23_state_sha256": candidate["sha256"],
            "x24_state_path": mapped["path"],
            "x24_state_sha256": mapped["sha256"],
            "x23_global_original_operator_residual": summary[
                "fresh_input_global_original_operator_residual"
            ],
            "x23_boundary_spectrum_l1": summary[
                "fresh_input_boundary_spectrum_l1"
            ],
            "x23_boundary_bolometric_fraction": summary[
                "fresh_input_boundary_bolometric_fraction"
            ],
            "coefficient_report_directory": spec.coefficient_report_directory,
            "evaluation_report_directory": spec.evaluation_report_directory,
            "coefficient_manifest_path": spec.coefficient_manifest_path,
            "evaluation_manifest_path": spec.evaluation_manifest_path,
            "candidate_summary_path": spec.candidate_summary_path,
            "candidate_figure_path": spec.candidate_figure_path,
            "candidate_commit_manifest_path": str(
                work_root / "candidate_commit_manifest.json"
            ),
            "candidate_transient_backup_path": str(
                work_root / "candidate_transient_active_block.backup"
            ),
            "fresh_map_manifest_path": str(work_root / "fresh_map_manifest.json"),
            "fresh_map_report_directory": str(work_root / "fresh_map_reports"),
            "fresh_map_summary_path": str(fresh_summary),
            "candidate_output_path": candidate["path"],
            "fresh_map_output_path": mapped["path"],
        }
    )
    if (
        cfg["maximum_concurrent_processes"] != 2
        or protocol["algebraic_gates"][
            "each_dry_full_map_wall_time_strictly_below_s"
        ]
        != 1800.0
        or protocol["fresh_map_gates"]["full_map_wall_time_strictly_below_s"]
        != 1800.0
        or protocol["execution_plan"]["additional_full_state_count"] != 0
    ):
        raise RuntimeError("repeat cycle changed a frozen resource/state gate")
    # 中文：只轮换两个已存在缓冲；预测量仍不能代替 fresh residual。
    if fresh_manifest["candidate_state_sha256"] != cfg["x23_state_sha256"]:
        raise RuntimeError("repeat-cycle candidate lineage changed")
    return protocol


def _safe_json_path(value: str, *, output: bool) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "outputs"
        or path.suffix != ".json"
    ):
        raise ValueError("repeat-cycle paths must be repository-relative JSON under outputs/")
    if output and len(path.parts) > 1 and path.parts[1] == "checkpoints":
        raise ValueError("repeat-cycle protocol must not be written in checkpoints/")
    return str(path)


def preregister(
    root: Path,
    *,
    prior_protocol_path: str,
    prior_pass1_manifest_path: str,
    prior_pass2_manifest_path: str,
    prior_candidate_commit_manifest_path: str,
    prior_fresh_manifest_path: str,
    prior_fresh_summary_path: str,
    protocol_output_path: str,
    phase_index: int,
    phase: str,
    classification: str,
) -> tuple[dict[str, object], str]:
    inputs = [
        _safe_json_path(value, output=False)
        for value in (
            prior_protocol_path,
            prior_pass1_manifest_path,
            prior_pass2_manifest_path,
            prior_candidate_commit_manifest_path,
            prior_fresh_manifest_path,
            prior_fresh_summary_path,
        )
    ]
    output_relative = _safe_json_path(protocol_output_path, output=True)
    output = root / output_relative
    stem = output.stem
    work_root = PurePosixPath("outputs/checkpoints") / f"{stem}_work"
    candidate_summary = PurePosixPath("outputs") / f"{stem}_candidate_summary.json"
    candidate_figure = PurePosixPath("outputs") / f"{stem}_candidate.png"
    spec = RepeatStreamingCycleSpec(
        phase=phase,
        phase_index=phase_index,
        classification=classification,
        prior_protocol_path=inputs[0],
        prior_pass1_manifest_path=inputs[1],
        prior_pass2_manifest_path=inputs[2],
        prior_candidate_commit_manifest_path=inputs[3],
        prior_fresh_manifest_path=inputs[4],
        prior_fresh_summary_path=inputs[5],
        coefficient_report_directory=str(work_root / "pass1_coefficient_reports"),
        evaluation_report_directory=str(work_root / "pass2_evaluation_reports"),
        coefficient_manifest_path=str(work_root / "pass1_coefficient_manifest.json"),
        evaluation_manifest_path=str(work_root / "pass2_evaluation_manifest.json"),
        candidate_summary_path=str(candidate_summary),
        candidate_figure_path=str(candidate_figure),
    )
    payload = build_repeat_streaming_protocol(root, spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, output)
    return payload, streaming._sha256(output)


def main(argv: Sequence[str] | None = None, *, root: Path = ROOT) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-protocol", required=True)
    parser.add_argument("--prior-pass1-manifest", required=True)
    parser.add_argument("--prior-pass2-manifest", required=True)
    parser.add_argument("--prior-candidate-commit-manifest", required=True)
    parser.add_argument("--prior-fresh-manifest", required=True)
    parser.add_argument("--prior-fresh-summary", required=True)
    parser.add_argument("--protocol-output", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument(
        "--phase", default="7B9dn repeat two-pass streaming Anderson(1)"
    )
    parser.add_argument(
        "--classification",
        default=(
            "[A-preregistered]+[V-prior-cycle]+[O]：仅复用已完整通过的前一 "
            "streaming 周期，在同一双缓冲上重复两遍 dry、候选提交和 fresh map。"
        ),
    )
    args = parser.parse_args(argv)
    _, digest = preregister(
        root,
        prior_protocol_path=args.prior_protocol,
        prior_pass1_manifest_path=args.prior_pass1_manifest,
        prior_pass2_manifest_path=args.prior_pass2_manifest,
        prior_candidate_commit_manifest_path=args.prior_candidate_commit_manifest,
        prior_fresh_manifest_path=args.prior_fresh_manifest,
        prior_fresh_summary_path=args.prior_fresh_summary,
        protocol_output_path=args.protocol_output,
        phase_index=args.phase_index,
        phase=args.phase,
        classification=args.classification,
    )
    print(digest)
    return digest


if __name__ == "__main__":
    main()
