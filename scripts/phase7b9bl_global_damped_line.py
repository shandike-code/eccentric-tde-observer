"""Phase 7B9bl：计算并写入全局阻尼的正强度候选。"""

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
EXPECTED_PROTOCOL_SHA256 = "5894876aa7023b8800ff88e1b64bbce16e68ad81d3e8d1705f8fec2d611c7154"


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
    protocol_path = OUTPUT / "phase7b9bl_preregistered_global_damped_line.json"
    if _sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bl protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if path.stat().st_size != source["size_bytes"] or _sha256(path) != source["sha256"]:
            raise RuntimeError(f"Phase 7B9bl source changed: {source['path']}")
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = (
        int(cfg["physical_frequency_groups"]),
        int(cfg["angular_direction_count"]),
        int(cfg["radiation_depth_cell_count"]),
    )
    y = np.memmap(ROOT / cfg["base_state_path"], mode="r", dtype=np.float64, shape=shape)
    fy = np.memmap(ROOT / cfg["base_map_path"], mode="r", dtype=np.float64, shape=shape)
    z = np.memmap(ROOT / cfg["trial_state_path"], mode="r", dtype=np.float64, shape=shape)
    fz = np.memmap(ROOT / cfg["trial_map_path"], mode="r", dtype=np.float64, shape=shape)
    eta = np.asarray(cfg["eta_grid_exact"], dtype=np.float64)
    numerator = np.zeros(eta.size)
    scale = np.zeros(eta.size)
    minimum_state = np.full(eta.size, np.inf)
    minimum_map = np.full(eta.size, np.inf)
    chunk = int(cfg["frequency_chunk"])
    for start in range(0, shape[0], chunk):
        stop = min(start + chunk, shape[0])
        yc = np.asarray(y[start:stop]).reshape(-1)
        fyc = np.asarray(fy[start:stop]).reshape(-1)
        zc = np.asarray(z[start:stop]).reshape(-1)
        fzc = np.asarray(fz[start:stop]).reshape(-1)
        # 固定物质场下，用两端完整算子像预测凸组合残差；随后仍做真实映射审计。
        states = yc[None, :] + eta[:, None] * (zc - yc)[None, :]
        maps = fyc[None, :] + eta[:, None] * (fzc - fyc)[None, :]
        numerator = np.maximum(numerator, np.max(np.abs(maps - states), axis=1))
        scale = np.maximum(scale, np.maximum(np.max(states, axis=1), np.max(maps, axis=1)))
        minimum_state = np.minimum(minimum_state, np.min(states, axis=1))
        minimum_map = np.minimum(minimum_map, np.min(maps, axis=1))
        if start % (128 * chunk) == 0:
            print(json.dumps({"scanned_frequency_groups": stop, "total": shape[0]}), flush=True)
    residual = np.divide(numerator, scale, out=numerator.copy(), where=scale > 0.0)
    selected_index = int(np.argmin(residual))
    selected_eta = float(eta[selected_index])
    base_residual = float(residual[0])
    ratio = float(residual[selected_index] / base_residual)
    checks = {
        "positive_convex_line_pass": bool(
            np.all(minimum_state >= gates["minimum_candidate_and_modeled_map_intensity_at_least"])
            and np.all(minimum_map >= gates["minimum_candidate_and_modeled_map_intensity_at_least"])
        ),
        "nonzero_step_pass": selected_eta > gates["selected_eta_strictly_above"],
        "modeled_contraction_pass": ratio < gates["modeled_residual_contraction_ratio_below"],
    }
    write_candidate = all(checks.values())
    output_path = ROOT / cfg["candidate_output_path"]
    old_sha = _sha256(output_path)
    if old_sha != cfg["candidate_output_previous_sha256"]:
        raise RuntimeError("Phase 7B9bl rejected trial checkpoint changed")
    if write_candidate:
        output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
        for start in range(0, shape[0], chunk):
            stop = min(start + chunk, shape[0])
            output[start:stop] = y[start:stop] + selected_eta * (z[start:stop] - y[start:stop])
        output.flush()
        del output
    candidate_sha = _sha256(output_path)
    figure_path = ROOT / cfg["figure_path"]
    figure, axis = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    axis.semilogy(eta, residual, "o-")
    axis.axhline(gates["fixed_matter_convergence_target"], color="tab:red", ls="--", label="Fixed-matter target")
    axis.set(xlabel="Global damping fraction", ylabel="Modeled original-operator residual", title="Global damping of targeted block correction")
    axis.legend(frameon=False)
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "eta_grid": eta.tolist(),
        "modeled_global_original_operator_residuals": residual.tolist(),
        "minimum_candidate_intensities": minimum_state.tolist(),
        "minimum_modeled_map_intensities": minimum_map.tolist(),
        "selected_eta": selected_eta,
        "base_global_original_operator_residual": base_residual,
        "selected_modeled_global_original_operator_residual": float(residual[selected_index]),
        "modeled_residual_contraction_ratio": ratio,
        "gate_checks": checks,
        "candidate_state_path": cfg["candidate_output_path"],
        "candidate_state_sha256": candidate_sha,
        "candidate_written": write_candidate,
        "decision": {
            "fresh_global_original_operator_audit_authorized": write_candidate,
            "fixed_matter_convergence_claimed": False,
            "material_feedback_authorized": False,
        },
        "figures": [figure_path.name],
    }
    _write_json_atomic(ROOT / cfg["summary_path"], summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
