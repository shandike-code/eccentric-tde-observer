"""Phase 7B9au：执行正性约束 Anderson 写后态独立审计。"""

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
EXPECTED_PROTOCOL_SHA256 = "860dcb776da22f27c02959bfbc111b962f9d5b16636fbb82bb58941a5d13eb4e"


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
        default=(
            OUTPUT / "phase7b9au_preregistered_constrained_anderson_audit.json"
        ),
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
        (ROOT / protocol["sources"]["phase7b9at_summary"]["path"]).read_text(
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
            - written["selected_boundary_spectrum_l1"]
        )
        <= tolerance
        and abs(
            summary["mapped_state_boundary_bolometric_fraction"]
            - written["selected_boundary_bolometric_fraction"]
        )
        <= tolerance
    )
    summary["gate_checks"]["prediction_reproduction_pass"] = reproduction
    mapping_valid = (
        summary["decision"]["positive_picard_contraction_audit_passed"]
        and reproduction
    )
    converged = mapping_valid and summary["gate_checks"]["global_residual_pass"]
    summary["classification"] = "[A-informed]+[A-preregistered]+[V]+[O]"
    summary["decision"] = {
        "constrained_anderson_candidate_global_audit_passed": mapping_valid,
        "prediction_reproduced": reproduction,
        "continue_positive_iteration_authorized": mapping_valid and not converged,
        "material_feedback_authorized": converged,
        "dynamic_nlte_solution_accepted": False,
    }
    _write_json_atomic(ROOT / protocol["configuration"]["summary_path"], summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
