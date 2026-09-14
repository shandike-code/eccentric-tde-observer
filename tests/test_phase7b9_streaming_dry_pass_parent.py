"""streaming Anderson dry-pass parent 的纯 tmp_path 测试。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "scripts"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from scripts import phase7b9_streaming_dry_pass_parent as parent
from scripts import phase7b9di_streaming_anderson_orchestrator as orchestrator
from scripts import phase7b9di_streaming_anderson_tail as streaming


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


def _fixture(root: Path, *, pin_parent: bool = True) -> tuple[Path, str]:
    for path in (
        parent.PARENT_RELATIVE_PATH,
        streaming.RUNNER_RELATIVE_PATH,
        streaming.ORCHESTRATOR_RELATIVE_PATH,
    ):
        _write(root / path, f"dummy {path}".encode())
    sources = {
        "streaming_anderson_worker": _source(root, streaming.RUNNER_RELATIVE_PATH),
        "streaming_anderson_orchestrator": _source(
            root, streaming.ORCHESTRATOR_RELATIVE_PATH
        ),
    }
    if pin_parent:
        sources[parent.PARENT_SOURCE_KEY] = _source(root, parent.PARENT_RELATIVE_PATH)
    gates = streaming.frozen.protected_anderson_tail_gates()
    gates.update(
        {
            "predicted_boundary_spectrum_ratio_to_x24_below": 1.0,
            "predicted_boundary_bolometric_ratio_to_x24_below": 1.0,
            "pass1_pass2_each_mapped_block_sha256_must_match": True,
            "pass1_pass2_block_ownership_exactly_once": True,
            "each_dry_process_peak_rss_strictly_below_mib": 6144.0,
            "each_dry_worker_wall_time_strictly_below_s": 60.0,
            "each_dry_full_map_wall_time_strictly_below_s": 1800.0,
        }
    )
    protocol = {
        "phase": "stream",
        "sources": sources,
        "configuration": {
            "physical_frequency_groups": 76,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
            "natural_frequency_block_count": 76,
            "diagnostic_frequency_block": 1,
            "minimum_forward_picard_fraction": 1.0,
            "maximum_forward_picard_fraction": 96.0,
            "maximum_concurrent_processes": 2,
            "x23_state_sha256": _sha(b"x23"),
            "x24_state_sha256": _sha(b"x24"),
            "coefficient_report_directory": "outputs/checkpoints/stream/pass1",
            "evaluation_report_directory": "outputs/checkpoints/stream/pass2",
            "coefficient_manifest_path": "outputs/checkpoints/stream/coefficient.json",
            "evaluation_manifest_path": "outputs/checkpoints/stream/evaluation.json",
            "runner_path": streaming.RUNNER_RELATIVE_PATH,
            "orchestrator_path": streaming.ORCHESTRATOR_RELATIVE_PATH,
        },
        "algebraic_gates": gates,
    }
    path = root / "outputs/stream_protocol.json"
    _write(path, protocol)
    return path, _sha(path.read_bytes())


def _executor(protocol_hash: str, *, mismatch_pass2_block: int | None = None):
    mu = np.asarray([1.0])
    weight = np.asarray([1.0])
    width = np.asarray([1.0])

    def execute(
        pass_index: int,
        indices: list[int],
        selected: float | None,
        paths: list[Path],
    ) -> list[dict[str, object]]:
        reports = []
        for index in indices:
            x23 = np.asarray([[[1.0]]])
            x24 = np.asarray([[[1.1]]])
            mapped = np.asarray([[[1.15]]])
            if pass_index == 2 and mismatch_pass2_block == index:
                mapped = np.asarray([[[1.151]]])
            if pass_index == 1:
                payload = streaming.coefficient_block_statistics(
                    x23,
                    x24,
                    mapped,
                    global_group_start=index,
                    mu=mu,
                    weight=weight,
                    frequency_width=width,
                )
            else:
                assert selected is not None
                payload = streaming.evaluation_block_statistics(
                    x23, x24, mapped, selected, mu, weight, width
                )
            reports.append(
                {
                    "protocol_sha256": protocol_hash,
                    "pass_index": pass_index,
                    "block_index": index,
                    "core_group_start": index,
                    "core_group_stop": index + 1,
                    "x23_state_sha256": _sha(b"x23"),
                    "x24_state_sha256": _sha(b"x24"),
                    "baseline_highwater_rss_mib": 10.0,
                    "peak_process_rss_mib": 100.0,
                    "wall_runtime_s": 0.01,
                    "full_state_write_performed": False,
                    **payload,
                }
            )
        return reports

    return execute


def test_parent_runs_two_complete_dry_passes_and_orchestrator_accepts(
    tmp_path: Path,
) -> None:
    protocol_path, digest = _fixture(tmp_path)
    first = parent.run_dry_pass(
        tmp_path,
        protocol_path,
        digest,
        1,
        batch_executor=_executor(digest),
    )
    assert first["status"] == "complete"
    assert len(first["reports"]) == 76
    assert first["full_state_write_performed"] is False
    selected = first["aggregate"]["selected_forward_fraction"]
    assert selected > 1.0
    second = parent.run_dry_pass(
        tmp_path,
        protocol_path,
        digest,
        2,
        batch_executor=_executor(digest),
    )
    assert second["status"] == "complete"
    assert len(second["reports"]) == 76
    assert second["selected_forward_fraction"] == selected
    assert second["coefficient_manifest_sha256"] == parent._sha256(
        tmp_path / "outputs/checkpoints/stream/coefficient.json"
    )
    protocol = json.loads(protocol_path.read_text())
    coefficient, evaluation, checks = orchestrator.validate_dry_evidence(
        tmp_path, protocol, digest
    )
    assert coefficient == first["aggregate"]
    assert evaluation == second["aggregate"]
    assert all(checks.values())


def test_pass1_recovers_without_rerunning_committed_blocks(tmp_path: Path) -> None:
    protocol_path, digest = _fixture(tmp_path)
    base = _executor(digest)

    def failing(
        pass_index: int,
        indices: list[int],
        selected: float | None,
        paths: list[Path],
    ) -> list[dict[str, object]]:
        if indices[0] == 2:
            raise RuntimeError("simulated dry-worker crash")
        return base(pass_index, indices, selected, paths)

    with pytest.raises(RuntimeError, match="simulated"):
        parent.run_dry_pass(
            tmp_path, protocol_path, digest, 1, batch_executor=failing
        )
    manifest_path = tmp_path / "outputs/checkpoints/stream/coefficient.json"
    interrupted = json.loads(manifest_path.read_text())
    assert [row["block_index"] for row in interrupted["reports"]] == [0, 1]
    seen: list[int] = []

    def resumed(
        pass_index: int,
        indices: list[int],
        selected: float | None,
        paths: list[Path],
    ) -> list[dict[str, object]]:
        seen.extend(indices)
        return base(pass_index, indices, selected, paths)

    completed = parent.run_dry_pass(
        tmp_path, protocol_path, digest, 1, batch_executor=resumed
    )
    assert completed["status"] == "complete"
    assert 0 not in seen and 1 not in seen
    assert seen == list(range(2, 76))


def test_recovery_rejects_modified_committed_report(tmp_path: Path) -> None:
    protocol_path, digest = _fixture(tmp_path)
    parent.run_dry_pass(
        tmp_path,
        protocol_path,
        digest,
        1,
        batch_executor=_executor(digest),
    )
    report = tmp_path / "outputs/checkpoints/stream/pass1/pass1_block00.json"
    payload = json.loads(report.read_text())
    payload["x24_state_sha256"] = "0" * 64
    _write(report, payload)
    with pytest.raises(RuntimeError, match="completed report changed|block 0 failed"):
        parent.run_dry_pass(
            tmp_path,
            protocol_path,
            digest,
            1,
            batch_executor=_executor(digest),
        )


def test_pass2_mapped_sha_mismatch_is_fail_closed(tmp_path: Path) -> None:
    protocol_path, digest = _fixture(tmp_path)
    parent.run_dry_pass(
        tmp_path,
        protocol_path,
        digest,
        1,
        batch_executor=_executor(digest),
    )
    with pytest.raises(RuntimeError, match="not blockwise reproducible"):
        parent.run_dry_pass(
            tmp_path,
            protocol_path,
            digest,
            2,
            batch_executor=_executor(digest, mismatch_pass2_block=34),
        )
    evaluation = json.loads(
        (tmp_path / "outputs/checkpoints/stream/evaluation.json").read_text()
    )
    assert evaluation["status"] == "running"
    assert evaluation["full_state_write_performed"] is False


def test_parent_must_be_pinned_by_future_streaming_protocol(tmp_path: Path) -> None:
    protocol_path, digest = _fixture(tmp_path, pin_parent=False)
    with pytest.raises(RuntimeError, match="parent is not frozen"):
        parent.run_dry_pass(
            tmp_path,
            protocol_path,
            digest,
            1,
            batch_executor=_executor(digest),
        )
