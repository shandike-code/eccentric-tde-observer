"""7B9dj memory-only 双重 block34 rerun 的 tmp_path 测试。"""

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

from scripts import phase7b9dj_memory_only_block_rerun as rerun


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


def _fixture(root: Path) -> tuple[Path, str, Path, Path, Path]:
    _write(root / rerun.RUNNER_RELATIVE_PATH, b"memory-only runner")
    _write(root / "scripts/di.py", b"frozen di runner")
    _write(root / "outputs/material.npz", b"material")
    material = _source(root, "outputs/material.npz")
    _write(root / "outputs/fixed.json", {"sources": {"current_material_state": material}})
    protocol = {
        "sources": {
            "progression_continuation_runner": _source(root, "scripts/di.py"),
            "finite_trial_protocol": _source(root, "outputs/fixed.json"),
            "finite_trial_material": material,
        },
        "configuration": {
            "physical_frequency_groups": 76,
            "angular_direction_count": 1,
            "radiation_depth_cell_count": 1,
        },
    }
    protocol_path = root / "outputs/di_protocol.json"
    _write(protocol_path, protocol)
    protocol_sha = _sha(protocol_path.read_bytes())
    a_path = root / "outputs/A.dat"
    b_path = root / "outputs/B.dat"
    np.ones((76, 1, 1), dtype=np.float64).tofile(a_path)
    np.full((76, 1, 1), 3.0, dtype=np.float64).tofile(b_path)
    a_sha = _sha(a_path.read_bytes())
    b_sha = _sha(b_path.read_bytes())
    records = [{"iteration": index} for index in range(20)]
    records.append(
        {
            "iteration": 20,
            "input_state_path": "outputs/A.dat",
            "input_state_sha256": a_sha,
            "mapped_state_path": "outputs/B.dat",
            "mapped_state_sha256": b_sha,
        }
    )
    manifest_path = root / "outputs/di_manifest.json"
    _write(
        manifest_path,
        {
            "protocol_sha256": protocol_sha,
            "status": "gate_failed",
            "active_iteration": None,
            "iterations": records,
        },
    )
    return protocol_path, protocol_sha, manifest_path, a_path, b_path


def _fake_executor(mapped_sha: str, *, second_sha: str | None = None):
    calls = 0

    def execute(
        input_path: Path,
        input_sha: str,
        virtual_output: Path,
        block_index: int,
        start: int,
        stop: int,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        assert input_path.exists()
        assert len(input_sha) == 64
        assert not virtual_output.exists()
        assert (block_index, start, stop) == (34, 34, 35)
        return {
            "block_relative_radiation_change": 9.716e-4,
            "maximum_absolute_radiation_change": 9.716e-4,
            "maximum_radiation_scale": 1.0,
            "in_memory_rerun_block_sha256": (
                second_sha if calls == 2 and second_sha is not None else mapped_sha
            ),
        }

    return execute


def test_sparse_memory_sink_accepts_only_expected_core() -> None:
    sink = rerun.MemoryOnlyBlockSink(slice(34, 35))
    mapped = np.ones((1, 2, 3), dtype=np.float64)
    sink[slice(34, 35)] = mapped
    sink.flush()
    assert np.array_equal(sink.mapped, mapped)
    assert sink.flush_count == 1
    with pytest.raises(RuntimeError, match="more than one write"):
        sink[slice(34, 35)] = mapped


def test_cli_writes_two_rerun_summary_without_virtual_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol, digest, manifest, a_path, b_path = _fixture(tmp_path)
    a_before = a_path.read_bytes()
    b_before = b_path.read_bytes()
    mapped_sha = _sha(b"deterministic mapped block")
    executor = _fake_executor(mapped_sha)
    monkeypatch.setattr(
        rerun,
        "_default_attempt_executor",
        lambda *args, **kwargs: executor,
    )
    output = tmp_path / "outputs/rerun_summary.json"
    rerun.main(
        [
            "--di-protocol",
            str(protocol.relative_to(tmp_path)),
            "--expected-di-protocol-sha256",
            digest,
            "--di-manifest",
            str(manifest.relative_to(tmp_path)),
            "--output",
            str(output.relative_to(tmp_path)),
            "--natural-frequency-block-width",
            "1",
        ],
        root=tmp_path,
    )
    payload = json.loads(output.read_text())
    rows = payload["independent_memory_only_reruns"]
    assert len(rows) == 2
    assert rows[0]["in_memory_rerun_block_sha256"] == mapped_sha
    assert rows[1]["in_memory_rerun_block_sha256"] == mapped_sha
    assert payload["output_persisted"] is False
    assert payload["input_modified"] is False
    assert not list(output.parent.glob(".virtual_block34_attempt*.dat"))
    assert a_path.read_bytes() == a_before
    assert b_path.read_bytes() == b_before
    assert payload["sources"]["di_protocol"]["sha256"] == digest
    assert payload["sources"]["di_progression_runner"]["path"] == "scripts/di.py"


def test_disagreeing_memory_reruns_fail_without_summary(tmp_path: Path) -> None:
    protocol, digest, manifest, _, _ = _fixture(tmp_path)
    output = tmp_path / "outputs/rerun_summary.json"
    with pytest.raises(RuntimeError, match="did not isolate"):
        rerun.run_two_memory_only_reruns(
            tmp_path,
            protocol,
            digest,
            manifest,
            output,
            natural_frequency_block_width=1,
            attempt_executor=_fake_executor(_sha(b"one"), second_sha=_sha(b"two")),
        )
    assert not output.exists()
