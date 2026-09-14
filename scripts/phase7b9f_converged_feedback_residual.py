"""Phase 7B9f：比较最后两态的正式 H/He 反馈并形成基准物质残差。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)
from eccentric_tde_observer.full_frequency_residual_evaluation import (
    FullFrequencyResidualFidelity,
    FullFrequencyResidualStatus,
    RecoverableFullFrequencyResidualEvaluation,
    build_full_frequency_residual_request,
    write_encoded_residual_atomic,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)
from eccentric_tde_observer.source import PhysicalDomainError

try:
    from scripts import phase7b7f_assembled_diagnostics as phase7b7f
    from scripts import phase7b7j_second_assembled_feedback as phase7b7j
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b7f_assembled_diagnostics as phase7b7f  # type: ignore[no-redef]
    import phase7b7j_second_assembled_feedback as phase7b7j  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "0a665c8dccb1fa59c0e9939d2ded5d5d1dd0c9e7ed9430ac4c466e8b3007398e"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _load_protocol(path: Path, *, validate_sources: bool) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9f protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if validate_sources:
        for source in protocol["sources"].values():
            source_path = ROOT / source["path"]
            if (
                source_path.stat().st_size != int(source["size_bytes"])
                or _sha256(source_path) != source["sha256"]
            ):
                raise RuntimeError(f"frozen Phase 7B9f source changed: {source['path']}")
    return protocol


def run_worker(
    protocol_path: Path,
    state_label: str,
    block_index: int,
    partial_path: Path,
    report_path: Path,
) -> None:
    protocol = _load_protocol(protocol_path, validate_sources=False)
    if state_label not in ("previous", "final"):
        raise ValueError("Phase 7B9f state label is invalid")
    old_protocol_path = ROOT / protocol["sources"]["phase7b7j_protocol"]["path"]
    template = json.loads(old_protocol_path.read_text(encoding="utf-8"))
    template["sources"]["mapped_radiation_state"] = dict(
        protocol["sources"][f"{state_label}_radiation"]
    )
    # 中文：沿用已验证的正式反馈 worker，只替换已冻结的全局辐射态。
    phase7b7j._load_protocol = lambda _path, validate_sources=False: template
    phase7b7j.run_worker(old_protocol_path, block_index, partial_path, report_path)


def _feedback_manifest_path(protocol: dict[str, object], label: str) -> Path:
    return (
        ROOT
        / protocol["configuration"]["feedback_work_directory"]
        / f"{label}_manifest.json"
    )


def _run_feedback_state(
    protocol: dict[str, object], protocol_path: Path, label: str
) -> dict[str, object]:
    configuration = protocol["configuration"]
    work = ROOT / configuration["feedback_work_directory"] / label
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = _feedback_manifest_path(protocol, label)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "phase": protocol["phase"],
            "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
            "state_label": label,
            "state_path": protocol["sources"][f"{label}_radiation"]["path"],
            "state_sha256": protocol["sources"][f"{label}_radiation"]["sha256"],
            "status": "running",
            "completed_blocks": [],
            "accumulated_wall_runtime_s": 0.0,
        }
        _write_json_atomic(manifest_path, manifest)
    if (
        manifest["protocol_sha256"] != EXPECTED_PROTOCOL_SHA256
        or manifest["state_label"] != label
        or manifest["state_sha256"]
        != protocol["sources"][f"{label}_radiation"]["sha256"]
    ):
        raise RuntimeError("Phase 7B9f feedback manifest changed")
    if manifest["status"] == "complete":
        artifact = ROOT / manifest["feedback_artifact_path"]
        if _sha256(artifact) != manifest["feedback_artifact_sha256"]:
            raise RuntimeError("Phase 7B9f completed feedback changed")
        return manifest
    completed = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    for row in completed.values():
        partial = ROOT / row["partial_path"]
        if _sha256(partial) != row["partial_sha256"]:
            raise RuntimeError("Phase 7B9f completed partial changed")
    block_count = int(configuration["block_count"])
    pending = [index for index in range(block_count) if index not in completed]
    concurrency = int(configuration["maximum_concurrent_processes"])
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
                        str(Path(__file__).resolve()),
                        "--worker",
                        "--protocol",
                        str(protocol_path),
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
        return_codes = [process.wait() for process in processes]
        if any(code != 0 for code in return_codes):
            raise RuntimeError(f"Phase 7B9f worker batch failed: {return_codes}")
        for block_index, report_path in zip(batch, report_paths, strict=True):
            row = json.loads(report_path.read_text(encoding="utf-8"))
            if int(row["block_index"]) != block_index:
                raise RuntimeError("Phase 7B9f worker block changed")
            manifest["completed_blocks"].append(row)
        manifest["completed_blocks"].sort(key=lambda row: int(row["block_index"]))
        manifest["accumulated_wall_runtime_s"] = float(
            manifest["accumulated_wall_runtime_s"]
        ) + (time.perf_counter() - started)
        _write_json_atomic(manifest_path, manifest)
        count = len(manifest["completed_blocks"])
        if count % 10 == 0 or count == block_count:
            print(
                json.dumps(
                    {"state": label, "completed_blocks": count, "total_blocks": block_count}
                ),
                flush=True,
            )
    records = manifest["completed_blocks"]
    depth = int(configuration["radiation_depth_cell_count"])
    combined = phase7b7j._zero(depth)
    ownership = np.zeros(int(configuration["physical_frequency_groups"]), dtype=np.int64)
    for row in records:
        partial_path = ROOT / row["partial_path"]
        if _sha256(partial_path) != row["partial_sha256"]:
            raise RuntimeError("Phase 7B9f partial hash changed before assembly")
        ownership[int(row["core_group_start"]) : int(row["core_group_stop"])] += 1
        with np.load(partial_path) as partial:
            for name in combined:
                combined[name] += np.asarray(partial[name])
    old_protocol = json.loads(
        (ROOT / protocol["sources"]["phase7b7j_protocol"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    context = phase7b7f.phase7b7e.phase7b5x._context(old_protocol)
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
    artifact_path = ROOT / configuration[f"{label}_feedback_output"]
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
    gates = protocol["gates"]
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
            "feedback_artifact_sha256": _sha256(artifact_path),
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


def _weighted_l1(
    previous: np.ndarray, final: np.ndarray, width: np.ndarray
) -> np.ndarray:
    if previous.shape != final.shape or previous.shape[0] != width.size:
        raise ValueError("Phase 7B9f convergence arrays have inconsistent shapes")
    trailing = tuple(range(1, previous.ndim))
    weight = width.reshape((width.size,) + (1,) * len(trailing))
    numerator = np.sum(weight * np.abs(final - previous), axis=0)
    denominator = np.sum(
        weight * np.maximum(np.abs(previous), np.abs(final)), axis=0
    )
    residual = np.array(numerator, copy=True, dtype=np.float64)
    np.divide(numerator, denominator, out=residual, where=denominator > 0.0)
    return residual


def _prepare_recoverable_residual(
    protocol: dict[str, object], protocol_path: Path, feedback_path: Path,
    residual_path: Path, feedback_gate: bool, feedback_wall_runtime_s: float,
) -> RecoverableFullFrequencyResidualEvaluation:
    configuration = protocol["configuration"]
    ranges = tuple(
        (start, min(start + int(configuration["core_frequency_groups"]), 9632))
        for start in range(0, 9632, int(configuration["core_frequency_groups"]))
    )
    request = build_full_frequency_residual_request(
        ROOT,
        evaluation_id="phase7b9f-base-state",
        fidelity=FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION,
        encoded_unknown_count=int(configuration["encoded_unknown_count"]),
        radiation_shape=(9632, 32, 4096),
        frequency_block_ranges=ranges,
        radiation_output_path=ROOT / protocol["sources"]["final_radiation"]["path"],
        radiation_inner_residual_tolerance=1.0e-4,
        input_artifact_paths={
            "frozen_protocol": protocol_path,
            "encoded_material_state": ROOT
            / protocol["sources"]["encoded_material_state"]["path"],
            "decoded_material_state": ROOT
            / protocol["sources"]["current_material_state"]["path"],
            "physical_old_time_level": ROOT
            / protocol["sources"]["physical_old_time_level"]["path"],
            "initial_radiation_checkpoint": ROOT
            / protocol["sources"]["previous_radiation"]["path"],
        },
    )
    manifest_path = ROOT / configuration["recoverable_residual_manifest"]
    if manifest_path.exists():
        evaluation = RecoverableFullFrequencyResidualEvaluation.resume(ROOT, manifest_path)
    else:
        evaluation = RecoverableFullFrequencyResidualEvaluation.create(
            ROOT, manifest_path, request
        )
        evaluation.start_radiation()
        for block_index in range(len(ranges)):
            evaluation.mark_frequency_block_complete(block_index)
        upstream = json.loads(
            (ROOT / protocol["sources"]["phase7b9e2_summary"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        evaluation.complete_radiation(
            inner_iteration_count=int(upstream["final_additional_map"]),
            inner_residual_norm=float(upstream["final_global_source_map_residual"]),
            inner_converged=True,
            science_functionals_passed=True,
            wall_runtime_s=float(
                sum(row["wall_runtime_s"] for row in upstream["history"])
            ),
        )
    if evaluation.status is FullFrequencyResidualStatus.RADIATION_COMPLETE:
        evaluation.complete_feedback(
            feedback_path,
            source_consistency_passed=feedback_gate,
            conservation_passed=feedback_gate,
            wall_runtime_s=feedback_wall_runtime_s,
        )
    if (
        evaluation.status is FullFrequencyResidualStatus.FEEDBACK_COMPLETE
        and feedback_gate
    ):
        evaluation.complete_material_residual(residual_path)
    return evaluation


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    previous: dict[str, np.ndarray],
    final: dict[str, np.ndarray],
    comparison: dict[str, object],
    residual: np.ndarray,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.6, 8.1), constrained_layout=True)
    for index, label in enumerate(("H I", "He I", "He II")):
        axes[0, 0].semilogy(
            mass_centre,
            final["half_photoionization_s1"][:, index],
            label=label,
        )
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Photoionization rate (s$^{-1}$)",
        title="(a) Final assembled H/He photoionization rates",
    )
    axes[0, 0].legend(frameon=False)
    for name, label, style in (
        ("half_atomic_rate_heating_erg_s_cm3", "Atomic-rate heating", "-"),
        ("half_source_direct_heating_erg_s_cm3", "Direct comoving source", "--"),
        ("half_source_formal_heating_erg_s_cm3", "Inverse lab four-force", ":"),
    ):
        axes[0, 1].plot(mass_centre, final[name], ls=style, label=label)
    heating_scale = max(
        float(np.max(np.abs(final[name])))
        for name in (
            "half_atomic_rate_heating_erg_s_cm3",
            "half_source_direct_heating_erg_s_cm3",
            "half_source_formal_heating_erg_s_cm3",
        )
    )
    if heating_scale > 0.0:
        axes[0, 1].set_yscale("symlog", linthresh=heating_scale * 1.0e-2)
    axes[0, 1].set(
        xlabel="Mass fraction from surface",
        ylabel="Material heating (erg s$^{-1}$ cm$^{-3}$)",
        title="(b) Final formal-source identity",
    )
    axes[0, 1].legend(frameon=False, fontsize=8.5)
    component = residual.reshape(-1, 4)
    for index, label in enumerate(
        ("Log thermal energy", "Log H II/H I", "Log He II/He I", "Log He III/He I")
    ):
        axes[1, 0].plot(mass_centre, component[:, index], label=label)
    axes[1, 0].axhline(0.0, color="0.25", ls=":")
    axes[1, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Encoded fixed-point residual",
        title="(c) Physical base Newton residual",
    )
    axes[1, 0].legend(frameon=False, fontsize=8.2)
    axes[1, 1].axis("off")
    photo = comparison["photoionization_volume_l1"]
    recombination = comparison["total_recombination_volume_l1"]
    axes[1, 1].text(
        0.03,
        0.96,
        "(d) Last-two-state feedback convergence\n\n"
        f"Max photoionization L1 = {max(photo):.3e}\n"
        f"Max total recombination L1 = {max(recombination):.3e}\n"
        f"Atomic-heating L1 = {comparison['atomic_heating_volume_l1']:.3e}\n"
        f"Direct-heating L1 = {comparison['direct_heating_volume_l1']:.3e}\n"
        f"Formal-heating L1 = {comparison['formal_heating_volume_l1']:.3e}\n"
        f"Residual L2 norm = {np.linalg.norm(residual):.3e}\n\n"
        "No clipping, floor, point deletion, or renormalization",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=10.2,
    )
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path, validate_sources=True)
    summary_path = OUTPUT / "phase7b9f_converged_feedback_residual_summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    previous_manifest = _run_feedback_state(protocol, protocol_path, "previous")
    final_manifest = _run_feedback_state(protocol, protocol_path, "final")
    if previous_manifest["status"] != "complete" or final_manifest["status"] != "complete":
        raise RuntimeError("Phase 7B9f formal feedback state gate failed")
    with np.load(ROOT / previous_manifest["feedback_artifact_path"]) as previous_file:
        previous = {name: np.array(previous_file[name], copy=True) for name in previous_file.files}
    with np.load(ROOT / final_manifest["feedback_artifact_path"]) as final_file:
        final = {name: np.array(final_file[name], copy=True) for name in final_file.files}
    width = final["subcell_width_cm"]
    photo_l1 = _weighted_l1(
        previous["photoionization_s1"], final["photoionization_s1"], width
    )
    recombination_l1 = _weighted_l1(
        previous["total_recombination_cm3_s"],
        final["total_recombination_cm3_s"],
        width,
    )
    atomic_l1 = float(
        _weighted_l1(
            previous["atomic_rate_heating_erg_s_cm3"],
            final["atomic_rate_heating_erg_s_cm3"],
            width,
        )
    )
    direct_l1 = float(
        _weighted_l1(
            previous["source_direct_heating_erg_s_cm3"],
            final["source_direct_heating_erg_s_cm3"],
            width,
        )
    )
    formal_l1 = float(
        _weighted_l1(
            previous["source_formal_heating_erg_s_cm3"],
            final["source_formal_heating_erg_s_cm3"],
            width,
        )
    )
    gates = protocol["gates"]
    feedback_pair_gate = bool(
        np.max(photo_l1) < gates["last_two_photoionization_volume_l1_below"]
        and np.max(recombination_l1)
        < gates["last_two_total_recombination_volume_l1_below"]
        and atomic_l1 < gates["last_two_atomic_heating_volume_l1_below"]
        and direct_l1 < gates["last_two_direct_heating_volume_l1_below"]
        and formal_l1 < gates["last_two_formal_heating_volume_l1_below"]
    )
    configuration = protocol["configuration"]
    with np.load(ROOT / protocol["sources"]["current_material_state"]["path"]) as current:
        phase = int(current["phase_index"])
        duration = float(current["step_duration_s"])
        density = np.array(current["density_g_cm3"], copy=True)
        temperature = np.array(current["temperature_k"], copy=True)
        hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        helium = np.array(current["helium_fraction"], copy=True)
    with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
        if (
            duration != float(old["step_duration_s"][phase])
            or not np.array_equal(density, old["density_g_cm3"][phase])
        ):
            raise RuntimeError("Phase 7B9f fixed physical time level changed")
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
    response = frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        final["half_photoionization_s1"],
        final["half_total_recombination_cm3_s"],
        final["half_atomic_rate_heating_erg_s_cm3"],
    )
    codec = GroundStateLogSimplexCodec(int(configuration["material_cell_count"]))
    encoded_current = np.asarray(codec.encode(temperature, hydrogen, helium))
    frozen_encoded = np.asarray(
        np.load(ROOT / protocol["sources"]["encoded_material_state"]["path"])
    )
    if not np.array_equal(encoded_current, frozen_encoded):
        raise RuntimeError("Phase 7B9f encoded base material changed")
    encoded_target = np.asarray(
        codec.encode(
            response.temperature_k,
            response.hydrogen_fraction,
            response.helium_fraction,
        )
    )
    residual = encoded_target - encoded_current
    if not np.all(np.isfinite(residual)):
        raise PhysicalDomainError("Phase 7B9f base material residual is non-finite")
    target_path = ROOT / configuration["target_material_output"]
    _write_npz_atomic(
        target_path,
        phase_index=np.array(phase),
        step_duration_s=np.array(duration),
        density_g_cm3=density,
        temperature_k=np.asarray(response.temperature_k),
        hydrogen_fraction=np.asarray(response.hydrogen_fraction),
        helium_fraction=np.asarray(response.helium_fraction),
        specific_material_energy_erg_g=np.asarray(
            response.recovered_specific_material_energy_erg_g
        ),
        encoded_state=encoded_target,
    )
    residual_path = ROOT / configuration["encoded_residual_output"]
    write_encoded_residual_atomic(residual_path, residual)
    formal_gate = bool(
        previous_manifest["state_gate_passed"]
        and final_manifest["state_gate_passed"]
        and feedback_pair_gate
    )
    evaluation = _prepare_recoverable_residual(
        protocol,
        protocol_path,
        ROOT / final_manifest["feedback_artifact_path"],
        residual_path,
        formal_gate,
        float(final_manifest["accumulated_wall_runtime_s"]),
    )
    comparison = {
        "photoionization_volume_l1": photo_l1.tolist(),
        "total_recombination_volume_l1": recombination_l1.tolist(),
        "atomic_heating_volume_l1": atomic_l1,
        "direct_heating_volume_l1": direct_l1,
        "formal_heating_volume_l1": formal_l1,
    }
    figure_path = OUTPUT / "phase7b9f_converged_feedback_residual.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        previous,
        final,
        comparison,
        residual,
    )
    decision = {
        "frozen_protocol_sources_and_radiation_hashes_passed": True,
        "previous_formal_feedback_gate_passed": previous_manifest["state_gate_passed"],
        "final_formal_feedback_gate_passed": final_manifest["state_gate_passed"],
        "last_two_h_he_rate_and_heating_gate_passed": feedback_pair_gate,
        "physical_material_response_exists": True,
        "recoverable_inner_converged_residual_complete": evaluation.status
        is FullFrequencyResidualStatus.COMPLETE,
        "full_frequency_jv_evaluated": False,
        "newton_step_performed": False,
        "accepted_as_dynamic_NLTE_solution": False,
        "phase7b9f_gate_passed": bool(
            formal_gate and evaluation.status is FullFrequencyResidualStatus.COMPLETE
        ),
        "one_preconditioned_full_frequency_jv_decision_authorized": bool(
            formal_gate and evaluation.status is FullFrequencyResidualStatus.COMPLETE
        ),
    }
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "comparison": comparison,
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
        "target_material_sha256": _sha256(target_path),
        "encoded_residual_path": str(residual_path.relative_to(ROOT)),
        "encoded_residual_sha256": _sha256(residual_path),
        "encoded_residual_l2_norm": float(np.linalg.norm(residual)),
        "encoded_residual_maximum_absolute_component": float(np.max(np.abs(residual))),
        "recoverable_residual_manifest": str(evaluation.manifest_path.relative_to(ROOT)),
        "recoverable_residual_status": evaluation.status.value,
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(summary_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9f_preregistered_converged_feedback_residual.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--state-label", choices=("previous", "final"))
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if any(
            value is None
            for value in (
                args.state_label,
                args.block_index,
                args.partial,
                args.worker_report,
            )
        ):
            parser.error("worker mode requires state, block, partial, and report")
        run_worker(
            args.protocol,
            args.state_label,
            args.block_index,
            args.partial,
            args.worker_report,
        )
        return
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
