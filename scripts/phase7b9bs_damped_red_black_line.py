"""Phase 7B9bs：评估并写入全局阻尼的红黑候选。"""

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
EXPECTED_PROTOCOL_SHA256 = "1705f9445b4a99983c370eb5e150ed17b3a78cf06fddd75131372c8925420c41"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    protocol_path = OUTPUT / "phase7b9bs_preregistered_damped_red_black_line.json"
    if _sha256(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9bs protocol changed")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        path = ROOT / source["path"]
        if path.stat().st_size != source["size_bytes"] or _sha256(path) != source["sha256"]:
            raise RuntimeError(f"Phase 7B9bs source changed: {source['path']}")
    cfg = protocol["configuration"]
    gates = protocol["gates"]
    shape = tuple(int(value) for value in cfg["shape"])
    y = np.memmap(ROOT / cfg["base_state_path"], mode="r", dtype=np.float64, shape=shape)
    fy = np.memmap(ROOT / cfg["base_map_path"], mode="r", dtype=np.float64, shape=shape)
    z = np.memmap(ROOT / cfg["cycle_state_path"], mode="r", dtype=np.float64, shape=shape)
    fz = np.memmap(ROOT / cfg["cycle_map_path"], mode="r", dtype=np.float64, shape=shape)
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
        # 红黑方向只作全局凸阻尼；不对任何单元裁剪或重归一化。
        states = yc[None, :] + eta[:, None] * (zc - yc)[None, :]
        maps = fyc[None, :] + eta[:, None] * (fzc - fyc)[None, :]
        numerator = np.maximum(numerator, np.max(np.abs(maps - states), axis=1))
        scale = np.maximum(scale, np.maximum(np.max(states, axis=1), np.max(maps, axis=1)))
        minimum_state = np.minimum(minimum_state, np.min(states, axis=1))
        minimum_map = np.minimum(minimum_map, np.min(maps, axis=1))
        if start % 1024 == 0:
            print(json.dumps({"scanned_frequency_groups": stop, "total": shape[0]}), flush=True)
    residual = numerator / scale
    selected_index = int(np.argmin(residual))
    selected_eta = float(eta[selected_index])
    base_residual = float(residual[0])
    ratio = float(residual[selected_index] / base_residual)
    checks = {
        "positive_line_pass": bool(np.all(minimum_state >= gates["minimum_candidate_and_modeled_map_intensity_at_least"]) and np.all(minimum_map >= gates["minimum_candidate_and_modeled_map_intensity_at_least"])),
        "nonzero_step_pass": selected_eta > gates["selected_eta_strictly_above"],
        "modeled_contraction_pass": ratio < gates["modeled_residual_contraction_ratio_below"],
    }
    write_candidate = all(checks.values())
    output_path = ROOT / cfg["candidate_output_path"]
    if _sha256(output_path) != cfg["candidate_output_previous_sha256"]:
        raise RuntimeError("Phase 7B9bs cycle state changed before write")
    if write_candidate:
        output = np.memmap(output_path, mode="r+", dtype=np.float64, shape=shape)
        for start in range(0, shape[0], chunk):
            stop = min(start + chunk, shape[0])
            output[start:stop] = y[start:stop] + selected_eta * (z[start:stop] - y[start:stop])
        output.flush()
        del output
    output_sha = _sha256(output_path)
    figure_path = ROOT / cfg["figure_path"]
    figure, axis = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
    axis.semilogy(eta, residual, "o-")
    axis.axhline(gates["fixed_matter_convergence_target"], color="tab:red", ls="--", label="Fixed-matter target")
    axis.set(xlabel="Red-black damping fraction", ylabel="Modeled original-operator residual", title="Global damping of red-black Krylov cycle")
    axis.legend(frameon=False)
    figure.savefig(figure_path, dpi=180)
    plt.close(figure)
    summary = {
        "phase": protocol["phase"], "classification": "[A-preregistered]+[V]+[O]", "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "eta_grid": eta.tolist(), "modeled_global_original_operator_residuals": residual.tolist(), "selected_eta": selected_eta,
        "base_global_original_operator_residual": base_residual, "selected_modeled_global_original_operator_residual": float(residual[selected_index]), "modeled_residual_contraction_ratio": ratio,
        "minimum_candidate_intensities": minimum_state.tolist(), "minimum_modeled_map_intensities": minimum_map.tolist(), "gate_checks": checks,
        "candidate_state_path": cfg["candidate_output_path"] if write_candidate else None, "candidate_state_sha256": output_sha if write_candidate else None, "candidate_written": write_candidate,
        "decision": {"fresh_global_original_operator_audit_authorized": write_candidate, "fixed_matter_convergence_claimed": False, "material_feedback_authorized": False},
        "figures": [figure_path.name],
    }
    summary_path = ROOT / cfg["summary_path"]
    temporary = summary_path.with_name(f"{summary_path.name}.tmp")
    temporary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    os.replace(temporary, summary_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
