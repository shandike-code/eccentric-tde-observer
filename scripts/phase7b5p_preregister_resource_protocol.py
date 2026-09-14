"""Phase 7B5p：冻结 4816/9632 隔离进程资源审计协议。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCE_FILES = {
    "phase7b5o_protocol": OUTPUT / "phase7b5o_preregistered_protocol.json",
    "phase7b5o_summary": OUTPUT / "phase7b5o_summary.json",
    "phase7b5o_parent_choices": OUTPUT / "phase7b5o_parent_choices.csv",
}
EXPECTED_SHA256 = {
    "phase7b5o_protocol": (
        "ff63f6f46cd71c96089c714a600f8ef7a31d71bf92afd306aec743a89e94a176"
    ),
    "phase7b5o_summary": (
        "369ed77391cf746758f24906ba0c7d5d58838415e52ca2befed97efa35ae3790"
    ),
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def build_protocol() -> dict[str, object]:
    source_hashes = {
        name: _sha256_file(path) for name, path in SOURCE_FILES.items()
    }
    for name, expected in EXPECTED_SHA256.items():
        if source_hashes[name] != expected:
            raise RuntimeError(
                f"frozen {name} hash changed: {source_hashes[name]}"
            )
    summary = json.loads(SOURCE_FILES["phase7b5o_summary"].read_text())
    if summary["decision"]["one_cell_production_frequency_candidate_selected"]:
        raise RuntimeError("Phase 7B5o unexpectedly selected a production grid")
    return {
        "phase": "7B5p isolated-process resource decision support",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] exposed worst-state resource stress; "
            "[V] fresh-process runtime/RSS; [O] budget authorization"
        ),
        "sources": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": digest}
            for name, (path, digest) in zip(
                SOURCE_FILES,
                zip(SOURCE_FILES.values(), source_hashes.values()),
                strict=True,
            )
        },
        "representations": [
            {
                "label": "hierarchical P0, 4816",
                "key": "candidate",
                "physical_group_count": 4816,
                "active_edge_sha256": summary["grid"][
                    "sha256_after_validation"
                ],
            },
            {
                "label": "nested master, 9632",
                "key": "master",
                "physical_group_count": 9632,
            },
        ],
        "stress_state": {
            "case": "signed width change q80",
            "source_state_label": "converged",
            "reason": (
                "already-exposed Phase 7B5o worst candidate He II state; "
                "resource stress only, not an independent science holdout"
            ),
        },
        "measurement": {
            "fresh_process_per_run": True,
            "repeat_count_per_representation": 5,
            "worker_order": [
                "candidate",
                "master",
                "master",
                "candidate",
                "candidate",
                "master",
                "master",
                "candidate",
                "candidate",
                "master",
            ],
            "peak_metric": "ru_maxrss converted by operating-system convention",
            "runtime_metrics": [
                "operator wall time inside worker",
                "fresh worker process wall time",
            ],
            "reported_aggregates": [
                "median and maximum process peak RSS",
                "median operator and process runtime",
                "master-to-candidate ratios",
            ],
        },
        "integrity_gates": {
            "all_workers_exit_zero": True,
            "fresh_worker_pid_each_run": True,
            "deterministic_result_hash_within_representation": True,
            "returned_array_bytes_match_phase7b5o": True,
            "candidate_edge_hash_unchanged": True,
        },
        "authorization": {
            "frequency_budget_changed": False,
            "angle_or_radiation_subgrid_gate_authorized": False,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
            "uvot_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT / "phase7b5p_preregistered_resource_protocol.json",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {args.output}; pass --force")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(args.output, build_protocol())
    print(_sha256_file(args.output))


if __name__ == "__main__":
    main()
