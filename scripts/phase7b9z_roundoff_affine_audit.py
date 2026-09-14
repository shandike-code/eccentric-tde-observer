"""Phase 7B9z：审计极小物理残差下失去分辨率的仿射相对指标。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "0fd4b9ecdc81cdf13611d1acfeedf5f5ce9f20029b4d3a197778f316c743bf39"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    protocol_path = OUTPUT / "phase7b9z_preregistered_roundoff_affine_audit.json"
    if _sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9z protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if path.stat().st_size != source["size_bytes"] or _sha256(path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B9z source changed: {source['path']}")
    manifest = json.loads(
        (ROOT / protocol["sources"]["phase7b9t_stopped_manifest"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    by_block = {int(row["block_index"]): row for row in manifest["completed_blocks"]}
    rows = [by_block[int(index)] for index in protocol["configuration"]["selected_blocks"]]
    gates = protocol["gates"]
    checks = {
        "selected_block_count_pass": len(rows) == gates["selected_block_count_exactly"],
        "fresh_residuals_are_below_physical_resolution_gate": all(
            row["fresh_line_candidate_original_operator_residual"]
            < gates["fresh_original_operator_residual_below"]
            for row in rows
        ),
        "fresh_residual_improvement_is_strong": all(
            row["fresh_line_candidate_to_raw_residual_ratio"]
            < gates["fresh_candidate_to_raw_residual_ratio_below"]
            for row in rows
        ),
        "full_nonnegative_endpoints_were_used": all(
            row["endpoint_exact_nonnegative_step"]
            >= gates["endpoint_exact_nonnegative_step_at_least"]
            and row["line_selected_fraction"]
            >= gates["line_selected_fraction_at_least"]
            for row in rows
        ),
        "boundaries_do_not_worsen": all(
            row["fresh_line_candidate_to_raw_boundary_ratio"]
            <= gates["fresh_candidate_boundary_ratio_at_most"]
            for row in rows
        ),
        "candidates_are_nonnegative": all(
            row["minimum_line_candidate_intensity"]
            >= gates["minimum_line_candidate_intensity_at_least"]
            for row in rows
        ),
    }
    passed = all(checks.values())
    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), constrained_layout=True)
    block = np.asarray([row["block_index"] for row in rows])
    axes[0].semilogy(
        block,
        [row["fresh_line_candidate_original_operator_residual"] for row in rows],
        "o-",
        label="Fresh original residual",
    )
    axes[0].axhline(
        gates["fresh_original_operator_residual_below"],
        color="0.25",
        ls="--",
        label="Physical-resolution gate",
    )
    axes[0].set(
        xlabel="Natural frequency block",
        ylabel="Relative original-operator residual",
        title="(a) Direct physical residual",
    )
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].semilogy(
        block,
        [row["affine_prediction_to_fresh_residual_linf"] for row in rows],
        "s-",
        color="tab:orange",
        label="Residual-relative affine defect",
    )
    axes[1].axhline(2.0e-8, color="0.25", ls="--", label="Phase 7B9t gate")
    axes[1].set(
        xlabel="Natural frequency block",
        ylabel="Relative affine diagnostic",
        title="(b) Unresolved relative diagnostic",
    )
    axes[1].legend(frameon=False, fontsize=8)
    figure_path = OUTPUT / "phase7b9z_roundoff_affine_audit.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "selected_blocks": [row["block_index"] for row in rows],
        "maximum_fresh_original_operator_residual": max(
            row["fresh_line_candidate_original_operator_residual"] for row in rows
        ),
        "maximum_residual_improvement_ratio": max(
            row["fresh_line_candidate_to_raw_residual_ratio"] for row in rows
        ),
        "maximum_unresolved_affine_relative_diagnostic": max(
            row["affine_prediction_to_fresh_residual_linf"] for row in rows
        ),
        "gate_checks": checks,
        "decision": {
            "roundoff_resolution_audit_passed": passed,
            "selected_candidate_blocks_retained": passed,
            "phase7b9t_original_failure_status_preserved": True,
            "global_candidate_residual_authorized": False,
            "material_feedback_authorized": False,
        },
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b9z_roundoff_affine_audit_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
