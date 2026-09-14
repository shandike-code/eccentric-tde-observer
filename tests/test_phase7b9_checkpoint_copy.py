"""旧锚点 runner 字节冻结与新命名目标复制器的安全回归。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
OLD_SCRIPT = ROOT / "scripts/phase7b9_checkpoint_copy.py"
NEW_SCRIPT = ROOT / "scripts/phase7b9_new_checkpoint_copy.py"
OLD_RUNNER_SHA256 = "dabeddb16b0566f405d801116607a3e01205c651531f5288e7dc908c8d934b15"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


old_runner = load_module("phase7b9_checkpoint_copy_old_test", OLD_SCRIPT)
new_runner = load_module("phase7b9_checkpoint_copy_new_test", NEW_SCRIPT)


def write_bytes(root: Path, relative_path: str, content: bytes) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def frozen_new_protocol(
    root: Path,
) -> tuple[Path, str, str, str, str]:
    source_path = "outputs/source.dat"
    target_path = "outputs/new_anchor.dat"
    summary_path = "outputs/anchor_summary.json"
    runner_path = "scripts/phase7b9_new_checkpoint_copy.py"
    write_bytes(root, source_path, b"source00")
    write_bytes(root, runner_path, b"frozen-new-runner")
    protocol = {
        "phase": "test new-target checkpoint copy",
        "sources": {
            "source_state": {
                "path": source_path,
                "size_bytes": (root / source_path).stat().st_size,
                "sha256": new_runner._sha256(root / source_path),
            },
            "new_checkpoint_copy_runner": {
                "path": runner_path,
                "size_bytes": (root / runner_path).stat().st_size,
                "sha256": new_runner._sha256(root / runner_path),
            },
        },
        "configuration": {
            "source_state_path": source_path,
            "source_state_sha256": new_runner._sha256(root / source_path),
            "target_state_path": target_path,
            "target_previous_exists": False,
            "target_state_previous_sha256": None,
            "summary_path": summary_path,
            "postcopy_authorization_key": "continue_authorized",
        },
    }
    protocol_path = root / "outputs/copy_protocol.json"
    protocol_path.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    return (
        protocol_path,
        new_runner._sha256(protocol_path),
        source_path,
        target_path,
        runner_path,
    )


def fake_apfs_clone(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def copy(command: list[str], *, check: bool) -> None:
        assert check is True
        assert command[:2] == ["/bin/cp", "-c"]
        calls.append(command)
        shutil.copyfile(command[2], command[3])

    monkeypatch.setattr(new_runner.subprocess, "run", copy)
    return calls


def test_old_runner_bytes_match_the_frozen_ci_cm_protocols() -> None:
    assert old_runner._sha256(OLD_SCRIPT) == OLD_RUNNER_SHA256
    ci = json.loads(
        (ROOT / "outputs/phase7b9ci_preregistered_third_map_anchor.json").read_text()
    )
    cm = json.loads(
        (ROOT / "outputs/phase7b9cm_preregistered_fourth_map_anchor.json").read_text()
    )
    assert ci["sources"]["checkpoint_copy_runner"]["sha256"] == OLD_RUNNER_SHA256
    assert cm["sources"]["checkpoint_copy_runner"]["sha256"] == OLD_RUNNER_SHA256
    assert "target_previous_exists" not in OLD_SCRIPT.read_text()


def test_absent_target_is_created_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(new_runner, "ROOT", tmp_path)
    calls = fake_apfs_clone(monkeypatch)
    protocol_path, digest, source_path, target_path, _ = frozen_new_protocol(
        tmp_path
    )
    summary = new_runner.run(protocol_path, digest)
    assert len(calls) == 1
    assert (tmp_path / target_path).read_bytes() == (tmp_path / source_path).read_bytes()
    assert summary["gate_checks"]["target_created_from_absent"] is True
    assert summary["gate_checks"]["already_identical_recovery"] is False


def test_completed_new_target_recovers_without_recopying_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(new_runner, "ROOT", tmp_path)
    calls = fake_apfs_clone(monkeypatch)
    protocol_path, digest, _, _, _ = frozen_new_protocol(tmp_path)
    first = new_runner.run(protocol_path, digest)
    second = new_runner.run(protocol_path, digest)
    assert len(calls) == 1
    assert first["gate_checks"]["already_identical_recovery"] is False
    assert second["gate_checks"]["already_identical_recovery"] is True
    assert second["gate_checks"]["target_created_from_absent"] is False


def test_new_target_protocol_rejects_a_conflicting_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(new_runner, "ROOT", tmp_path)
    calls = fake_apfs_clone(monkeypatch)
    protocol_path, digest, _, target_path, _ = frozen_new_protocol(tmp_path)
    write_bytes(tmp_path, target_path, b"conflict")
    with pytest.raises(RuntimeError, match="exists but is not identical"):
        new_runner.run(protocol_path, digest)
    assert calls == []
    assert (tmp_path / target_path).read_bytes() == b"conflict"


def test_new_runner_strictly_rejects_any_changed_frozen_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(new_runner, "ROOT", tmp_path)
    fake_apfs_clone(monkeypatch)
    protocol_path, digest, _, _, runner_path = frozen_new_protocol(tmp_path)
    write_bytes(tmp_path, runner_path, b"changed-new-runner")
    with pytest.raises(RuntimeError, match="source changed"):
        new_runner.run(protocol_path, digest)
