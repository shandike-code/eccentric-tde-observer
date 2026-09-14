"""7B9dk 全 76 块重算协议与 runner 的纯 tmp_path 测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9dk_full_map_reproduction as reproduction
from scripts import phase7b9dk_preregister_full_map_reproduction as preregistration


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _source(root: Path, relative: str) -> dict[str, object]:
    data = (root / relative).read_bytes()
    return {"path": relative, "size_bytes": len(data), "sha256": _sha(data)}


def _fixture(root: Path) -> tuple[reproduction.FullMapReproductionSpec, Path, Path]:
    runner = reproduction.RUNNER_RELATIVE_PATH
    _write(root / runner, b"independent reproduction runner")
    _write(root / "outputs/material.npz", b"fixed material")
    material_source = _source(root, "outputs/material.npz")
    _write(
        root / "outputs/fixed.json",
        {"sources": {"current_material_state": material_source}},
    )
    a_path = root / "outputs/checkpoints/A.dat"
    b_path = root / "outputs/checkpoints/B.dat"
    a = np.ones((76, 1, 1), dtype=np.float64)
    b = np.full((76, 1, 1), 3.0, dtype=np.float64)
    a_path.parent.mkdir(parents=True, exist_ok=True)
    a.tofile(a_path)
    b.tofile(b_path)
    a_sha = _sha(a_path.read_bytes())
    b_sha = _sha(b_path.read_bytes())
    gates = {
        "block_count_exactly": 76,
        "owned_frequency_group_count_exactly": 76,
        "minimum_input_and_mapped_intensity_at_least": 0.0,
        "global_original_operator_residual_below": 1.0e-4,
        "subsequent_residual_contraction_ratio_below": 1.01,
        "global_boundary_spectrum_l1_below": 1.0e-3,
        "global_boundary_bolometric_fraction_below": 1.0e-3,
        "each_process_peak_rss_strictly_below_mib": 6144.0,
        "each_worker_wall_time_strictly_below_s": 60.0,
        "each_full_map_wall_time_strictly_below_s": 1800.0,
    }
    di_protocol = {
        "sources": {
            "finite_trial_protocol": _source(root, "outputs/fixed.json"),
            "finite_trial_material": material_source,
        },
        "configuration": {
            "maximum_concurrent_processes": 2,
            "physical_frequency_groups": 76,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
            "raw_float64_checkpoint_size_bytes": int(a.nbytes),
            "diagnostic_fixed_iteration_count": 1,
            "spatial_scheme": "hybrid_step_turning_upwind",
            "source_map_only": True,
            "material_candidate_absolute_relaxation": 0.0625,
        },
        "gates": gates,
    }
    _write(root / "outputs/di_protocol.json", di_protocol)
    di_sha = _sha((root / "outputs/di_protocol.json").read_bytes())
    records = []
    for index in range(21):
        records.append(
            {
                "iteration": index,
                "input_state_path": "outputs/checkpoints/A.dat",
                "input_state_sha256": a_sha,
                "mapped_state_path": "outputs/checkpoints/B.dat",
                "mapped_state_sha256": b_sha,
                "global_original_operator_residual": (
                    0.013567 if index == 20 else 0.001777798494271581
                ),
            }
        )
    manifest = {
        "protocol_sha256": di_sha,
        "status": "gate_failed",
        "active_iteration": None,
        "iterations": records,
    }
    _write(root / "outputs/di_manifest.json", manifest)
    _write(root / "outputs/di_summary.json", manifest)
    audit = {
        "frozen_state_claims": {
            "immutable_input_sha256": a_sha,
            "failed_output_sha256": b_sha,
        },
        "decision": {
            "unreproducible_block_index": 34,
            "single_block_repair_authorized": False,
            "fresh_full_76_block_reproduction_required": True,
        },
    }
    _write(root / "outputs/dj_audit.json", audit)
    spec = reproduction.FullMapReproductionSpec(
        phase="dk",
        classification="[A-preregistered]+[V]+[O]",
        di_protocol_path="outputs/di_protocol.json",
        di_manifest_path="outputs/di_manifest.json",
        di_summary_path="outputs/di_summary.json",
        failure_audit_path="outputs/dj_audit.json",
        runner_path=runner,
        manifest_path="outputs/checkpoints/dk/manifest.json",
        report_directory="outputs/checkpoints/dk_reports",
        summary_path="outputs/dk_summary.json",
        immutable_input_sha256=a_sha,
        authorized_output_previous_sha256=b_sha,
        natural_frequency_block_width=1,
    )
    return spec, a_path, b_path


def _executor(protocol_hash: str, *, rss: float = 100.0):
    def execute(
        indices: list[int],
        input_path: Path,
        input_sha: str,
        output_path: Path,
        report_paths: list[Path],
    ) -> list[dict[str, object]]:
        source = np.memmap(input_path, mode="r", dtype=np.float64, shape=(76, 1, 1))
        target = np.memmap(output_path, mode="r+", dtype=np.float64, shape=(76, 1, 1))
        rows = []
        for index in indices:
            mapped = float(source[index, 0, 0]) + 5.0e-4
            target[index, 0, 0] = mapped
            rows.append(
                {
                    "protocol_sha256": protocol_hash,
                    "input_state_sha256": input_sha,
                    "picard_iteration": 20,
                    "block_index": index,
                    "core_group_start": index,
                    "core_group_stop": index + 1,
                    "maximum_absolute_radiation_change": 5.0e-4,
                    "maximum_radiation_scale": mapped,
                    "block_relative_radiation_change": 5.0e-4 / mapped,
                    "boundary_spectrum_l1_numerator": 1.0e-9,
                    "current_boundary_absolute_scale": 1.0,
                    "mapped_boundary_absolute_scale": 1.0,
                    "current_boundary_bolometric": 1.0,
                    "mapped_boundary_bolometric": 1.0,
                    "minimum_input_intensity": 1.0,
                    "minimum_mapped_intensity": mapped,
                    "peak_process_rss_mib": rss,
                    "wall_runtime_s": 0.01,
                }
            )
        target.flush()
        del source, target
        return rows

    return execute


def test_builder_freezes_full_overwrite_not_block34_patch(tmp_path: Path) -> None:
    spec, _, _ = _fixture(tmp_path)
    protocol = reproduction.build_reproduction_protocol(tmp_path, spec)
    assert protocol["configuration"]["block_layout"][0]["block_index"] == 0
    assert protocol["configuration"]["block_layout"][-1]["block_index"] == 75
    assert protocol["authorization"]["single_block_repair_authorized"] is False
    assert protocol["authorization"]["all_76_blocks_must_be_freshly_written"] is True
    assert protocol["configuration"]["maximum_concurrent_processes"] == 2
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0


def test_prereg_cli_atomically_writes_protocol_without_hashing_dat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec, a_path, b_path = _fixture(tmp_path)
    dat_mtimes = (a_path.stat().st_mtime_ns, b_path.stat().st_mtime_ns)
    original_sha = reproduction._sha256

    def guarded_sha(path: Path) -> str:
        if path.suffix == ".dat":
            raise AssertionError("preregistration attempted to hash a full-state dat")
        return original_sha(path)

    monkeypatch.setattr(reproduction, "_sha256", guarded_sha)
    output = "outputs/dk_protocol.json"
    protocol, digest = preregistration.main(
        [
            "--phase",
            spec.phase,
            "--classification",
            spec.classification,
            "--di-protocol",
            spec.di_protocol_path,
            "--di-manifest",
            spec.di_manifest_path,
            "--di-summary",
            spec.di_summary_path,
            "--failure-audit",
            spec.failure_audit_path,
            "--runner",
            spec.runner_path,
            "--manifest",
            spec.manifest_path,
            "--report-directory",
            spec.report_directory,
            "--summary",
            spec.summary_path,
            "--immutable-input-sha256",
            spec.immutable_input_sha256,
            "--authorized-output-previous-sha256",
            spec.authorized_output_previous_sha256,
            "--natural-frequency-block-width",
            "1",
            "--output",
            output,
        ],
        root=tmp_path,
    )
    assert (tmp_path / output).exists()
    assert not (tmp_path / f"{output}.tmp").exists()
    assert original_sha(tmp_path / output) == digest
    assert protocol["configuration"]["block_layout"][0]["block_index"] == 0
    assert (a_path.stat().st_mtime_ns, b_path.stat().st_mtime_ns) == dat_mtimes


def test_full_reproduction_overwrites_every_block_and_retains_reports(
    tmp_path: Path,
) -> None:
    spec, a_path, b_path = _fixture(tmp_path)
    di_manifest_before = (tmp_path / spec.di_manifest_path).read_bytes()
    a_before = a_path.read_bytes()
    protocol_path = tmp_path / "outputs/dk_protocol.json"
    _, digest = reproduction.write_protocol(tmp_path, spec, protocol_path)
    summary = reproduction.run_reproduction(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=_executor(digest),
    )
    assert summary["status"] == "reproduction_passed"
    assert summary["block_report_count"] == 76
    assert summary["decision"]["fresh_state_authorized_as_continuation_input"] is True
    assert summary["decision"]["already_converged"] is False
    assert a_path.read_bytes() == a_before
    assert (tmp_path / spec.di_manifest_path).read_bytes() == di_manifest_before
    mapped = np.fromfile(b_path, dtype=np.float64)
    assert np.all(mapped == 1.0005)
    reports = sorted((tmp_path / spec.report_directory).glob("*.json"))
    assert len(reports) == 76
    first = json.loads(reports[0].read_text())
    assert len(first["previous_block_sha256"]) == 64
    assert len(first["new_block_sha256"]) == 64
    assert first["previous_block_sha256"] != first["new_block_sha256"]


def test_changed_authorized_output_is_rejected_before_any_write(
    tmp_path: Path,
) -> None:
    spec, _, b_path = _fixture(tmp_path)
    protocol_path = tmp_path / "outputs/dk_protocol.json"
    _, digest = reproduction.write_protocol(tmp_path, spec, protocol_path)
    before = b_path.read_bytes()
    b_path.write_bytes(before[:-8] + np.float64(4.0).tobytes())
    changed = b_path.read_bytes()
    with pytest.raises(RuntimeError, match="authorized B changed"):
        reproduction.initialize_manifest(tmp_path, protocol_path, digest)
    assert b_path.read_bytes() == changed


def test_resource_failure_does_not_authorize_continuation(tmp_path: Path) -> None:
    spec, _, _ = _fixture(tmp_path)
    protocol_path = tmp_path / "outputs/dk_protocol.json"
    _, digest = reproduction.write_protocol(tmp_path, spec, protocol_path)
    summary = reproduction.run_reproduction(
        tmp_path,
        protocol_path,
        digest,
        batch_executor=_executor(digest, rss=7000.0),
    )
    assert summary["status"] == "gate_failed"
    assert summary["progression_gate_checks"]["resources_pass"] is False
    assert summary["decision"]["fresh_state_authorized_as_continuation_input"] is False
