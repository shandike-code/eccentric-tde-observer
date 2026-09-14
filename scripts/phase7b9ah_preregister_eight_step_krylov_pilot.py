"""Phase 7B9ah：冻结八步 Krylov 成本缩减小样。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SELECTED = {
    22: "low-energy slow-mode shoulder",
    26: "maximum absolute residual",
    45: "helium-region secondary residual",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _source(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def main() -> None:
    prior = json.loads(
        (OUTPUT / "phase7b9ag_current_state_krylov_pilot_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if prior["decision"]["current_state_krylov_pilot_passed"] is not True:
        raise RuntimeError("Phase 7B9ah requires the passed sixteen-step pilot")
    base_protocol = json.loads(
        (OUTPUT / "phase7b9ag_preregistered_current_state_krylov_pilot.json").read_text(
            encoding="utf-8"
        )
    )
    payload = base_protocol
    payload["phase"] = "7B9ah eight-step current-state Krylov cost pilot"
    payload["classification"] = (
        "[A-preregistered] halve the previously passed Krylov work budget from "
        "sixteen to eight iterations on three frozen representative blocks; [V] "
        "fresh residual, boundary, positivity and resource comparison; [O] no "
        "candidate state is written"
    )
    payload["sources"]["phase7b9ag_summary"] = _source(
        "outputs/phase7b9ag_current_state_krylov_pilot_summary.json"
    )
    payload["sources"]["phase7b9ag_protocol"] = _source(
        "outputs/phase7b9ag_preregistered_current_state_krylov_pilot.json"
    )
    payload["sources"]["generic_krylov_pilot_runner"] = _source(
        "scripts/phase7b9ag_current_state_krylov_pilot.py"
    )
    payload["configuration"]["selected_blocks"] = [
        {"block_index": index, "role": role} for index, role in SELECTED.items()
    ]
    payload["configuration"]["gmres_maximum_restart_cycles"] = 1
    payload["configuration"]["maximum_gmres_iterations"] = 8
    payload["configuration"]["report_prefix"] = "phase7b9ah"
    payload["configuration"]["runner_path"] = (
        "scripts/phase7b9ah_eight_step_krylov_pilot.py"
    )
    payload["configuration"]["figure_path"] = (
        "outputs/phase7b9ah_eight_step_krylov_pilot.png"
    )
    payload["configuration"]["summary_path"] = (
        "outputs/phase7b9ah_eight_step_krylov_pilot_summary.json"
    )
    payload["gates"]["selected_block_count_exactly"] = len(SELECTED)
    payload["gates"]["each_gmres_iteration_count_at_most"] = 8
    payload["gates"]["each_fresh_line_candidate_to_raw_residual_ratio_below"] = 0.25
    payload["gates"]["median_fresh_line_candidate_to_raw_residual_ratio_below"] = 0.10
    payload["authorization"] = {
        "eight_step_dominant_block_production_if_all_gates_pass": True,
        "write_candidate_state_in_pilot": False,
        "material_feedback": False,
        "accept_nonlinear_step": False,
        "accept_dynamic_nlte_solution": False,
    }
    path = OUTPUT / "phase7b9ah_preregistered_eight_step_krylov_pilot.json"
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    print(_sha256(path))


if __name__ == "__main__":
    main()
