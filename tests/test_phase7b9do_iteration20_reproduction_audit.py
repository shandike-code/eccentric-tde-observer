from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase7b9do_iteration20_reproduction_audit.py"
SPEC = importlib.util.spec_from_file_location("phase7b9do", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _fixture(tmp_path: Path) -> dict[str, Path]:
    input_sha = "input-sha"
    failed_sha = "failed-output-sha"
    fresh_sha = "fresh-output-sha"
    failed_block_sha = "failed-block-34"
    memory_sha = "fresh-block-34"

    row19 = {
        "iteration": 19,
        "input_state_sha256": "previous-sha",
        "mapped_state_sha256": input_sha,
        "global_original_operator_residual": 2.0e-3,
        "contraction_ratio": 0.95,
        "boundary_spectrum_l1": 6.0e-4,
        "boundary_bolometric_fraction": 5.9e-4,
        "frequency_ownership_exact": True,
        "block_report_count": 76,
        "progression_passed": True,
        "progression_gate_checks": {"contraction_pass": True},
    }
    original = {
        "iteration": 20,
        "input_state_sha256": input_sha,
        "mapped_state_sha256": failed_sha,
        "global_original_operator_residual": 1.4e-2,
        "contraction_ratio": 7.0,
        "boundary_spectrum_l1": 5.5e-4,
        "boundary_bolometric_fraction": 5.4e-4,
        "frequency_ownership_exact": True,
        "block_report_count": 76,
        "progression_passed": False,
        "progression_gate_checks": {"contraction_pass": False},
    }
    di = _write(
        tmp_path / "di.json",
        {"status": "gate_failed", "iterations": [row19, original]},
    )
    dj_audit = _write(
        tmp_path / "dj_audit.json",
        {
            "failed_map": {"mapped_state_sha256": failed_sha},
            "decision": {"unreproducible_block_index": 34},
        },
    )
    reruns = [
        {
            "attempt": attempt,
            "in_memory_rerun_block_sha256": memory_sha,
            "output_persisted": False,
            "input_modified": False,
        }
        for attempt in (1, 2)
    ]
    dj_memory = _write(
        tmp_path / "dj_memory.json",
        {
            "failed_persisted_block_sha256": failed_block_sha,
            "independent_memory_only_reruns": reruns,
            "decision": {"single_block_repair_authorized": False},
        },
    )
    metrics = {
        "frequency_ownership_count": 9632,
        "frequency_ownership_exact": True,
        "global_original_operator_residual": 1.8e-3,
        "contraction_ratio": 0.9,
        "boundary_spectrum_l1": 5.0e-4,
        "boundary_bolometric_fraction": 4.9e-4,
        "minimum_input_intensity": 0.0,
        "minimum_mapped_intensity": 0.0,
    }
    dk = _write(
        tmp_path / "dk.json",
        {
            "protocol_sha256": "protocol-sha",
            "status": "reproduction_passed",
            "immutable_input_sha256": input_sha,
            "fresh_output_sha256": fresh_sha,
            "failed_output_previous_sha256": failed_sha,
            "block_report_count": 76,
            "block_reports_retained": True,
            "metrics": metrics,
            "progression_gate_checks": {
                "contraction_pass": True,
                "positive_map_pass": True,
                "resources_pass": True,
            },
            "convergence_gate_checks": {
                "residual_pass": False,
                "boundary_spectrum_pass": True,
                "boundary_bolometric_pass": True,
            },
            "decision": {
                "full_76_block_reproduction_passed": True,
                "single_block_repair_used": False,
            },
        },
    )

    dl_rows = []
    residuals = [1.8e-3, 1.7e-3, 1.6e-3, 1.5e-3]
    for offset, residual in enumerate(residuals):
        iteration = 20 + offset
        dl_rows.append(
            {
                "iteration": iteration,
                "mapped_state_sha256": fresh_sha if iteration == 20 else f"tail-{iteration}",
                "global_original_operator_residual": residual,
                "contraction_ratio": 0.9 if iteration == 20 else residual / residuals[offset - 1],
                "boundary_spectrum_l1": 5.0e-4 - offset * 2.0e-5,
                "boundary_bolometric_fraction": 4.9e-4 - offset * 2.0e-5,
            }
        )
    dl = _write(
        tmp_path / "dl.json",
        {
            "status": "maximum_maps_exhausted",
            "iterations": dl_rows,
            "rejected_evidence": {
                "record": {"mapped_state_sha256": failed_sha},
                "may_enter_valid_history": False,
            },
            "decision": {
                "fresh_dk_reproduction_used_as_iteration20": True,
                "failed_di_iteration20_used_as_valid_history": False,
            },
        },
    )

    reports = tmp_path / "reports"
    for block in range(76):
        start = (9632 * block) // 76
        stop = (9632 * (block + 1)) // 76
        previous = failed_block_sha if block == 34 else f"block-{block}"
        new = memory_sha if block == 34 else previous
        _write(
            reports / f"phase7b9dk_block{block:02d}.json",
            {
                "protocol_sha256": "protocol-sha",
                "input_state_sha256": input_sha,
                "block_index": block,
                "core_group_start": start,
                "core_group_stop": stop,
                "previous_block_sha256": previous,
                "new_block_sha256": new,
                "block_relative_radiation_change": 1.0e-3,
            },
        )
    return {
        "di_path": di,
        "dj_audit_path": dj_audit,
        "dj_memory_path": dj_memory,
        "dk_path": dk,
        "dl_path": dl,
        "reports_dir": reports,
    }


def test_build_audit_accepts_full_reproduction_with_only_block34_changed(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    audit = MODULE.build_audit(tmp_path, **paths)
    reports = audit["fresh_full_76_block_reproduction"]["reports"]
    assert reports["count"] == 76
    assert reports["differing_block_indices"] == [34]
    assert reports["unchanged_block_count"] == 75
    assert audit["scope"]["full_state_bytes_read"] is False
    assert audit["decision"]["single_block_repair_used"] is False


def test_build_audit_rejects_a_second_changed_block(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    report35 = paths["reports_dir"] / "phase7b9dk_block35.json"
    value = json.loads(report35.read_text(encoding="utf-8"))
    value["new_block_sha256"] = "unexpected-second-change"
    _write(report35, value)
    with pytest.raises(ValueError, match="only block 34"):
        MODULE.build_audit(tmp_path, **paths)


def test_build_audit_rejects_single_block_repair_authority(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    value = json.loads(paths["dj_memory_path"].read_text(encoding="utf-8"))
    value["decision"]["single_block_repair_authorized"] = True
    _write(paths["dj_memory_path"], value)
    with pytest.raises(ValueError, match="single-block repair was authorized"):
        MODULE.build_audit(tmp_path, **paths)


def test_small_json_reader_refuses_dat_even_when_contents_are_json(tmp_path: Path) -> None:
    fake_state = tmp_path / "forbidden.dat"
    fake_state.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="refusing non-JSON input"):
        MODULE._read_small_json(fake_state)


def test_write_audit_creates_small_json_and_english_figure(tmp_path: Path) -> None:
    paths = _fixture(tmp_path)
    audit = MODULE.build_audit(tmp_path, **paths)
    output_json = tmp_path / "audit.json"
    output_figure = tmp_path / "audit.png"
    MODULE.write_audit(audit, output_json, output_figure)
    saved = json.loads(output_json.read_text(encoding="utf-8"))
    assert saved["decision"]["original_iteration20_rejected"] is True
    assert output_figure.stat().st_size > 10_000
