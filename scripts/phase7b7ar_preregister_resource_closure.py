"""Phase 7B7a-r：冻结超限工作组的一块一进程资源闭合协议。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(path: str) -> dict[str, str]:
    return {"path": path, "sha256": _sha256(ROOT / path)}


def main() -> None:
    summary = json.loads(
        (OUTPUT / "phase7b7a_feedback_coefficients_summary.json").read_text(
            encoding="utf-8"
        )
    )
    decision = summary["decision"]
    for gate in (
        "frozen_protocol_source_and_state_hashes_passed",
        "worker_block_and_frequency_ownership_passed",
        "comoving_intensity_rates_and_arrays_valid",
        "rate_heating_vs_inverse_four_force_passed",
        "parent_mirror_symmetry_passed",
    ):
        if decision[gate] is not True:
            raise RuntimeError(f"Phase 7B7a-r requires passed science gate: {gate}")
    if decision["resource_and_runtime_gates_passed"] is not False:
        raise RuntimeError("Phase 7B7a-r is only the targeted resource-failure branch")
    reports = [
        json.loads((OUTPUT / f"phase7b7a_worker{index}.json").read_text())
        for index in range(1, 5)
    ]
    failed_owner_indices = [
        index
        for index, report in enumerate(reports)
        if float(report["peak_process_rss_mib"]) >= 6144.0
    ]
    if failed_owner_indices != [1, 2]:
        raise RuntimeError("Phase 7B7a-r frozen failed owners changed")
    target_blocks = {
        str(owner): [int(row["block_index"]) for row in reports[owner]["rows"]]
        for owner in failed_owner_indices
    }
    payload = {
        "phase": "7B7a-r isolated-block resource closure",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] rerun only the two over-limit owner sets with one block "
            "per short-lived process; [V] bitwise partial-array reproduction and RSS; "
            "[O] no matter update"
        ),
        "sources": {
            "phase7b7a_summary": _source(
                "outputs/phase7b7a_feedback_coefficients_summary.json"
            ),
            "phase7b7a_protocol": _source(
                "outputs/phase7b7a_preregistered_feedback_coefficients.json"
            ),
            "phase7b7a_runner": _source(
                "scripts/phase7b7a_feedback_coefficients.py"
            ),
            "phase7b7a_owner2_report": _source("outputs/phase7b7a_worker2.json"),
            "phase7b7a_owner3_report": _source("outputs/phase7b7a_worker3.json"),
            "phase7b7a_owner2_partial": _source(
                "outputs/phase7b7a_worker2_partial.npz"
            ),
            "phase7b7a_owner3_partial": _source(
                "outputs/phase7b7a_worker3_partial.npz"
            ),
        },
        "configuration": {
            "failed_owner_indices": failed_owner_indices,
            "target_blocks_by_owner": target_blocks,
            "target_block_count": sum(len(value) for value in target_blocks.values()),
            "blocks_per_short_lived_process": 1,
            "maximum_concurrent_processes": 2,
            "aggregation_order": "ascending block index within each original owner",
            "scientific_configuration_changed": False,
            "cellwise_clipping": False,
            "floor": False,
            "point_deletion": False,
            "posthoc_renormalization": False,
        },
        "gates": {
            "failed_owner_count_exactly": 2,
            "target_block_count_exactly": 38,
            "each_block_completed_exactly_once": True,
            "each_reaggregated_partial_maximum_absolute_difference_exactly": 0.0,
            "each_process_peak_rss_strictly_below_mib": 6144.0,
            "total_wall_time_strictly_below_s": 900.0,
        },
        "authorization": {
            "one_frozen_radiation_matter_update_if_passes": True,
            "further_resource_retry_if_fails": False,
            "fully_coupled_iteration": False,
            "full_orbit": False,
            "phase4_replacement": False,
        },
    }
    path = OUTPUT / "phase7b7ar_preregistered_resource_closure.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
