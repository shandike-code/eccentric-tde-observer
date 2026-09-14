"""0.0625 fixed-material radiation continuation small-file tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts import phase7b9_half_trial_radiation_continuation as continuation
from scripts import phase7b9_protocol_builders as common
from scripts import phase7b9_half_trial_positive_sequence_engine as engine


def _write(root: Path, relative: str, payload: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_json(root: Path, relative: str, payload: dict[str, object]) -> None:
    _write(root, relative, json.dumps(payload, indent=2).encode())


def _source(root: Path, relative: str) -> dict[str, object]:
    return common.source_entry(root, relative)


def _fixture(root: Path) -> continuation.HalfTrialRadiationContinuationSpec:
    candidate = "outputs/half_material.npz"
    _write(root, candidate, b"half-material")
    material_protocol = "outputs/material_protocol.json"
    _write_json(
        root,
        material_protocol,
        {"configuration": {"candidate_absolute_relaxation": 0.0625}},
    )
    material_summary = "outputs/material_summary.json"
    _write_json(
        root,
        material_summary,
        {
            "protocol_sha256": common.sha256(root / material_protocol),
            "candidate_absolute_relaxation": 0.0625,
            "candidate_path": candidate,
            "candidate_sha256": common.sha256(root / candidate),
            "gate_checks": {"all_material_gates": True},
            "decision": {
                "material_candidate_gate_passed": True,
                "candidate_full_frequency_radiation_authorized": True,
                "candidate_radiation_evaluated": False,
                "candidate_formal_feedback_evaluated": False,
                "candidate_accepted_as_nonlinear_step": False,
            },
        },
    )
    initial = continuation.INITIAL_RADIATION_PATH
    buffer_a = "outputs/checkpoints/approved_a.dat"
    buffer_b = "outputs/checkpoints/approved_b.dat"
    _write(root, initial, b"protected-initial")
    _write(root, buffer_a, b"historical-A-old!")
    _write(root, buffer_b, b"historical-B-old!")
    assert len((root / initial).read_bytes()) == len((root / buffer_a).read_bytes())
    assert len((root / initial).read_bytes()) == len((root / buffer_b).read_bytes())
    claim_protocol = "outputs/initial_claim.json"
    _write_json(
        root,
        claim_protocol,
        {
            "sources": {
                "final_radiation": {
                    "path": initial,
                    "size_bytes": (root / initial).stat().st_size,
                    "sha256": continuation.INITIAL_RADIATION_SHA256,
                }
            }
        },
    )
    storage = "outputs/storage_auth.json"
    _write_json(
        root,
        storage,
        {
            "configuration": {
                "target_count": 2,
                "targets": [
                    {
                        "path": buffer_a,
                        "future_role": "buffer_a",
                        "size_bytes": (root / buffer_a).stat().st_size,
                        "verified_current_sha256": common.sha256(root / buffer_a),
                    },
                    {
                        "path": buffer_b,
                        "future_role": "buffer_b",
                        "size_bytes": (root / buffer_b).stat().st_size,
                        "verified_current_sha256": common.sha256(root / buffer_b),
                    },
                ],
                "protected_current_chain": [
                    {"path": initial, "must_not_be_modified": True}
                ],
                "overwrite_may_begin_only_after_future_protocol_hash_is_frozen": True,
            },
            "gate_checks": {
                "metadata": True,
                "hashes": True,
                "approval": True,
            },
            "authorization": {
                "destructive_reuse_authorized": True,
                "overwrite_only_exact_named_targets": True,
                "delete_unrelated_files": False,
                "modify_protected_current_chain": False,
                "numerical_repair": {
                    "nan_to_num": False,
                    "clipping": False,
                    "floors": False,
                    "failed_point_deletion": False,
                    "posthoc_renormalization": False,
                },
            },
        },
    )
    phase7b7i_template = "outputs/phase7b7i_template.json"
    _write_json(root, phase7b7i_template, {"sources": {}, "configuration": {}})
    master = "outputs/master.npz"
    _write(root, master, b"master")
    finite = "outputs/finite_template.json"
    _write_json(
        root,
        finite,
        {
            "phase": "finite template",
            "sources": {
                "current_material_state": _source(root, candidate),
                "finite_trial_material": _source(root, candidate),
                "phase7b5p_master_input": _source(root, master),
                "phase7b7i_template_protocol": _source(root, phase7b7i_template),
            },
            "configuration": {},
        },
    )
    for relative in (
        common.MAP_WORKER,
        common.WORKER_HELPERS,
        common.GENERIC_MAP_RUNNER,
        continuation.SEQUENCE_ENGINE_RELATIVE_PATH,
        common.MIXED_FRAME_OPERATOR,
        common.MIXED_FRAME_FREQUENCY,
        continuation.RUNNER_RELATIVE_PATH,
    ):
        _write(root, relative, relative.encode())
    return continuation.HalfTrialRadiationContinuationSpec(
        phase="7B9 half-trial continuation test",
        phase_index=1500,
        classification="[A-preregistered]+[V]+[O]",
        material_protocol_path=material_protocol,
        material_summary_path=material_summary,
        storage_authorization_path=storage,
        initial_radiation_claim_protocol_path=claim_protocol,
        finite_radiation_template_path=finite,
        fixed_material_worker_template_path="outputs/fixed_worker.json",
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        initialization_receipt_path="outputs/init_receipt.json",
        manifest_path="outputs/manifest.json",
        transient_report_directory=(
            "outputs/checkpoints/phase7b9_test_transient_reports"
        ),
        summary_path="outputs/summary.json",
        figure_path="outputs/figure.png",
    )


def _bundle(
    root: Path,
) -> tuple[continuation.HalfTrialRadiationContinuationSpec, Path, dict[str, object], str]:
    spec = _fixture(root)
    protocol_path = root / "outputs/protocol.json"
    protocol, digest = continuation.write_protocol_bundle(root, spec, protocol_path)
    return spec, protocol_path, protocol, digest


def _replace_initial_claim_with_fixture_hash(
    root: Path,
    spec: continuation.HalfTrialRadiationContinuationSpec,
) -> None:
    """Runtime fixture uses tiny bytes while production pins the real known hash."""
    claim_path = root / spec.initial_radiation_claim_protocol_path
    claim = json.loads(claim_path.read_text())
    claim["sources"]["final_radiation"]["sha256"] = common.sha256(
        root / continuation.INITIAL_RADIATION_PATH
    )
    claim_path.write_text(json.dumps(claim, indent=2))


def test_builder_freezes_half_material_two_buffers_and_unchanged_gates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    original_sha = common.sha256

    def forbid_dat_hash(path: Path) -> str:
        if path.suffix == ".dat":
            raise AssertionError("builder tried to hash a full-state checkpoint")
        return original_sha(path)

    monkeypatch.setattr(common, "sha256", forbid_dat_hash)
    worker = continuation.build_fixed_material_worker_template(tmp_path, spec)
    continuation._write_json_atomic(
        tmp_path / spec.fixed_material_worker_template_path, worker
    )
    protocol = continuation.build_half_trial_radiation_continuation_protocol(
        tmp_path, spec
    )
    cfg = protocol["configuration"]
    assert cfg["material_candidate_absolute_relaxation"] == 0.0625
    assert cfg["maximum_concurrent_processes"] == 2
    assert cfg["maximum_picard_maps"] == 24
    assert cfg["initial_reference_mode"] == "unreferenced_fixed_material_bootstrap"
    assert cfg["material_feedback_authorization_mode"] == (
        "after_two_consecutive_and_formal_pair"
    )
    assert protocol["gates"] == common.memory_safe_seeded_two_map_gates()
    assert protocol["gates"]["each_full_map_wall_time_strictly_below_s"] == 1800.0
    assert protocol["storage_plan"]["additional_full_state_allocation_count"] == 0
    assert protocol["authorization"]["formal_pair_only_after_next_consecutive_fresh_residual"]
    assert all(
        value is False
        for key, value in cfg.items()
        if key
        in {
            "cellwise_clipping",
            "nan_to_num",
            "intensity_floor",
            "point_deletion",
            "posthoc_renormalization",
            "matter_feedback_during_sequence",
        }
    )


@pytest.mark.parametrize(
    "failure",
    ("approval", "hash_gate", "material", "protected", "transient"),
)
def test_builder_rejects_scope_or_science_drift(tmp_path: Path, failure: str) -> None:
    spec = _fixture(tmp_path)
    if failure == "approval":
        path = tmp_path / spec.storage_authorization_path
        data = json.loads(path.read_text())
        data["authorization"]["destructive_reuse_authorized"] = False
        path.write_text(json.dumps(data))
    elif failure == "hash_gate":
        path = tmp_path / spec.storage_authorization_path
        data = json.loads(path.read_text())
        data["gate_checks"]["hashes"] = False
        path.write_text(json.dumps(data))
    elif failure == "material":
        path = tmp_path / spec.material_summary_path
        data = json.loads(path.read_text())
        data["candidate_absolute_relaxation"] = 0.125
        path.write_text(json.dumps(data))
    elif failure == "protected":
        path = tmp_path / spec.storage_authorization_path
        data = json.loads(path.read_text())
        data["configuration"]["protected_current_chain"] = []
        path.write_text(json.dumps(data))
    else:
        spec = continuation.HalfTrialRadiationContinuationSpec(
            **{
                **spec.__dict__,
                "transient_report_directory": "outputs/checkpoints/not_stage_reports",
            }
        )
    with pytest.raises(RuntimeError):
        worker = continuation.build_fixed_material_worker_template(tmp_path, spec)
        continuation._write_json_atomic(
            tmp_path / spec.fixed_material_worker_template_path, worker
        )
        continuation.build_half_trial_radiation_continuation_protocol(tmp_path, spec)


def test_initialization_overwrites_only_a_and_preserves_source_and_b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    _replace_initial_claim_with_fixture_hash(tmp_path, spec)
    monkeypatch.setattr(
        continuation,
        "INITIAL_RADIATION_SHA256",
        common.sha256(tmp_path / continuation.INITIAL_RADIATION_PATH),
    )
    protocol_path = tmp_path / "outputs/protocol.json"
    protocol, digest = continuation.write_protocol_bundle(
        tmp_path, spec, protocol_path
    )
    source = tmp_path / continuation.INITIAL_RADIATION_PATH
    a = tmp_path / protocol["configuration"]["initial_state_path"]
    b = tmp_path / protocol["configuration"]["scratch_state_path"]
    source_before = source.read_bytes()
    b_before = b.read_bytes()
    receipt = continuation.initialize_authorized_buffers(
        tmp_path, protocol_path, digest
    )
    assert a.read_bytes() == source_before
    assert source.read_bytes() == source_before
    assert b.read_bytes() == b_before
    assert receipt["protected_source_modified"] is False
    assert receipt["estimated_peak_additional_disk_bytes"] == 64 * 1024 * 1024
    second = continuation.initialize_authorized_buffers(tmp_path, protocol_path, digest)
    assert second == receipt


def test_initialization_creates_only_missing_receipt_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _fixture(tmp_path)
    spec = continuation.HalfTrialRadiationContinuationSpec(
        **{
            **original.__dict__,
            "initialization_receipt_path": (
                "outputs/checkpoints/new_stage_only/initialization_receipt.json"
            ),
            "manifest_path": "outputs/checkpoints/new_stage_only/manifest.json",
        }
    )
    _replace_initial_claim_with_fixture_hash(tmp_path, spec)
    actual = common.sha256(tmp_path / continuation.INITIAL_RADIATION_PATH)
    monkeypatch.setattr(continuation, "INITIAL_RADIATION_SHA256", actual)
    protocol_path = tmp_path / "outputs/protocol.json"
    protocol, digest = continuation.write_protocol_bundle(
        tmp_path, spec, protocol_path
    )
    parent = tmp_path / "outputs/checkpoints/new_stage_only"
    assert not parent.exists()
    unrelated = tmp_path / "outputs/checkpoints/historical_untouched"
    unrelated.mkdir(parents=True)
    marker = unrelated / "keep.txt"
    marker.write_text("keep")
    receipt = continuation.initialize_authorized_buffers(
        tmp_path, protocol_path, digest
    )
    assert parent.is_dir()
    assert (parent / "initialization_receipt.json").is_file()
    assert receipt["status"] == "complete"
    assert marker.read_text() == "keep"


def test_initialization_recovers_copy_before_receipt_without_second_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    _replace_initial_claim_with_fixture_hash(tmp_path, spec)
    actual = common.sha256(tmp_path / continuation.INITIAL_RADIATION_PATH)
    monkeypatch.setattr(continuation, "INITIAL_RADIATION_SHA256", actual)
    protocol_path = tmp_path / "outputs/protocol.json"
    protocol, digest = continuation.write_protocol_bundle(
        tmp_path, spec, protocol_path
    )
    source = tmp_path / continuation.INITIAL_RADIATION_PATH
    a = tmp_path / protocol["configuration"]["initial_state_path"]
    shutil_copy = source.read_bytes()
    a.write_bytes(shutil_copy)
    receipt = continuation.initialize_authorized_buffers(
        tmp_path, protocol_path, digest
    )
    assert receipt["resumed_after_copy_before_receipt"] is True


def test_initialization_receipt_does_not_require_ping_pong_buffers_to_stay_initial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    _replace_initial_claim_with_fixture_hash(tmp_path, spec)
    actual = common.sha256(tmp_path / continuation.INITIAL_RADIATION_PATH)
    monkeypatch.setattr(continuation, "INITIAL_RADIATION_SHA256", actual)
    protocol_path = tmp_path / "outputs/protocol.json"
    protocol, digest = continuation.write_protocol_bundle(
        tmp_path, spec, protocol_path
    )
    receipt = continuation.initialize_authorized_buffers(
        tmp_path, protocol_path, digest
    )
    continuation._write_json_atomic(
        tmp_path / protocol["configuration"]["manifest_path"],
        {"protocol_sha256": digest, "status": "running", "iterations": []},
    )
    (tmp_path / protocol["configuration"]["initial_state_path"]).write_bytes(
        b"mapped-state-0001"
    )
    (tmp_path / protocol["configuration"]["scratch_state_path"]).write_bytes(
        b"mapped-state-0002"
    )
    assert continuation.initialize_authorized_buffers(
        tmp_path, protocol_path, digest
    ) == receipt


def test_report_compaction_is_confined_to_owned_transient_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _fixture(tmp_path)
    _replace_initial_claim_with_fixture_hash(tmp_path, spec)
    monkeypatch.setattr(
        continuation,
        "INITIAL_RADIATION_SHA256",
        common.sha256(tmp_path / continuation.INITIAL_RADIATION_PATH),
    )
    protocol_path = tmp_path / "outputs/protocol.json"
    protocol, digest = continuation.write_protocol_bundle(
        tmp_path, spec, protocol_path
    )
    reports = [
        {"block_index": index, "value": float(index)} for index in range(76)
    ]
    manifest = {
        "protocol_sha256": digest,
        "status": "running",
        "iterations": [{"iteration": 0, "reports": reports}],
    }
    continuation._write_json_atomic(
        tmp_path / protocol["configuration"]["manifest_path"], manifest
    )
    transient = continuation._transient_root(tmp_path, protocol, digest)
    _write(tmp_path, str((transient / "iteration_00/block00.json").relative_to(tmp_path)), b"x")
    unrelated = tmp_path / "outputs/checkpoints/historical_keep/report.json"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("keep")
    compacted = continuation.compact_committed_reports(
        tmp_path, protocol, digest
    )
    audit = compacted["iterations"][0]["block_report_audit"]
    assert audit["record_count"] == 76
    assert audit["block_indices"] == list(range(76))
    assert audit["full_reports_retained"] is False
    assert not (transient / "iteration_00").exists()
    assert unrelated.read_text() == "keep"


def test_protocol_bundle_rejects_postfreeze_small_source_drift(tmp_path: Path) -> None:
    spec, protocol_path, _, digest = _bundle(tmp_path)
    runner = tmp_path / spec.runner_path
    runner.write_text("changed")
    with pytest.raises(RuntimeError, match="source changed"):
        continuation._load_runtime_protocol(tmp_path, protocol_path, digest)


def test_engine_bootstrap_skips_only_inapplicable_first_reproduction() -> None:
    gates = {"initial_audit_absolute_tolerance": 2.0e-12}
    reference = {
        "initial_global_residual": None,
        "initial_boundary_spectrum_l1": None,
        "initial_boundary_bolometric_fraction": None,
    }
    metrics = {
        "global_original_operator_residual": 0.4,
        "boundary_spectrum_l1": 0.2,
        "boundary_bolometric_fraction": 0.1,
    }
    applicable, passed = engine._initial_reproduction_gate(
        {"initial_reference_mode": "unreferenced_fixed_material_bootstrap"},
        reference,
        gates,
        metrics,
        0,
    )
    assert applicable is False
    assert passed is True
    applicable, passed = engine._initial_reproduction_gate(
        {"initial_reference_mode": "unreferenced_fixed_material_bootstrap"},
        reference,
        gates,
        metrics,
        1,
    )
    assert applicable is True
    assert passed is True


def test_engine_legacy_reproduction_and_authorization_remain_default() -> None:
    gates = {"initial_audit_absolute_tolerance": 2.0e-12}
    reference = {
        "initial_global_residual": 0.4,
        "initial_boundary_spectrum_l1": 0.2,
        "initial_boundary_bolometric_fraction": 0.1,
    }
    metrics = {
        "global_original_operator_residual": 0.4,
        "boundary_spectrum_l1": 0.2,
        "boundary_bolometric_fraction": 0.1,
    }
    assert engine._initial_reproduction_gate(
        {}, reference, gates, metrics, 0
    ) == (True, True)
    assert engine._feedback_authorization({}, converged=True) == (True, False)


def test_engine_provisional_mode_never_authorizes_material_feedback() -> None:
    cfg = {
        "material_feedback_authorization_mode": (
            "after_two_consecutive_and_formal_pair"
        )
    }
    assert engine._feedback_authorization(cfg, converged=False) == (False, False)
    assert engine._feedback_authorization(cfg, converged=True) == (False, True)
