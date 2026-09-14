"""未来2-worker整图协议的资源门与历史语义隔离回归。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9_protocol_builders.py"
SPEC = importlib.util.spec_from_file_location(
    "phase7b9_memory_safe_resource_builders", SCRIPT
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load Phase 7B9 protocol builders")
builders = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builders
SPEC.loader.exec_module(builders)


def write_bytes(root: Path, relative_path: str, content: bytes) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_json(root: Path, relative_path: str, payload: dict[str, object]) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def candidate_spec(
    root: Path, spec_type: type
) -> builders.CandidateMapProtocolSpec:
    for index, relative_path in enumerate(
        (
            builders.FINITE_TRIAL_PROTOCOL,
            builders.FINITE_TRIAL_MATERIAL,
            builders.MASTER_INPUT,
            builders.GENERIC_MAP_RUNNER,
            builders.MAP_WORKER,
            builders.WORKER_HELPERS,
            builders.MIXED_FRAME_OPERATOR,
            builders.MIXED_FRAME_FREQUENCY,
        )
    ):
        write_bytes(root, relative_path, f"source-{index}".encode())
    input_path = "outputs/checkpoints/candidate.dat"
    output_path = "outputs/checkpoints/scratch.dat"
    write_bytes(root, input_path, b"candidate")
    write_bytes(root, output_path, b"scratch00")
    summary_path = "outputs/candidate_summary.json"
    protocol_path = "outputs/candidate_protocol.json"
    write_json(
        root,
        summary_path,
        {
            "candidate_state_path": input_path,
            "candidate_state_sha256": builders.sha256(root / input_path),
            "decision": {
                "protected_slow_mode_candidate_passed": True,
                "fresh_original_operator_map_authorized": True,
                "material_feedback_authorized": False,
            },
        },
    )
    write_json(root, protocol_path, {"frozen": True})
    return spec_type(
        phase="future memory-safe candidate map",
        phase_index=1900,
        classification="[A-resource] fixed 3/2 wall-time scaling",
        candidate_summary_path=summary_path,
        candidate_protocol_path=protocol_path,
        candidate_summary_source_key="candidate_summary",
        candidate_protocol_source_key="candidate_protocol",
        output_state_path=output_path,
        manifest_path="outputs/checkpoints/future_candidate/manifest.json",
        report_directory="outputs/checkpoints/future_candidate/reports",
        summary_path="outputs/future_candidate_summary.json",
        figure_path="outputs/future_candidate.png",
        block_report_prefix="future_candidate",
        runner_path="scripts/future_candidate.py",
    )


def test_historical_candidate_builder_stays_three_workers_and_1200_s(
    tmp_path: Path,
) -> None:
    spec = candidate_spec(tmp_path, builders.CandidateMapProtocolSpec)
    payload = builders.build_candidate_map_protocol(tmp_path, spec)
    assert builders.MAXIMUM_CONCURRENT_PROCESSES == 3
    assert payload["configuration"]["maximum_concurrent_processes"] == 3
    assert payload["gates"]["full_map_wall_time_strictly_below_s"] == 1200.0
    assert "resource_gate_provenance" not in payload
    assert builders.seeded_two_map_gates()[
        "each_full_map_wall_time_strictly_below_s"
    ] == 1200.0


def test_future_candidate_builder_uses_only_resource_scaled_gate(
    tmp_path: Path,
) -> None:
    spec = candidate_spec(tmp_path, builders.MemorySafeCandidateMapProtocolSpec)
    payload = builders.build_memory_safe_candidate_map_protocol(tmp_path, spec)
    assert builders.MEMORY_SAFE_HEAVY_MAXIMUM_CONCURRENT_PROCESSES == 2
    assert payload["configuration"]["maximum_concurrent_processes"] == 2
    assert payload["gates"]["full_map_wall_time_strictly_below_s"] == 1800.0
    historical = builders.candidate_map_gates()
    for key, value in historical.items():
        if key != "full_map_wall_time_strictly_below_s":
            assert payload["gates"][key] == value
    provenance = payload["resource_gate_provenance"]
    assert provenance["classification"] == "[A-resource]"
    assert provenance["worker_count_scale_factor"] == 1.5
    assert provenance["threshold_from_observed"] is False
    assert provenance["scientific_gate_changed"] is False
