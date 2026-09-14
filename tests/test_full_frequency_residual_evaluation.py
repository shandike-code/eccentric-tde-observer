import json
from pathlib import Path

import numpy as np
import pytest

from eccentric_tde_observer.full_frequency_residual_evaluation import (
    FullFrequencyResidualFidelity,
    FullFrequencyResidualStatus,
    RecoverableFullFrequencyResidualEvaluation,
    build_full_frequency_residual_request,
    write_encoded_residual_atomic,
)
from eccentric_tde_observer.source import PhysicalDomainError


_REQUIRED_INPUTS = (
    "frozen_protocol",
    "encoded_material_state",
    "decoded_material_state",
    "physical_old_time_level",
    "initial_radiation_checkpoint",
)


def _request(root: Path, fidelity: FullFrequencyResidualFidelity):
    inputs = {}
    for index, name in enumerate(_REQUIRED_INPUTS):
        path = root / f"{name}.dat"
        path.write_bytes(f"input-{index}".encode())
        inputs[name] = path
    return build_full_frequency_residual_request(
        root,
        evaluation_id=f"test-{fidelity.value}",
        fidelity=fidelity,
        encoded_unknown_count=8,
        radiation_shape=(4, 2, 3),
        frequency_block_ranges=((0, 2), (2, 4)),
        radiation_output_path=root / "radiation.dat",
        radiation_inner_residual_tolerance=1.0e-6,
        input_artifact_paths=inputs,
    )


def _create_running(root: Path, fidelity: FullFrequencyResidualFidelity):
    request = _request(root, fidelity)
    evaluation = RecoverableFullFrequencyResidualEvaluation.create(
        root, root / "manifest.json", request
    )
    np.arange(24, dtype=np.float64).tofile(root / "radiation.dat")
    evaluation.start_radiation()
    return evaluation


def _complete_radiation(evaluation, *, converged: bool):
    evaluation.mark_frequency_block_complete(0)
    evaluation.mark_frequency_block_complete(1)
    evaluation.complete_radiation(
        inner_iteration_count=3 if converged else 1,
        inner_residual_norm=5.0e-7 if converged else 0.2,
        inner_converged=converged,
        science_functionals_passed=True,
        wall_runtime_s=12.0,
    )


def _complete_feedback(evaluation):
    feedback = evaluation.workspace_root / "feedback.npz"
    np.savez(feedback, rate=np.array([1.0]))
    evaluation.complete_feedback(
        feedback,
        source_consistency_passed=True,
        conservation_passed=True,
        wall_runtime_s=2.0,
    )


def test_partial_radiation_checkpoint_is_recoverable_but_not_physical(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    evaluation.mark_frequency_block_complete(0)
    recovered = RecoverableFullFrequencyResidualEvaluation.resume(
        tmp_path, tmp_path / "manifest.json"
    )
    assert recovered.status is FullFrequencyResidualStatus.RADIATION_RUNNING
    assert len(recovered.payload["completed_frequency_blocks"]) == 1
    with pytest.raises(RuntimeError, match="partial radiation checkpoint"):
        recovered.radiation_checkpoint_for_feedback()
    with pytest.raises(RuntimeError, match="partial radiation checkpoint"):
        recovered.complete_radiation(
            inner_iteration_count=2,
            inner_residual_norm=1.0e-7,
            inner_converged=True,
            science_functionals_passed=True,
            wall_runtime_s=1.0,
        )


def test_resume_rejects_changed_completed_frequency_block(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    evaluation.mark_frequency_block_complete(0)
    checkpoint = np.memmap(
        tmp_path / "radiation.dat", mode="r+", dtype=np.float64, shape=(4, 2, 3)
    )
    checkpoint[0, 0, 0] += 1.0
    checkpoint.flush()
    del checkpoint
    with pytest.raises(RuntimeError, match="completed radiation block changed"):
        RecoverableFullFrequencyResidualEvaluation.resume(
            tmp_path, tmp_path / "manifest.json"
        )


def test_radiation_completion_rejects_changed_registered_block(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    evaluation.mark_frequency_block_complete(0)
    evaluation.mark_frequency_block_complete(1)
    checkpoint = np.memmap(
        tmp_path / "radiation.dat", mode="r+", dtype=np.float64, shape=(4, 2, 3)
    )
    checkpoint[2, 0, 0] += 1.0
    checkpoint.flush()
    del checkpoint
    with pytest.raises(RuntimeError, match="completed radiation block changed"):
        evaluation.complete_radiation(
            inner_iteration_count=2,
            inner_residual_norm=1.0e-7,
            inner_converged=True,
            science_functionals_passed=True,
            wall_runtime_s=1.0,
        )


def test_one_map_residual_remains_diagnostic_and_cannot_enter_newton(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.ONE_MAP_DIAGNOSTIC
    )
    _complete_radiation(evaluation, converged=False)
    assert evaluation.radiation_checkpoint_for_feedback().name == "radiation.dat"
    _complete_feedback(evaluation)
    residual = np.linspace(-0.2, 0.2, 8)
    write_encoded_residual_atomic(tmp_path / "residual.npy", residual)
    evaluation.complete_material_residual(tmp_path / "residual.npy")
    assert evaluation.status is FullFrequencyResidualStatus.DIAGNOSTIC_COMPLETE
    with pytest.raises(RuntimeError, match="not an inner-converged Newton residual"):
        evaluation.load_newton_residual()


def test_inner_converged_evaluation_loads_verified_newton_residual(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    _complete_radiation(evaluation, converged=True)
    _complete_feedback(evaluation)
    expected = np.linspace(-0.3, 0.4, 8)
    write_encoded_residual_atomic(tmp_path / "residual.npy", expected)
    evaluation.complete_material_residual(tmp_path / "residual.npy")
    assert evaluation.status is FullFrequencyResidualStatus.COMPLETE
    np.testing.assert_array_equal(evaluation.load_newton_residual(), expected)
    recovered = RecoverableFullFrequencyResidualEvaluation.resume(
        tmp_path, tmp_path / "manifest.json"
    )
    np.testing.assert_array_equal(recovered.load_newton_residual(), expected)


def test_inner_converged_fidelity_rejects_failed_radiation_gate(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    evaluation.mark_frequency_block_complete(0)
    evaluation.mark_frequency_block_complete(1)
    with pytest.raises(RuntimeError, match="inner-converged radiation gate"):
        evaluation.complete_radiation(
            inner_iteration_count=4,
            inner_residual_norm=2.0e-6,
            inner_converged=True,
            science_functionals_passed=True,
            wall_runtime_s=4.0,
        )
    assert evaluation.status is FullFrequencyResidualStatus.RADIATION_RUNNING


def test_failed_feedback_cannot_define_material_residual(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    _complete_radiation(evaluation, converged=True)
    feedback = tmp_path / "feedback.npz"
    np.savez(feedback, rate=np.array([1.0]))
    evaluation.complete_feedback(
        feedback,
        source_consistency_passed=False,
        conservation_passed=True,
        wall_runtime_s=1.0,
    )
    write_encoded_residual_atomic(tmp_path / "residual.npy", np.ones(8))
    with pytest.raises(RuntimeError, match="invalid feedback"):
        evaluation.complete_material_residual(tmp_path / "residual.npy")


def test_physical_domain_failure_is_terminal_and_preserved_without_floor(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.INNER_CONVERGED_RADIATION
    )
    evaluation.record_failure(
        physical_domain=True,
        stage="decode_material_response",
        exception_type="PhysicalDomainError",
        message="specific material energy leaves no positive gas heat",
    )
    assert evaluation.status is FullFrequencyResidualStatus.FAILED_PHYSICAL_DOMAIN
    recovered = RecoverableFullFrequencyResidualEvaluation.resume(
        tmp_path, tmp_path / "manifest.json"
    )
    assert recovered.payload["failure"]["physical_domain"] is True
    assert "no positive gas heat" in recovered.payload["failure"]["message"]
    with pytest.raises(RuntimeError, match="terminal"):
        recovered.start_radiation()


def test_manifest_request_tampering_is_detected(tmp_path):
    evaluation = _create_running(
        tmp_path, FullFrequencyResidualFidelity.ONE_MAP_DIAGNOSTIC
    )
    payload = json.loads((tmp_path / "manifest.json").read_text())
    payload["request"]["encoded_unknown_count"] = 9
    (tmp_path / "manifest.json").write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="manifest state hash changed"):
        RecoverableFullFrequencyResidualEvaluation.resume(
            tmp_path, tmp_path / "manifest.json"
        )
    assert evaluation.request.encoded_unknown_count == 8


def test_atomic_residual_writer_rejects_nonfinite_values(tmp_path):
    with pytest.raises(PhysicalDomainError, match="residual is invalid"):
        write_encoded_residual_atomic(tmp_path / "bad.npy", [0.0, np.nan])
    assert not (tmp_path / "bad.npy").exists()


def test_request_rejects_frequency_block_gap(tmp_path):
    inputs = {}
    for index, name in enumerate(_REQUIRED_INPUTS):
        path = tmp_path / f"{name}.dat"
        path.write_bytes(f"input-{index}".encode())
        inputs[name] = path
    with pytest.raises(PhysicalDomainError, match="ordered and contiguous"):
        build_full_frequency_residual_request(
            tmp_path,
            evaluation_id="bad-blocks",
            fidelity=FullFrequencyResidualFidelity.ONE_MAP_DIAGNOSTIC,
            encoded_unknown_count=8,
            radiation_shape=(4, 2, 3),
            frequency_block_ranges=((0, 2), (3, 4)),
            radiation_output_path=tmp_path / "radiation.dat",
            radiation_inner_residual_tolerance=1.0e-6,
            input_artifact_paths=inputs,
        )
