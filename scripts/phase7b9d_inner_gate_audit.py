"""Phase 7B9d：审计首轮内迭代暴露的错误 ledger 准入门。"""

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
PROTOCOL_SHA256 = "812febafdc66a072c11ad00638034773bbb6c7dc39cd1e58a83551b26c0f59df"


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


def _report_family(prefix: str) -> dict[str, float | int]:
    rows = [
        json.loads(path.read_text())
        for path in sorted(OUTPUT.glob(f"{prefix}_block*.json"))
    ]
    if len(rows) != 76:
        raise RuntimeError(f"Phase 7B9d audit lost reports for {prefix}")
    local_change = [
        float(row["maximum_absolute_radiation_change"])
        / float(row["maximum_radiation_scale"])
        if float(row["maximum_radiation_scale"]) > 0.0
        else float(row["maximum_absolute_radiation_change"])
        for row in rows
    ]
    return {
        "block_count": len(rows),
        "maximum_block_local_change": max(local_change),
        "maximum_internal_coupled_residual": max(
            float(row["internal_global_coupled_residual"]) for row in rows
        ),
        "maximum_internal_energy_ledger_residual": max(
            float(row["internal_total_energy_ledger_residual"]) for row in rows
        ),
    }


def run() -> dict[str, object]:
    protocol_path = OUTPUT / "phase7b9d_preregistered_inner_converged_base_radiation.json"
    if _sha256(protocol_path) != PROTOCOL_SHA256:
        raise RuntimeError("Phase 7B9d frozen protocol changed")
    manifest_path = OUTPUT / "checkpoints/phase7b9d_work/inner_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["protocol_sha256"] != PROTOCOL_SHA256
        or int(manifest["current_additional_map"]) != 1
        or len(manifest["history"]) != 1
    ):
        raise RuntimeError("Phase 7B9d committed audit state changed")
    snapshot_path = OUTPUT / "phase7b9d_inner_gate_audit_snapshot.json"
    _write_json_atomic(snapshot_path, manifest)
    families = {
        "Phase 7B7i": _report_family("phase7b7i"),
        "Phase 7B8b": _report_family("phase7b8b"),
        "Phase 7B8e": _report_family("phase7b8e"),
    }
    new_reports = [
        json.loads(path.read_text())
        for path in sorted(
            (OUTPUT / "checkpoints/phase7b9d_work/reports").glob("map01_block*.json")
        )
    ]
    if len(new_reports) != 76:
        raise RuntimeError("Phase 7B9d first committed map reports are incomplete")
    local_change = [
        float(row["maximum_absolute_radiation_change"])
        / float(row["maximum_radiation_scale"])
        if float(row["maximum_radiation_scale"]) > 0.0
        else float(row["maximum_absolute_radiation_change"])
        for row in new_reports
    ]
    families["Phase 7B9d"] = {
        "block_count": len(new_reports),
        "maximum_block_local_change": max(local_change),
        "maximum_internal_coupled_residual": max(
            float(row["internal_global_coupled_residual"]) for row in new_reports
        ),
        "maximum_internal_energy_ledger_residual": max(
            float(row["internal_total_energy_ledger_residual"]) for row in new_reports
        ),
    }
    first = manifest["history"][0]
    phase7b6p = json.loads(
        (OUTPUT / "phase7b6p_final_formal_flux_summary.json").read_text()
    )
    ledger_history = [
        float(value["maximum_internal_energy_ledger_residual"])
        for value in families.values()
    ]
    invariant_ledger = bool(min(ledger_history) > 0.95 and max(ledger_history) < 0.99)
    prior_science_pass_with_large_ledger = bool(
        all(float(row["maximum_block_energy_ledger_residual"]) > 0.95 for row in phase7b6p["states"])
        and phase7b6p["decision"]["formal_face_flux_spectrum_gate_passed"]
        and phase7b6p["decision"]["formal_face_bolometric_gate_passed"]
    )
    original_gate_valid = False
    decision = {
        "frozen_protocol_and_committed_state_passed": True,
        "first_full_frequency_map_preserved": True,
        "first_map_boundary_science_functionals_passed": bool(
            first["boundary_flux_spectrum_l1"] < 1.0e-3
            and first["boundary_flux_bolometric_fraction"] < 1.0e-3
        ),
        "ledger_diagnostic_invariant_across_prior_directional_maps": invariant_ledger,
        "prior_science_flux_passed_with_same_large_ledger": prior_science_pass_with_large_ledger,
        "original_internal_ledger_gate_valid": original_gate_valid,
        "continue_original_protocol_authorized": False,
        "corrected_science_functional_continuation_design_authorized": bool(
            invariant_ledger and prior_science_pass_with_large_ledger
        ),
        "formal_feedback_evaluated": False,
        "encoded_newton_residual_evaluated": False,
        "full_frequency_jv_evaluated": False,
        "accepted_as_dynamic_NLTE_solution": False,
    }
    labels = list(families)
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.0), constrained_layout=True)
    axes[0, 0].bar(
        labels,
        [families[label]["maximum_internal_energy_ledger_residual"] for label in labels],
        color="#9b6b5a",
    )
    axes[0, 0].axhline(1.0e-8, color="0.25", ls="--", label="Invalid preregistered gate")
    axes[0, 0].set(
        ylabel="Maximum block diagnostic",
        title="(a) One-map internal ledger is invariant near unity",
        ylim=(0.0, 1.05),
    )
    axes[0, 0].tick_params(axis="x", rotation=20)
    axes[0, 0].legend(frameon=False)
    axes[0, 1].bar(
        (0, 1, 2),
        (
            first["raw_source_map_residual"],
            first["boundary_flux_spectrum_l1"],
            first["boundary_flux_bolometric_fraction"],
        ),
        color=("#507ba6", "#5f9d82", "#92a85c"),
    )
    axes[0, 1].axhline(1.0e-3, color="0.25", ls="--", label="Boundary gate")
    axes[0, 1].set_yscale("log")
    axes[0, 1].set(
        xticks=(0, 1, 2),
        xticklabels=("Global source\nchange", "Boundary\nspectral L1", "Boundary\nbolometric"),
        ylabel="Successive-state metric",
        title="(b) First new map carries useful convergence evidence",
    )
    axes[0, 1].legend(frameon=False)
    axes[1, 0].bar(
        (0, 1),
        (
            max(float(row["maximum_block_energy_ledger_residual"]) for row in phase7b6p["states"]),
            float(phase7b6p["formal_face_flux_spectrum_l1"]),
        ),
        color=("#9b6b5a", "#5f9d82"),
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set(
        xticks=(0, 1),
        xticklabels=("One-map internal\nledger", "Formal boundary\nspectral L1"),
        ylabel="Diagnostic value",
        title="(c) Phase 7B6p already separated these diagnostics",
    )
    axes[1, 1].axis("off")
    axes[1, 1].text(
        0.04,
        0.95,
        "(d) Audit decision\n\n"
        "Committed 9632x32x4096 map: preserved\n"
        "Original ledger admission gate: invalid\n"
        "Original protocol continuation: stopped\n"
        "Corrected rate/heating functional gate: required\n\n"
        "No clipping, floor, or point deletion",
        transform=axes[1, 1].transAxes,
        va="top",
        fontsize=11,
    )
    figure_path = OUTPUT / "phase7b9d_inner_gate_audit.png"
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    report = {
        "phase": "7B9d first-map inner-gate audit",
        "classification": "[V]+[O]",
        "protocol_sha256": PROTOCOL_SHA256,
        "committed_additional_source_maps": 1,
        "committed_radiation_path": manifest["current_state_path"],
        "committed_radiation_sha256": manifest["current_state_sha256"],
        "first_map_metrics": first,
        "directional_map_family_diagnostics": families,
        "phase7b6p_formal_flux_spectrum_l1": phase7b6p[
            "formal_face_flux_spectrum_l1"
        ],
        "phase7b6p_formal_flux_bolometric_fraction": phase7b6p[
            "formal_face_bolometric_fraction"
        ],
        "snapshot_path": str(snapshot_path.relative_to(ROOT)),
        "snapshot_sha256": _sha256(snapshot_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b9d_inner_gate_audit_summary.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
