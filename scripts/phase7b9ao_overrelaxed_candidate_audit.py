"""Phase 7B9ao：执行 theta=8 超松弛候选的独立全局审计。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from scripts import phase7b9ad_picard_contraction_audit as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9ad_picard_contraction_audit as generic  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "59fab2d15e842d767703d0a66eb847c83432abc46f3716785022e3286d76f648"
)


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    generic.EXPECTED_PROTOCOL_SHA256 = EXPECTED_PROTOCOL_SHA256
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9ao_preregistered_overrelaxed_candidate_audit.json",
    )
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--block-index", type=int)
    parser.add_argument("--input-state", type=Path)
    parser.add_argument("--input-sha256")
    parser.add_argument("--worker-report", type=Path)
    args = parser.parse_args()
    if args.worker:
        if (
            args.block_index is None
            or args.input_state is None
            or args.input_sha256 is None
            or args.worker_report is None
        ):
            raise ValueError("worker mode requires block, state/hash and report")
        generic._run_worker(
            args.protocol,
            args.block_index,
            args.input_state,
            args.input_sha256,
            args.worker_report,
        )
        return
    summary = generic.run(args.protocol)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    written = json.loads(
        (ROOT / protocol["sources"]["phase7b9an_summary"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    tolerance = protocol["gates"]["prediction_reproduction_absolute_tolerance"]
    reproduction = (
        abs(
            summary["mapped_state_global_original_operator_residual"]
            - written["predicted_global_original_operator_residual"]
        )
        <= tolerance
        and abs(
            summary["mapped_state_boundary_spectrum_l1"]
            - written["predicted_boundary_spectrum_l1"]
        )
        <= tolerance
        and abs(
            summary["mapped_state_boundary_bolometric_fraction"]
            - written["predicted_boundary_bolometric_fraction"]
        )
        <= tolerance
    )
    summary["gate_checks"]["prediction_reproduction_pass"] = reproduction
    mapping_valid = (
        summary["decision"]["positive_picard_contraction_audit_passed"]
        and reproduction
    )
    converged = mapping_valid and summary["gate_checks"]["global_residual_pass"]
    summary["decision"] = {
        "overrelaxed_candidate_global_audit_passed": mapping_valid,
        "prediction_reproduced": reproduction,
        "continue_positive_iteration_authorized": mapping_valid and not converged,
        "material_feedback_authorized": converged,
        "dynamic_nlte_solution_accepted": False,
    }
    _write_json_atomic(
        ROOT / protocol["configuration"]["summary_path"], summary
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
