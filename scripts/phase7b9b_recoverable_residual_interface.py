"""Phase 7B9b：验证可恢复全频残差的保真度和文件状态机。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from eccentric_tde_observer.full_frequency_residual_evaluation import (
    FullFrequencyResidualFidelity,
    FullFrequencyResidualStatus,
    RecoverableFullFrequencyResidualEvaluation,
    build_full_frequency_residual_request,
    write_encoded_residual_atomic,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "962aee72870cf4c2aa3f5bda607c6fe391c381dc8b7d65d37060c0472852cc0d"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9b protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B9b source changed: {source['path']}")
    return protocol


def _new_evaluation(
    directory: Path,
    fidelity: FullFrequencyResidualFidelity,
) -> RecoverableFullFrequencyResidualEvaluation:
    inputs = {}
    for index, name in enumerate(
        (
            "frozen_protocol",
            "encoded_material_state",
            "decoded_material_state",
            "physical_old_time_level",
            "initial_radiation_checkpoint",
        )
    ):
        path = directory / f"{name}.dat"
        path.write_bytes(f"phase7b9b-control-{index}".encode())
        inputs[name] = path
    request = build_full_frequency_residual_request(
        directory,
        evaluation_id=f"control-{fidelity.value}",
        fidelity=fidelity,
        encoded_unknown_count=8,
        radiation_shape=(4, 2, 3),
        frequency_block_ranges=((0, 2), (2, 4)),
        radiation_output_path=directory / "radiation.dat",
        radiation_inner_residual_tolerance=1.0e-6,
        input_artifact_paths=inputs,
    )
    evaluation = RecoverableFullFrequencyResidualEvaluation.create(
        directory, directory / "manifest.json", request
    )
    np.arange(24, dtype=np.float64).tofile(directory / "radiation.dat")
    evaluation.start_radiation()
    return evaluation


def _mark_all_blocks(evaluation: RecoverableFullFrequencyResidualEvaluation) -> None:
    evaluation.mark_frequency_block_complete(0)
    evaluation.mark_frequency_block_complete(1)


def _add_feedback(evaluation: RecoverableFullFrequencyResidualEvaluation) -> None:
    feedback = evaluation.workspace_root / "feedback.npz"
    np.savez(feedback, formal_rate=np.array([1.0], dtype=np.float64))
    evaluation.complete_feedback(
        feedback,
        source_consistency_passed=True,
        conservation_passed=True,
        wall_runtime_s=0.1,
    )


def _run_controls(root: Path) -> dict[str, bool | float]:
    partial_dir = root / "partial"
    partial_dir.mkdir()
    partial = _new_evaluation(
        partial_dir, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    partial.mark_frequency_block_complete(0)
    partial_rejected = False
    try:
        partial.radiation_checkpoint_for_feedback()
    except RuntimeError:
        partial_rejected = True

    tamper_dir = root / "tamper"
    tamper_dir.mkdir()
    tamper = _new_evaluation(
        tamper_dir, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    tamper.mark_frequency_block_complete(0)
    checkpoint = np.memmap(
        tamper_dir / "radiation.dat", mode="r+", dtype=np.float64, shape=(4, 2, 3)
    )
    checkpoint[0, 0, 0] += 1.0
    checkpoint.flush()
    del checkpoint
    completed_block_tamper_rejected = False
    try:
        RecoverableFullFrequencyResidualEvaluation.resume(
            tamper_dir, tamper_dir / "manifest.json"
        )
    except RuntimeError:
        completed_block_tamper_rejected = True

    diagnostic_dir = root / "diagnostic"
    diagnostic_dir.mkdir()
    diagnostic = _new_evaluation(
        diagnostic_dir, FullFrequencyResidualFidelity.ONE_MAP_DIAGNOSTIC
    )
    _mark_all_blocks(diagnostic)
    diagnostic.complete_radiation(
        inner_iteration_count=1,
        inner_residual_norm=0.2,
        inner_converged=False,
        science_functionals_passed=True,
        wall_runtime_s=0.1,
    )
    _add_feedback(diagnostic)
    write_encoded_residual_atomic(
        diagnostic_dir / "residual.npy", np.linspace(-0.2, 0.2, 8)
    )
    diagnostic.complete_material_residual(diagnostic_dir / "residual.npy")
    one_map_newton_rejected = False
    try:
        diagnostic.load_newton_residual()
    except RuntimeError:
        one_map_newton_rejected = True

    converged_dir = root / "converged"
    converged_dir.mkdir()
    converged = _new_evaluation(
        converged_dir, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    _mark_all_blocks(converged)
    converged.complete_radiation(
        inner_iteration_count=3,
        inner_residual_norm=5.0e-7,
        inner_converged=True,
        science_functionals_passed=True,
        wall_runtime_s=0.2,
    )
    _add_feedback(converged)
    expected = np.linspace(-0.3, 0.4, 8)
    write_encoded_residual_atomic(converged_dir / "residual.npy", expected)
    converged.complete_material_residual(converged_dir / "residual.npy")
    recovered = RecoverableFullFrequencyResidualEvaluation.resume(
        converged_dir, converged_dir / "manifest.json"
    )
    inner_converged_newton_load_exact = bool(
        recovered.status is FullFrequencyResidualStatus.COMPLETE
        and np.array_equal(recovered.load_newton_residual(), expected)
    )

    failure_dir = root / "physical_failure"
    failure_dir.mkdir()
    failed = _new_evaluation(
        failure_dir, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    failed.record_failure(
        physical_domain=True,
        stage="decode_material_response",
        exception_type="PhysicalDomainError",
        message="specific material energy leaves no positive gas heat",
    )
    failed_recovered = RecoverableFullFrequencyResidualEvaluation.resume(
        failure_dir, failure_dir / "manifest.json"
    )
    physical_domain_failure_terminal = bool(
        failed_recovered.status is FullFrequencyResidualStatus.FAILED_PHYSICAL_DOMAIN
        and failed_recovered.payload["failure"]["physical_domain"]
    )

    manifest = converged_dir / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload["feedback"]["source_consistency_passed"] = False
    manifest.write_text(json.dumps(payload))
    manifest_tamper_rejected = False
    try:
        RecoverableFullFrequencyResidualEvaluation.resume(converged_dir, manifest)
    except RuntimeError:
        manifest_tamper_rejected = True

    return {
        "partial_checkpoint_rejected": partial_rejected,
        "completed_block_tamper_rejected": completed_block_tamper_rejected,
        "one_map_newton_load_rejected": one_map_newton_rejected,
        "inner_converged_newton_load_exact": inner_converged_newton_load_exact,
        "physical_domain_failure_terminal": physical_domain_failure_terminal,
        "manifest_tamper_rejected": manifest_tamper_rejected,
    }


def _plot(path: Path, controls: dict[str, bool | float], cost_s: float, jv_count: int) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.2), constrained_layout=True)
    axis = axes[0, 0]
    axis.set_xlim(0.0, 1.0)
    axis.set_ylim(0.0, 1.0)
    axis.axis("off")
    stages = ("Planned", "Radiation\nrunning", "Radiation\ncomplete", "Feedback\ncomplete")
    x_positions = (0.03, 0.28, 0.54, 0.79)
    for x, label in zip(x_positions, stages):
        patch = FancyBboxPatch(
            (x, 0.42), 0.17, 0.2, boxstyle="round,pad=0.02", fc="#dceaf7", ec="#2b5d87"
        )
        axis.add_patch(patch)
        axis.text(x + 0.085, 0.52, label, ha="center", va="center", fontsize=9.5)
    for left, right in zip(x_positions[:-1], x_positions[1:]):
        axis.annotate("", xy=(right - 0.01, 0.52), xytext=(left + 0.18, 0.52), arrowprops={"arrowstyle": "->"})
    axis.text(0.5, 0.82, "(a) Recoverable evaluation state machine", ha="center", fontsize=11)
    axis.text(0.5, 0.17, "Partial blocks are resumable, not physical feedback states", ha="center", color="#8b1a1a")

    axis = axes[0, 1]
    axis.axis("off")
    axis.text(0.5, 0.9, "(b) Fidelity is part of the frozen request", ha="center", fontsize=11)
    axis.text(
        0.08,
        0.68,
        "ONE MAP DIAGNOSTIC\n\nRadiation remembers its initial state\nNewton load: REJECTED",
        va="top",
        bbox={"boxstyle": "round", "fc": "#fde4d0", "ec": "#a44a1f"},
    )
    axis.text(
        0.55,
        0.68,
        "INNER-CONVERGED RADIATION\n\nAll blocks and physics gates pass\nNewton load: ELIGIBLE",
        va="top",
        bbox={"boxstyle": "round", "fc": "#dff1df", "ec": "#2c7a3f"},
    )

    axis = axes[1, 0]
    labels = (
        "Partial\nrejection",
        "Block\ntamper",
        "One-map\nrejection",
        "Inner\nload",
        "Physical\nfailure",
        "Manifest\ntamper",
    )
    values = [
        controls["partial_checkpoint_rejected"],
        controls["completed_block_tamper_rejected"],
        controls["one_map_newton_load_rejected"],
        controls["inner_converged_newton_load_exact"],
        controls["physical_domain_failure_terminal"],
        controls["manifest_tamper_rejected"],
    ]
    axis.bar(np.arange(len(values)), np.asarray(values, dtype=float), color="#3f7f93")
    axis.set(xticks=np.arange(len(values)), xticklabels=labels, ylim=(0.0, 1.12), ylabel="Gate passed")
    axis.set_title("(c) Independent state-machine controls")
    axis.set_yticks((0.0, 1.0))

    axis = axes[1, 1]
    hours = np.array([cost_s / 3600.0, cost_s * jv_count / 3600.0])
    axis.bar((0, 1), hours, color=("#809ab3", "#b05a4a"))
    axis.set(
        xticks=(0, 1),
        xticklabels=("One directional\nresidual", f"{jv_count} Jv directional\nlower bound"),
        ylabel="Wall time (hours)",
        title="(d) Measured lower bound before radiation inner solves",
    )
    for index, value in enumerate(hours):
        axis.text(index, value, f" {value:.2f} h", ha="center", va="bottom")
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    started = time.perf_counter()
    tmp_root = ROOT / "tmp"
    tmp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase7b9b-", dir=tmp_root) as directory:
        controls = _run_controls(Path(directory))
    validation_runtime = time.perf_counter() - started

    layout = protocol["production_layout"]
    checkpoint = OUTPUT / "checkpoints/phase7b8e_backtracked_radiation_map.dat"
    production_checkpoint_size_matches = bool(
        checkpoint.stat().st_size == int(layout["raw_float64_checkpoint_size_bytes"])
        and int(layout["frequency_group_count"])
        * int(layout["direction_count"])
        * int(layout["depth_count"])
        * np.dtype(np.float64).itemsize
        == checkpoint.stat().st_size
    )
    measured = protocol["measured_costs"]
    cost_s = float(measured["one_directional_full_frequency_residual_lower_bound_s"])
    jv_count = int(measured["phase7b9a_component_jv_count"])
    all_controls_passed = all(bool(value) for value in controls.values())
    runtime_passed = validation_runtime < float(
        protocol["gates"]["validation_wall_runtime_below_s"]
    )
    phase_passed = bool(
        all_controls_passed and runtime_passed and production_checkpoint_size_matches
    )
    decision = {
        "frozen_sources_passed": True,
        "production_layout_passed": production_checkpoint_size_matches,
        "state_machine_controls_passed": all_controls_passed,
        "validation_runtime_passed": runtime_passed,
        "phase7b9b_gate_passed": phase_passed,
        "block_or_low_rank_preconditioner_design_authorized": phase_passed,
        "unpreconditioned_full_frequency_jv_authorized": False,
        "new_full_frequency_residual_evaluated": False,
        "accepted_as_dynamic_NLTE_solution": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    figure_path = OUTPUT / "phase7b9b_recoverable_residual_interface.png"
    _plot(figure_path, controls, cost_s, jv_count)
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "production_layout": layout,
        "control_results": controls,
        "validation_wall_runtime_s": validation_runtime,
        "measured_one_directional_residual_lower_bound_s": cost_s,
        "component_jv_count": jv_count,
        "same_jv_count_directional_lower_bound_s": cost_s * jv_count,
        "same_jv_count_directional_lower_bound_h": cost_s * jv_count / 3600.0,
        "radiation_inner_iteration_cost_included": False,
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(
        OUTPUT / "phase7b9b_recoverable_residual_interface_summary.json", report
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9b_preregistered_recoverable_residual.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
