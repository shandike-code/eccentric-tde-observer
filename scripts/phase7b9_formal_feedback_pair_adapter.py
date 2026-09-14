"""Phase 7B9：为任意连续收敛辐射 summary 构造正式 H/He feedback pair。"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)
from eccentric_tde_observer.formal_feedback_pair import (
    trial_feedback_pair_diagnostics,
    trial_feedback_pair_gate_checks,
    weighted_volume_l1,
)
from eccentric_tde_observer.full_frequency_residual_evaluation import (
    write_encoded_residual_atomic,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)
from eccentric_tde_observer.source import PhysicalDomainError


PHYSICAL_FREQUENCY_GROUPS = 9632
CORE_FREQUENCY_GROUPS = 128
BLOCK_COUNT = 76
ANGULAR_DIRECTION_COUNT = 32
RADIATION_DEPTH_CELL_COUNT = 4096
MATERIAL_CELL_COUNT = 128
RATE_QUADRATURE_ORDER_PER_GROUP = 16
ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FormalFeedbackPairProtocolSpec:
    phase: str
    phase_index: int
    classification: str
    confirmation_summary_path: str
    confirmation_protocol_path: str
    trial_residual_acceptance_path: str
    trial_material_summary_path: str
    trial_material_path: str
    base_feedback_summary_path: str
    base_residual_path: str
    physical_old_time_level_path: str
    phase7b7j_protocol_path: str
    phase7b7j_runner_path: str
    adapter_runner_path: str
    feedback_work_directory: str
    previous_feedback_output: str
    final_feedback_output: str
    target_material_output: str
    encoded_residual_output: str
    summary_path: str
    figure_path: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _read_json(root: Path, relative_path: str) -> dict[str, object]:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def _source(root: Path, relative_path: str) -> dict[str, object]:
    path = root / relative_path
    return {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def _require_exact_acceptance_gates(acceptance: dict[str, object]) -> None:
    gates = acceptance.get("gates", {})
    authorization = acceptance.get("authorization", {})
    required = {
        "consecutive_inner_radiation_state_count_at_least": 2,
        "each_global_original_operator_residual_below": 1.0e-4,
        "each_boundary_spectrum_l1_below": 1.0e-3,
        "each_boundary_bolometric_fraction_below": 1.0e-3,
        "each_formal_feedback_state_gate_passed": True,
        "maximum_last_two_photoionization_volume_l1_below": 1.0e-3,
        "maximum_last_two_total_recombination_volume_l1_below": 1.0e-3,
        "last_two_atomic_heating_volume_l1_below": 1.0e-3,
        "last_two_direct_heating_volume_l1_below": 1.0e-3,
        "last_two_formal_heating_volume_l1_below": 1.0e-3,
        "inner_noise_to_trial_signal_l2_ratio_below": 0.1,
        "candidate_to_base_residual_l2_ratio_below": 1.0,
        "candidate_to_base_mass_weighted_norm_ratio_below": 1.0,
        "candidate_to_base_maximum_cell_norm_ratio_below": 1.0,
        "candidate_state_must_match_frozen_phase7b9i_bytes": True,
        "minimum_population_fraction_at_least": 0.0,
        "all_residual_components_finite": True,
    }
    if any(gates.get(name) != value for name, value in required.items()):
        raise RuntimeError("trial-residual acceptance gates changed")
    if (
        authorization.get(
            "accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass"
        )
        is not True
        or authorization.get("reject_this_trial_if_any_gate_fails") is not True
        or authorization.get("accept_dynamic_nlte_solution") is not False
    ):
        raise RuntimeError("trial-residual acceptance authorization changed")


def _formal_state_gates() -> dict[str, object]:
    """Keep the already validated Phase 7B9f state-level thresholds unchanged."""
    return {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 9632,
        "minimum_comoving_mean_intensity_at_least": 0.0,
        "all_rates_and_arrays_finite": True,
        "all_atomic_rates_at_least": 0.0,
        "atomic_rate_vs_direct_comoving_heating_volume_l1_below": 1.0e-10,
        "atomic_rate_vs_inverse_four_force_volume_l1_below": 1.0e-3,
        "atomic_rate_vs_inverse_four_force_global_fraction_below": 1.0e-3,
        "maximum_parent_mirror_residual_below": 1.0e-8,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_state_wall_time_strictly_below_s": 900.0,
    }


def _converged_pair(
    root: Path,
    summary_path: str,
    protocol_path: str,
    acceptance: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    summary = _read_json(root, summary_path)
    protocol = _read_json(root, protocol_path)
    protocol_hash = sha256(root / protocol_path)
    decision = summary.get("decision", {})
    checks = summary.get("gate_checks", {})
    cfg = protocol.get("configuration", {})
    if (
        summary.get("protocol_sha256") != protocol_hash
        or decision.get("two_consecutive_fixed_matter_states_converged") is not True
        or decision.get("formal_h_he_feedback_pair_authorized") is not True
        or decision.get("material_feedback_evaluated") is not False
        or decision.get("dynamic_nlte_solution_accepted") is not False
        or not checks
        or any(value is not True for value in checks.values())
    ):
        raise RuntimeError("formal feedback requires a passed consecutive confirmation")
    pairs = (
        ("previous_converged_state_path", "previous_converged_state_sha256"),
        ("input_state_path", "input_state_sha256"),
    )
    if any(
        summary.get(path) != cfg.get(path)
        or summary.get(digest) != cfg.get(digest)
        for path, digest in pairs
    ):
        raise RuntimeError("consecutive confirmation state lineage changed")
    metrics = (
        (
            cfg.get("previous_global_original_operator_residual"),
            acceptance["gates"]["each_global_original_operator_residual_below"],
        ),
        (
            cfg.get("previous_boundary_spectrum_l1"),
            acceptance["gates"]["each_boundary_spectrum_l1_below"],
        ),
        (
            cfg.get("previous_boundary_bolometric_fraction"),
            acceptance["gates"]["each_boundary_bolometric_fraction_below"],
        ),
        (
            summary.get("input_global_original_operator_residual"),
            acceptance["gates"]["each_global_original_operator_residual_below"],
        ),
        (
            summary.get("input_boundary_spectrum_l1"),
            acceptance["gates"]["each_boundary_spectrum_l1_below"],
        ),
        (
            summary.get("input_boundary_bolometric_fraction"),
            acceptance["gates"]["each_boundary_bolometric_fraction_below"],
        ),
    )
    if any(value is None or float(value) >= float(limit) for value, limit in metrics):
        raise RuntimeError("consecutive radiation metrics do not satisfy acceptance")
    for path_key, hash_key in pairs:
        state = root / str(summary[path_key])
        if sha256(state) != summary[hash_key]:
            raise RuntimeError("converged radiation checkpoint hash changed")
    return summary, protocol


def build_formal_feedback_pair_protocol(
    root: Path,
    spec: FormalFeedbackPairProtocolSpec,
) -> dict[str, object]:
    """Build a frozen pair protocol; this function performs no feedback evaluation."""
    acceptance = _read_json(root, spec.trial_residual_acceptance_path)
    _require_exact_acceptance_gates(acceptance)
    confirmation, confirmation_protocol = _converged_pair(
        root,
        spec.confirmation_summary_path,
        spec.confirmation_protocol_path,
        acceptance,
    )
    trial = _read_json(root, spec.trial_material_summary_path)
    base = _read_json(root, spec.base_feedback_summary_path)
    if (
        trial.get("decision", {}).get("phase7b9i_material_gate_passed") is not True
        or trial.get("decision", {}).get("accepted_as_nonlinear_step") is not False
        or trial.get("trial_material_path") != spec.trial_material_path
        or trial.get("trial_material_sha256") != sha256(root / spec.trial_material_path)
        or base.get("decision", {}).get("phase7b9f_gate_passed") is not True
        or base.get("encoded_residual_path") != spec.base_residual_path
        or base.get("encoded_residual_sha256") != sha256(root / spec.base_residual_path)
    ):
        raise RuntimeError("trial material or frozen base residual lineage changed")
    previous_path = str(confirmation["previous_converged_state_path"])
    final_path = str(confirmation["input_state_path"])
    acceptance_gates = dict(acceptance["gates"])
    return {
        "phase": spec.phase,
        "protocol_version": 1,
        "classification": spec.classification,
        "sources": {
            "consecutive_confirmation_summary": _source(
                root, spec.confirmation_summary_path
            ),
            "consecutive_confirmation_protocol": _source(
                root, spec.confirmation_protocol_path
            ),
            "trial_residual_acceptance": _source(
                root, spec.trial_residual_acceptance_path
            ),
            "trial_material_summary": _source(root, spec.trial_material_summary_path),
            "trial_material": _source(root, spec.trial_material_path),
            "base_feedback_summary": _source(root, spec.base_feedback_summary_path),
            "base_residual": _source(root, spec.base_residual_path),
            "physical_old_time_level": _source(
                root, spec.physical_old_time_level_path
            ),
            "phase7b7j_protocol": _source(root, spec.phase7b7j_protocol_path),
            "phase7b7j_runner": _source(root, spec.phase7b7j_runner_path),
            "adapter_runner": _source(root, spec.adapter_runner_path),
            "previous_radiation": _source(root, previous_path),
            "final_radiation": _source(root, final_path),
        },
        "configuration": {
            "phase_index": spec.phase_index,
            "physical_frequency_groups": PHYSICAL_FREQUENCY_GROUPS,
            "core_frequency_groups": CORE_FREQUENCY_GROUPS,
            "block_count": BLOCK_COUNT,
            "angular_direction_count": ANGULAR_DIRECTION_COUNT,
            "radiation_depth_cell_count": RADIATION_DEPTH_CELL_COUNT,
            "material_cell_count": MATERIAL_CELL_COUNT,
            "rate_quadrature_order_per_group": RATE_QUADRATURE_ORDER_PER_GROUP,
            "maximum_concurrent_processes": 2,
            "feedback_work_directory": spec.feedback_work_directory,
            "previous_feedback_output": spec.previous_feedback_output,
            "final_feedback_output": spec.final_feedback_output,
            "target_material_output": spec.target_material_output,
            "encoded_residual_output": spec.encoded_residual_output,
            "summary_path": spec.summary_path,
            "figure_path": spec.figure_path,
            "previous_global_original_operator_residual": confirmation_protocol[
                "configuration"
            ]["previous_global_original_operator_residual"],
            "previous_boundary_spectrum_l1": confirmation_protocol["configuration"][
                "previous_boundary_spectrum_l1"
            ],
            "previous_boundary_bolometric_fraction": confirmation_protocol[
                "configuration"
            ]["previous_boundary_bolometric_fraction"],
            "final_global_original_operator_residual": confirmation[
                "input_global_original_operator_residual"
            ],
            "final_boundary_spectrum_l1": confirmation[
                "input_boundary_spectrum_l1"
            ],
            "final_boundary_bolometric_fraction": confirmation[
                "input_boundary_bolometric_fraction"
            ],
            "transport_or_source_iteration": False,
            "material_update": False,
            "radiation_update": False,
            "cellwise_clipping": False,
            "nan_to_num": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "formal_state_gates": _formal_state_gates(),
        "acceptance_gates": acceptance_gates,
        "authorization": {
            "evaluate_exactly_two_formal_feedback_states": True,
            "accept_finite_trial_only_if_all_acceptance_gates_pass": True,
            "reject_trial_if_any_gate_fails": True,
            "material_update_during_feedback_pair": False,
            "radiation_update_during_feedback_pair": False,
            "accept_dynamic_nlte_solution": False,
            "full_orbit": False,
            "phase4_replacement": False,
            "uvot": False,
            "real_line_formation": False,
        },
    }


def adapt_phase7b7j_worker_protocol(
    pair_protocol: dict[str, object],
    template: dict[str, object],
    state_label: str,
) -> dict[str, object]:
    """Adapt the validated 7B7j worker to one converged state and the trial matter."""
    if state_label not in {"previous", "final"}:
        raise ValueError("formal feedback state label must be previous or final")
    adapted = deepcopy(template)
    sources = adapted["sources"]
    pair_sources = pair_protocol["sources"]
    # 中文：辐射态和物质态必须成对替换，避免误用旧基准物质闭合。
    sources["mapped_radiation_state"] = dict(
        pair_sources[f"{state_label}_radiation"]
    )
    sources["second_material_iterate"] = dict(pair_sources["trial_material"])
    sources["physical_old_time_level"] = dict(
        pair_sources["physical_old_time_level"]
    )
    configuration = adapted["configuration"]
    pair_configuration = pair_protocol["configuration"]
    for name in (
        "physical_frequency_groups",
        "core_frequency_groups",
        "block_count",
        "angular_direction_count",
        "radiation_depth_cell_count",
        "rate_quadrature_order_per_group",
        "maximum_concurrent_processes",
    ):
        configuration[name] = pair_configuration[name]
    configuration["transport_or_source_iteration"] = False
    configuration["material_update"] = False
    configuration["radiation_update"] = False
    return adapted


def load_frozen_pair_protocol(
    protocol_path: Path,
    expected_sha256: str,
    *,
    validate_sources: bool,
) -> dict[str, object]:
    """Load one explicitly hash-pinned pair protocol."""
    if len(expected_sha256) != 64 or sha256(protocol_path) != expected_sha256:
        raise RuntimeError("frozen formal feedback-pair protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            path = ROOT / source["path"]
            if (
                path.stat().st_size != int(source["size_bytes"])
                or sha256(path) != source["sha256"]
            ):
                raise RuntimeError(
                    f"frozen formal feedback-pair source changed: {source['path']}"
                )
    return protocol


def _validate_worker_template_sources(
    pair_protocol: dict[str, object],
) -> dict[str, object]:
    """Validate the inherited 7B7j dependencies that the adapter does not replace."""
    template_path = ROOT / pair_protocol["sources"]["phase7b7j_protocol"]["path"]
    template = json.loads(template_path.read_text(encoding="utf-8"))
    replaced = {
        "mapped_radiation_state",
        "second_material_iterate",
        "physical_old_time_level",
    }
    for name, source in template["sources"].items():
        if name in replaced:
            continue
        path = ROOT / source["path"]
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"inherited Phase 7B7j source changed: {source['path']}")
    return template


def run_worker_adapter(
    protocol_path: Path,
    expected_sha256: str,
    state_label: str,
    block_index: int,
    partial_path: Path,
    report_path: Path,
) -> None:
    """Run one validated Phase 7B7j block against the selected converged pair state."""
    try:
        from scripts import phase7b7j_second_assembled_feedback as phase7b7j
    except ModuleNotFoundError as error:
        if error.name != "scripts":
            raise
        import phase7b7j_second_assembled_feedback as phase7b7j  # type: ignore[no-redef]

    pair_protocol = load_frozen_pair_protocol(
        protocol_path, expected_sha256, validate_sources=False
    )
    template_path = ROOT / pair_protocol["sources"]["phase7b7j_protocol"]["path"]
    template = json.loads(template_path.read_text(encoding="utf-8"))
    adapted = adapt_phase7b7j_worker_protocol(pair_protocol, template, state_label)
    # 中文：复用已验证的原子率 worker，只注入冻结辐射态和试步物质态。
    original_loader = phase7b7j._load_protocol
    try:
        phase7b7j._load_protocol = lambda _path, validate_sources=False: adapted
        phase7b7j.run_worker(template_path, block_index, partial_path, report_path)
    finally:
        phase7b7j._load_protocol = original_loader


def _feedback_manifest_path(protocol: dict[str, object], label: str) -> Path:
    return (
        ROOT
        / protocol["configuration"]["feedback_work_directory"]
        / f"{label}_manifest.json"
    )


def _run_feedback_state(
    protocol: dict[str, object],
    protocol_path: Path,
    expected_sha256: str,
    label: str,
) -> dict[str, object]:
    """Evaluate and recoverably assemble one formal feedback state."""
    try:
        from scripts import phase7b7f_assembled_diagnostics as phase7b7f
        from scripts import phase7b7j_second_assembled_feedback as phase7b7j
    except ModuleNotFoundError as error:
        if error.name != "scripts":
            raise
        import phase7b7f_assembled_diagnostics as phase7b7f  # type: ignore[no-redef]
        import phase7b7j_second_assembled_feedback as phase7b7j  # type: ignore[no-redef]

    cfg = protocol["configuration"]
    work = ROOT / cfg["feedback_work_directory"] / label
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = _feedback_manifest_path(protocol, label)
    state_source = protocol["sources"][f"{label}_radiation"]
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": expected_sha256,
            "state_label": label,
            "state_path": state_source["path"],
            "state_sha256": state_source["sha256"],
            "status": "running",
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if (
        manifest.get("protocol_sha256") != expected_sha256
        or manifest.get("state_label") != label
        or manifest.get("state_sha256") != state_source["sha256"]
    ):
        raise RuntimeError("formal feedback manifest lineage changed")
    if manifest["status"] == "complete":
        artifact = ROOT / manifest["feedback_artifact_path"]
        if sha256(artifact) != manifest["feedback_artifact_sha256"]:
            raise RuntimeError("completed formal feedback artifact changed")
        return manifest
    if manifest["status"] != "running":
        return manifest
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    for row in completed.values():
        partial = ROOT / row["partial_path"]
        if sha256(partial) != row["partial_sha256"]:
            raise RuntimeError("completed formal feedback partial changed")
    pending = [index for index in range(int(cfg["block_count"])) if index not in completed]
    concurrency = int(cfg["maximum_concurrent_processes"])
    runner = ROOT / protocol["sources"]["adapter_runner"]["path"]
    for offset in range(0, len(pending), concurrency):
        batch = pending[offset : offset + concurrency]
        started = time.perf_counter()
        processes = []
        report_paths = []
        for block_index in batch:
            partial = work / f"block{block_index:02d}.npz"
            report = work / f"block{block_index:02d}.json"
            report_paths.append(report)
            processes.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(runner),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
                        "--expected-protocol-sha256",
                        expected_sha256,
                        "--state-label",
                        label,
                        "--block-index",
                        str(block_index),
                        "--partial",
                        str(partial),
                        "--worker-report",
                        str(report),
                    ],
                    cwd=ROOT,
                )
            )
        codes = [process.wait() for process in processes]
        if any(code != 0 for code in codes):
            raise RuntimeError(f"formal feedback worker batch failed: {codes}")
        for block_index, report_path in zip(batch, report_paths, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if int(row["block_index"]) != block_index:
                raise RuntimeError("formal feedback worker block changed")
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["accumulated_wall_runtime_s"] = float(
            manifest["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        count = len(manifest["completed_blocks"])
        if count % 10 == 0 or count == int(cfg["block_count"]):
            print(
                json.dumps(
                    {"state": label, "completed_blocks": count, "total_blocks": cfg["block_count"]}
                ),
                flush=True,
            )
    records = manifest["completed_blocks"]
    combined = phase7b7j._zero(int(cfg["radiation_depth_cell_count"]))
    ownership = np.zeros(int(cfg["physical_frequency_groups"]), dtype=np.int64)
    for row in records:
        partial_path = ROOT / row["partial_path"]
        if sha256(partial_path) != row["partial_sha256"]:
            raise RuntimeError("formal feedback partial changed before assembly")
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
        with np.load(partial_path) as partial:
            for name in combined:
                combined[name] += np.asarray(partial[name])
    template = _validate_worker_template_sources(protocol)
    context = phase7b7f.phase7b7e.phase7b5x._context(template)
    following = int(context["following"])
    subedge = phase7b7f.phase7b7e.phase7b5x._subdivide_column_edge(
        context["full"]["edge_cm"][following], 16
    )
    subwidth = np.diff(subedge)
    rate = combined["atomic_rate_heating_erg_s_cm3"]
    direct = combined["source_direct_heating_erg_s_cm3"]
    formal = combined["source_formal_heating_erg_s_cm3"]
    rate_direct_l1, _, _, _ = phase7b7f._source_metrics(rate, direct, subwidth)
    frame_l1, frame_global, integrated_rate, integrated_formal = phase7b7f._source_metrics(
        rate, formal, subwidth
    )
    parent = {
        name: np.mean(array.reshape(256, 16, *array.shape[1:]), axis=1)
        for name, array in combined.items()
    }
    mirror = {name: phase7b7j._mirror_residual(array) for name, array in parent.items()}
    artifact_path = ROOT / cfg[f"{label}_feedback_output"]
    _write_npz_atomic(
        artifact_path,
        subcell_width_cm=subwidth,
        **{name: np.asarray(value) for name, value in combined.items()},
        **{f"parent_{name}": np.asarray(value) for name, value in parent.items()},
        **{f"half_{name}": np.asarray(value[:128]) for name, value in parent.items()},
    )
    atomic_names = (
        "photoionization_s1",
        "spontaneous_recombination_cm3_s",
        "stimulated_recombination_cm3_s",
        "total_recombination_cm3_s",
    )
    gates = protocol["formal_state_gates"]
    state_gate = bool(
        len(records) == gates["block_count_exactly"]
        and int(np.sum(ownership)) == gates["owned_frequency_group_count_exactly"]
        and np.all(ownership == 1)
        and min(float(row["minimum_owned_comoving_mean_intensity"]) for row in records)
        >= gates["minimum_comoving_mean_intensity_at_least"]
        and all(np.all(np.isfinite(value)) for value in combined.values())
        and all(np.all(combined[name] >= 0.0) for name in atomic_names)
        and rate_direct_l1
        < gates["atomic_rate_vs_direct_comoving_heating_volume_l1_below"]
        and frame_l1
        < gates["atomic_rate_vs_inverse_four_force_volume_l1_below"]
        and frame_global
        < gates["atomic_rate_vs_inverse_four_force_global_fraction_below"]
        and max(mirror.values()) < gates["maximum_parent_mirror_residual_below"]
        and max(float(row["peak_process_rss_mib"]) for row in records)
        < gates["each_process_peak_rss_strictly_below_mib"]
        and float(manifest["accumulated_wall_runtime_s"])
        < gates["each_state_wall_time_strictly_below_s"]
    )
    manifest.update(
        {
            "status": "complete" if state_gate else "gate_failed",
            "feedback_artifact_path": str(artifact_path.relative_to(ROOT)),
            "feedback_artifact_sha256": sha256(artifact_path),
            "rate_direct_volume_l1": rate_direct_l1,
            "rate_formal_volume_l1": frame_l1,
            "rate_formal_global_fraction": frame_global,
            "integrated_atomic_rate_heating_erg_s_cm2": integrated_rate,
            "integrated_formal_heating_erg_s_cm2": integrated_formal,
            "maximum_parent_mirror_residual": max(mirror.values()),
            "maximum_process_peak_rss_mib": max(
                float(row["peak_process_rss_mib"]) for row in records
            ),
            "state_gate_passed": state_gate,
        }
    )
    _write_json_atomic(manifest_path, manifest)
    return manifest


def _feedback_arrays(manifest: dict[str, object]) -> dict[str, np.ndarray]:
    path = ROOT / manifest["feedback_artifact_path"]
    with np.load(path) as artifact:
        return {name: np.array(artifact[name], copy=True) for name in artifact.files}


def _load_reused_feedback_manifest(
    protocol: dict[str, object],
    label: str,
    *,
    root: Path = ROOT,
) -> dict[str, object]:
    """载入经独立复现审计授权的完整 feedback artifact。"""
    if label not in {"previous", "final"}:
        raise ValueError("reused feedback label must be previous or final")
    cfg = protocol["configuration"]
    authorization = protocol["authorization"]
    if (
        cfg.get("reuse_completed_feedback_manifests") is not True
        or authorization.get("reuse_only_after_bytewise_reproduction_audit")
        is not True
    ):
        raise RuntimeError("feedback artifact reuse is not authorized")
    manifest_source = protocol["sources"][f"{label}_feedback_manifest"]
    artifact_source = protocol["sources"][f"{label}_feedback_artifact"]
    radiation_source = protocol["sources"][f"{label}_radiation"]
    manifest = json.loads((root / manifest_source["path"]).read_text(encoding="utf-8"))
    if (
        manifest.get("protocol_sha256")
        != cfg.get("feedback_origin_protocol_sha256")
        or manifest.get("status") != "complete"
        or manifest.get("state_gate_passed") is not True
        or manifest.get("state_path") != radiation_source["path"]
        or manifest.get("state_sha256") != radiation_source["sha256"]
        or manifest.get("feedback_artifact_path") != artifact_source["path"]
        or manifest.get("feedback_artifact_sha256") != artifact_source["sha256"]
    ):
        raise RuntimeError("reused formal feedback manifest lineage changed")
    return manifest


def _validated_frozen_trial_encoding(
    codec: GroundStateLogSimplexCodec,
    temperature: np.ndarray,
    hydrogen: np.ndarray,
    helium: np.ndarray,
    frozen_encoded: np.ndarray,
) -> np.ndarray:
    """验证物理数组是冻结编码的精确 decode，并返回原始编码字节。"""
    decoded = codec.decode(frozen_encoded)
    if (
        not np.array_equal(temperature, decoded.temperature_k)
        or not np.array_equal(hydrogen, decoded.hydrogen_fraction)
        or not np.array_equal(helium, decoded.helium_fraction)
    ):
        raise RuntimeError("frozen finite-trial decoded state changed")
    # 中文：log-simplex 的 encode(decode(x)) 非逐字可逆；残差必须使用冻结 x。
    return np.array(frozen_encoded, copy=True)


def _material_response_residual(
    protocol: dict[str, object],
    feedback: dict[str, np.ndarray],
) -> tuple[object, np.ndarray, dict[str, np.ndarray | float | int]]:
    trial_path = ROOT / protocol["sources"]["trial_material"]["path"]
    old_path = ROOT / protocol["sources"]["physical_old_time_level"]["path"]
    with np.load(trial_path) as trial:
        phase = int(trial["phase_index"])
        duration = float(trial["step_duration_s"])
        density = np.array(trial["density_g_cm3"], copy=True)
        temperature = np.array(trial["temperature_k"], copy=True)
        hydrogen = np.array(trial["hydrogen_fraction"], copy=True)
        helium = np.array(trial["helium_fraction"], copy=True)
        frozen_encoded = np.array(trial["encoded_state"], copy=True)
    with np.load(old_path) as old:
        if (
            duration != float(old["step_duration_s"][phase])
            or not np.array_equal(density, old["density_g_cm3"][phase])
        ):
            raise RuntimeError("formal feedback fixed physical time level changed")
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
        cell_mass = np.array(old["cell_mass_g_cm2"], copy=True)
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
    codec = GroundStateLogSimplexCodec(int(protocol["configuration"]["material_cell_count"]))
    encoded_trial = _validated_frozen_trial_encoding(
        codec, temperature, hydrogen, helium, frozen_encoded
    )
    response = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        feedback["half_photoionization_s1"],
        feedback["half_total_recombination_cm3_s"],
        feedback["half_atomic_rate_heating_erg_s_cm3"],
    )
    target = np.asarray(
        codec.encode(
            response.temperature_k,
            response.hydrogen_fraction,
            response.helium_fraction,
        )
    )
    residual = target - encoded_trial
    context: dict[str, np.ndarray | float | int] = {
        "phase": phase,
        "duration": duration,
        "density": density,
        "cell_mass": cell_mass,
        "mass_edge": mass_edge,
    }
    return response, residual, context


def _feedback_stability_comparison(
    previous_feedback: dict[str, np.ndarray],
    final_feedback: dict[str, np.ndarray],
) -> dict[str, object]:
    """在物质响应失败时仍独立保留两态正式 feedback 稳定性。"""
    previous_width = np.asarray(previous_feedback["subcell_width_cm"])
    final_width = np.asarray(final_feedback["subcell_width_cm"])
    if not np.array_equal(previous_width, final_width):
        raise RuntimeError("formal feedback pair subcell widths changed")
    return {
        "photoionization_volume_l1": weighted_volume_l1(
            previous_feedback["photoionization_s1"],
            final_feedback["photoionization_s1"],
            final_width,
        ).tolist(),
        "total_recombination_volume_l1": weighted_volume_l1(
            previous_feedback["total_recombination_cm3_s"],
            final_feedback["total_recombination_cm3_s"],
            final_width,
        ).tolist(),
        "atomic_heating_volume_l1": float(
            weighted_volume_l1(
                previous_feedback["atomic_rate_heating_erg_s_cm3"],
                final_feedback["atomic_rate_heating_erg_s_cm3"],
                final_width,
            )
        ),
        "direct_heating_volume_l1": float(
            weighted_volume_l1(
                previous_feedback["source_direct_heating_erg_s_cm3"],
                final_feedback["source_direct_heating_erg_s_cm3"],
                final_width,
            )
        ),
        "formal_heating_volume_l1": float(
            weighted_volume_l1(
                previous_feedback["source_formal_heating_erg_s_cm3"],
                final_feedback["source_formal_heating_erg_s_cm3"],
                final_width,
            )
        ),
    }


def _feedback_stability_gate_checks(
    comparison: dict[str, object], gates: dict[str, object]
) -> dict[str, bool]:
    return {
        "last_two_photoionization_pass": bool(
            np.max(comparison["photoionization_volume_l1"])
            < float(gates["maximum_last_two_photoionization_volume_l1_below"])
        ),
        "last_two_total_recombination_pass": bool(
            np.max(comparison["total_recombination_volume_l1"])
            < float(gates["maximum_last_two_total_recombination_volume_l1_below"])
        ),
        "last_two_atomic_heating_pass": bool(
            comparison["atomic_heating_volume_l1"]
            < float(gates["last_two_atomic_heating_volume_l1_below"])
        ),
        "last_two_direct_heating_pass": bool(
            comparison["direct_heating_volume_l1"]
            < float(gates["last_two_direct_heating_volume_l1_below"])
        ),
        "last_two_formal_heating_pass": bool(
            comparison["formal_heating_volume_l1"]
            < float(gates["last_two_formal_heating_volume_l1_below"])
        ),
    }


def _plot_material_domain_failure(
    path: Path,
    mass_edge: np.ndarray,
    previous_feedback: dict[str, np.ndarray],
    final_feedback: dict[str, np.ndarray],
    failures: dict[str, dict[str, str]],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mass_centre = 0.5 * (mass_edge[:-1] + mass_edge[1:])
    figure, axes = plt.subplots(1, 3, figsize=(14.0, 4.4), constrained_layout=True)
    for index, label in enumerate(("H I", "He I", "He II")):
        axes[0].semilogy(
            mass_centre,
            final_feedback["half_photoionization_s1"][:, index],
            label=label,
        )
    axes[0].set(
        xlabel="Mass fraction from surface",
        ylabel="Photoionization rate (s$^{-1}$)",
        title="(a) Final formal photoionization rates",
    )
    axes[0].legend(frameon=False)
    axes[1].plot(
        mass_centre,
        previous_feedback["half_atomic_rate_heating_erg_s_cm3"],
        label="Previous converged radiation",
    )
    axes[1].plot(
        mass_centre,
        final_feedback["half_atomic_rate_heating_erg_s_cm3"],
        ls="--",
        label="Final converged radiation",
    )
    axes[1].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(b) Last-two-state heating response",
    )
    axes[1].legend(frameon=False)
    axes[2].axis("off")
    lines = ["Finite material trial rejected", ""]
    lines.extend(
        f"{label}: {row['error_type']}\n{row['message']}"
        for label, row in failures.items()
    )
    lines.extend(("", "No clipping, floor, or target residual written."))
    axes[2].text(0.02, 0.98, "\n".join(lines), va="top", fontsize=10.0)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _plot_pair(
    path: Path,
    mass_edge: np.ndarray,
    previous_feedback: dict[str, np.ndarray],
    final_feedback: dict[str, np.ndarray],
    previous_residual: np.ndarray,
    final_residual: np.ndarray,
    checks: dict[str, bool],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mass_centre = 0.5 * (mass_edge[:-1] + mass_edge[1:])
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    for index, label in enumerate(("H I", "He I", "He II")):
        axes[0, 0].semilogy(
            mass_centre,
            final_feedback["half_photoionization_s1"][:, index],
            label=label,
        )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Photoionization rate (s$^{-1}$)",
        title="(a) Final formal H/He photoionization rates",
    )
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(
        mass_centre,
        previous_feedback["half_atomic_rate_heating_erg_s_cm3"],
        label="Previous converged state",
    )
    axes[0, 1].plot(
        mass_centre,
        final_feedback["half_atomic_rate_heating_erg_s_cm3"],
        ls="--",
        label="Final converged state",
    )
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(b) Last-two-state heating response",
    )
    axes[0, 1].legend(frameon=False)
    previous_cell = np.linalg.norm(previous_residual.reshape(-1, 4), axis=1)
    final_cell = np.linalg.norm(final_residual.reshape(-1, 4), axis=1)
    axes[1, 0].semilogy(mass_centre, previous_cell, label="Previous feedback")
    axes[1, 0].semilogy(mass_centre, final_cell, ls="--", label="Final feedback")
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Encoded residual cell norm",
        title="(c) Finite-trial true residual",
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 1].axis("off")
    failed = [name for name, passed in checks.items() if not passed]
    axes[1, 1].text(
        0.03,
        0.96,
        "(d) Frozen acceptance result\n\n"
        f"Passed checks = {sum(checks.values())}/{len(checks)}\n"
        f"Failed checks = {', '.join(failed) if failed else 'none'}\n\n"
        "No clipping, floor, point deletion,\n"
        "or post-hoc renormalization",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.0,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_pair(protocol_path: Path, expected_sha256: str) -> dict[str, object]:
    """Run the recoverable formal pair and evaluate one finite material trial."""
    protocol = load_frozen_pair_protocol(
        protocol_path, expected_sha256, validate_sources=True
    )
    _validate_worker_template_sources(protocol)
    summary_path = ROOT / protocol["configuration"]["summary_path"]
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("protocol_sha256") != expected_sha256:
            raise RuntimeError("formal feedback-pair summary lineage changed")
        return summary
    if protocol["configuration"].get("reuse_completed_feedback_manifests") is True:
        previous_manifest = _load_reused_feedback_manifest(protocol, "previous")
        final_manifest = _load_reused_feedback_manifest(protocol, "final")
    else:
        previous_manifest = _run_feedback_state(
            protocol, protocol_path, expected_sha256, "previous"
        )
        final_manifest = _run_feedback_state(
            protocol, protocol_path, expected_sha256, "final"
        )
    if previous_manifest["status"] != "complete" or final_manifest["status"] != "complete":
        raise RuntimeError("formal H/He feedback state gate failed")
    previous_feedback = _feedback_arrays(previous_manifest)
    final_feedback = _feedback_arrays(final_manifest)
    material_results: dict[str, tuple[object, np.ndarray, dict[str, object]]] = {}
    material_failures: dict[str, dict[str, str]] = {}
    for label, feedback in (
        ("previous", previous_feedback),
        ("final", final_feedback),
    ):
        try:
            material_results[label] = _material_response_residual(protocol, feedback)
        except (PhysicalDomainError, ArithmeticError) as error:
            material_failures[label] = {
                "error_type": type(error).__name__,
                "message": str(error),
            }
    acceptance_gates = protocol["acceptance_gates"]
    cfg = protocol["configuration"]
    if material_failures:
        comparison = _feedback_stability_comparison(
            previous_feedback, final_feedback
        )
        checks = _feedback_stability_gate_checks(comparison, acceptance_gates)
        checks.update(
            {
                "two_formal_feedback_states_pass": bool(
                    previous_manifest["state_gate_passed"]
                    and final_manifest["state_gate_passed"]
                ),
                "two_inner_radiation_residuals_pass": max(
                    float(cfg["previous_global_original_operator_residual"]),
                    float(cfg["final_global_original_operator_residual"]),
                )
                < float(
                    acceptance_gates["each_global_original_operator_residual_below"]
                ),
                "two_boundary_spectra_pass": max(
                    float(cfg["previous_boundary_spectrum_l1"]),
                    float(cfg["final_boundary_spectrum_l1"]),
                )
                < float(acceptance_gates["each_boundary_spectrum_l1_below"]),
                "two_boundary_bolometric_pass": max(
                    float(cfg["previous_boundary_bolometric_fraction"]),
                    float(cfg["final_boundary_bolometric_fraction"]),
                )
                < float(
                    acceptance_gates["each_boundary_bolometric_fraction_below"]
                ),
                "candidate_state_bytes_pass": True,
                "previous_material_response_physical_pass": (
                    "previous" not in material_failures
                ),
                "final_material_response_physical_pass": (
                    "final" not in material_failures
                ),
                "population_nonnegative_pass": False,
                "all_residual_components_finite_pass": False,
                "inner_noise_resolved_pass": False,
                "candidate_l2_contraction_pass": False,
                "candidate_mass_weighted_contraction_pass": False,
                "candidate_maximum_cell_contraction_pass": False,
            }
        )
        with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
            mass_edge = np.array(old["mass_fraction_edges"], copy=True)
        figure_path = ROOT / cfg["figure_path"]
        _plot_material_domain_failure(
            figure_path,
            mass_edge,
            previous_feedback,
            final_feedback,
            material_failures,
        )
        report = {
            "phase": protocol["phase"],
            "classification": "[A-preregistered]+[V-physical-domain]+[O]",
            "protocol_sha256": expected_sha256,
            "comparison": {
                **comparison,
                "inner_noise_to_trial_signal_l2_ratio": None,
                "candidate_to_base_residual_l2_ratio": None,
                "candidate_to_base_mass_weighted_norm_ratio": None,
                "candidate_to_base_maximum_cell_norm_ratio": None,
                "not_evaluated_reason": "finite material response left the physical domain",
            },
            "material_response_failures": material_failures,
            "previous_feedback": {
                key: previous_manifest[key]
                for key in (
                    "feedback_artifact_path",
                    "feedback_artifact_sha256",
                    "rate_direct_volume_l1",
                    "rate_formal_volume_l1",
                    "rate_formal_global_fraction",
                    "maximum_parent_mirror_residual",
                    "maximum_process_peak_rss_mib",
                    "accumulated_wall_runtime_s",
                )
            },
            "final_feedback": {
                key: final_manifest[key]
                for key in (
                    "feedback_artifact_path",
                    "feedback_artifact_sha256",
                    "rate_direct_volume_l1",
                    "rate_formal_volume_l1",
                    "rate_formal_global_fraction",
                    "maximum_parent_mirror_residual",
                    "maximum_process_peak_rss_mib",
                    "accumulated_wall_runtime_s",
                )
            },
            "target_material_path": None,
            "encoded_residual_path": None,
            "gate_checks": checks,
            "decision": {
                "formal_h_he_feedback_pair_passed": True,
                "finite_trial_accepted_as_one_nonlinear_step": False,
                "finite_trial_rejected": True,
                "static_approximation_rejected_from_one_failed_trial": False,
                "dynamic_nlte_solution_accepted": False,
                "phase4_replacement": False,
                "real_line_formation": False,
            },
            "figures": [figure_path.name],
        }
        _write_json_atomic(summary_path, report)
        return report
    previous_response, previous_residual, previous_context = material_results["previous"]
    final_response, final_residual, final_context = material_results["final"]
    if any(
        not np.array_equal(previous_context[name], final_context[name])
        for name in ("density", "cell_mass", "mass_edge")
    ):
        raise RuntimeError("formal feedback pair material context changed")
    base_residual = np.asarray(
        np.load(ROOT / protocol["sources"]["base_residual"]["path"])
    )
    diagnostics = trial_feedback_pair_diagnostics(
        previous_feedback=previous_feedback,
        final_feedback=final_feedback,
        previous_encoded_residual=previous_residual,
        final_encoded_residual=final_residual,
        base_encoded_residual=base_residual,
        cell_width=final_feedback["subcell_width_cm"],
        cell_mass=np.asarray(final_context["cell_mass"]),
    )
    checks = trial_feedback_pair_gate_checks(diagnostics, acceptance_gates)
    checks.update(
        {
            "two_formal_feedback_states_pass": bool(
                previous_manifest["state_gate_passed"]
                and final_manifest["state_gate_passed"]
            ),
            "two_inner_radiation_residuals_pass": max(
                float(cfg["previous_global_original_operator_residual"]),
                float(cfg["final_global_original_operator_residual"]),
            )
            < float(acceptance_gates["each_global_original_operator_residual_below"]),
            "two_boundary_spectra_pass": max(
                float(cfg["previous_boundary_spectrum_l1"]),
                float(cfg["final_boundary_spectrum_l1"]),
            )
            < float(acceptance_gates["each_boundary_spectrum_l1_below"]),
            "two_boundary_bolometric_pass": max(
                float(cfg["previous_boundary_bolometric_fraction"]),
                float(cfg["final_boundary_bolometric_fraction"]),
            )
            < float(acceptance_gates["each_boundary_bolometric_fraction_below"]),
            "candidate_state_bytes_pass": True,
            "population_nonnegative_pass": min(
                float(np.min(previous_response.hydrogen_fraction)),
                float(np.min(previous_response.helium_fraction)),
                float(np.min(final_response.hydrogen_fraction)),
                float(np.min(final_response.helium_fraction)),
            )
            >= float(acceptance_gates["minimum_population_fraction_at_least"]),
            "all_residual_components_finite_pass": bool(
                np.all(np.isfinite(previous_residual))
                and np.all(np.isfinite(final_residual))
            ),
        }
    )
    passed = all(checks.values())
    target_path = ROOT / cfg["target_material_output"]
    _write_npz_atomic(
        target_path,
        phase_index=np.array(final_context["phase"]),
        step_duration_s=np.array(final_context["duration"]),
        density_g_cm3=np.asarray(final_context["density"]),
        temperature_k=np.asarray(final_response.temperature_k),
        hydrogen_fraction=np.asarray(final_response.hydrogen_fraction),
        helium_fraction=np.asarray(final_response.helium_fraction),
        specific_material_energy_erg_g=np.asarray(
            final_response.recovered_specific_material_energy_erg_g
        ),
    )
    residual_path = ROOT / cfg["encoded_residual_output"]
    write_encoded_residual_atomic(residual_path, final_residual)
    figure_path = ROOT / cfg["figure_path"]
    _plot_pair(
        figure_path,
        np.asarray(final_context["mass_edge"]),
        previous_feedback,
        final_feedback,
        previous_residual,
        final_residual,
        checks,
    )
    candidate = diagnostics.candidate_norms
    base = diagnostics.base_norms
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": expected_sha256,
        "comparison": {
            "photoionization_volume_l1": diagnostics.photoionization_volume_l1.tolist(),
            "total_recombination_volume_l1": diagnostics.total_recombination_volume_l1.tolist(),
            "atomic_heating_volume_l1": diagnostics.atomic_heating_volume_l1,
            "direct_heating_volume_l1": diagnostics.direct_heating_volume_l1,
            "formal_heating_volume_l1": diagnostics.formal_heating_volume_l1,
            "inner_noise_to_trial_signal_l2_ratio": (
                diagnostics.inner_noise_to_trial_signal_l2_ratio
            ),
            "candidate_to_base_residual_l2_ratio": candidate.l2 / base.l2,
            "candidate_to_base_mass_weighted_norm_ratio": candidate.mass_weighted
            / base.mass_weighted,
            "candidate_to_base_maximum_cell_norm_ratio": candidate.maximum_cell
            / base.maximum_cell,
        },
        "previous_feedback": {
            key: previous_manifest[key]
            for key in (
                "feedback_artifact_path",
                "feedback_artifact_sha256",
                "rate_direct_volume_l1",
                "rate_formal_volume_l1",
                "rate_formal_global_fraction",
                "maximum_parent_mirror_residual",
                "maximum_process_peak_rss_mib",
                "accumulated_wall_runtime_s",
            )
        },
        "final_feedback": {
            key: final_manifest[key]
            for key in (
                "feedback_artifact_path",
                "feedback_artifact_sha256",
                "rate_direct_volume_l1",
                "rate_formal_volume_l1",
                "rate_formal_global_fraction",
                "maximum_parent_mirror_residual",
                "maximum_process_peak_rss_mib",
                "accumulated_wall_runtime_s",
            )
        },
        "target_material_path": str(target_path.relative_to(ROOT)),
        "target_material_sha256": sha256(target_path),
        "encoded_residual_path": str(residual_path.relative_to(ROOT)),
        "encoded_residual_sha256": sha256(residual_path),
        "gate_checks": checks,
        "decision": {
            "formal_h_he_feedback_pair_passed": bool(
                previous_manifest["state_gate_passed"]
                and final_manifest["state_gate_passed"]
            ),
            "finite_trial_accepted_as_one_nonlinear_step": passed,
            "finite_trial_rejected": not passed,
            "static_approximation_rejected_from_one_failed_trial": False,
            "dynamic_nlte_solution_accepted": False,
            "phase4_replacement": False,
            "real_line_formation": False,
        },
        "figures": [figure_path.name],
    }
    _write_json_atomic(summary_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--expected-protocol-sha256")
    parser.add_argument("--state-label", choices=("previous", "final"))
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.protocol is None or args.expected_protocol_sha256 is None:
        parser.error("protocol and expected protocol hash are required")
    if args.worker:
        required = (
            args.state_label,
            args.block_index,
            args.partial,
            args.worker_report,
        )
        if any(value is None for value in required):
            parser.error("worker mode requires state, block, partial, and report")
        run_worker_adapter(
            args.protocol,
            args.expected_protocol_sha256,
            args.state_label,
            args.block_index,
            args.partial,
            args.worker_report,
        )
        return
    print(json.dumps(run_pair(args.protocol, args.expected_protocol_sha256), indent=2))


if __name__ == "__main__":
    main()
