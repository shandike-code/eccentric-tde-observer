"""Measure the finite-difference signal, the inner noise and the linear regime.

Read-only. This is the stage-D design measurement described in
`handoff/linux-runs/2026-09-18-stage-d-finite-difference-design.md`: along a fixed
encoded direction d, the response signal at step h is

    signal(h) = || r(base + h*d) - r(base) ||

measured directly from recorded candidate residuals, and the inner noise is the
round-to-round difference of those residuals within the same chain (same material
candidate, different radiation convergence). Two checks decide whether a step is
usable for a JVP rebuild:

  1. signal/noise >= 10 (requirement fixed in the design record);
  2. linearity: signal/h at step h must agree with signal/(h/2) at h/2, i.e. the
     halved step must give the same signal per unit step.

Nothing here renormalises, clips or recomputes a physical quantity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "hpc"), str(ROOT / "src")]
import pipeline
from operations.collect_encoded_ratios import BASE_RESIDUAL

SIGNAL_TO_NOISE_REQUIRED = 10.0
LINEARITY_TOLERANCE = 0.20          # |signal/h ratio difference| allowed vs the halved step


def round_vectors(run_relative: str) -> dict[str, object]:
    """Recorded residual vectors per round, oldest first, with their endpoints."""
    run = pipeline.safe_path(ROOT, run_relative)
    state = pipeline.read(run / "state.json")
    residuals = {int(row["iteration"]): float(row["residual"]) for row in state.get("history", [])}
    rows = []
    for entry in state.get("diagnostic", {}).get("rounds", []):
        summary_path = (ROOT / entry["ledger"]).parent / "feedback_summary.json"
        summary = pipeline.read(summary_path)
        vector = np.asarray(np.load(ROOT / summary["encoded_residual_path"], allow_pickle=False),
                            dtype=np.float64)
        endpoints = [int(i) for i in entry.get("endpoints", [])]
        rows.append({"round": entry.get("round"), "endpoints": endpoints,
                     "endpoint_residuals": [residuals.get(i) for i in endpoints],
                     "vector": vector})
    raw_alpha = pipeline.read(run / "config.json").get("candidate_relaxation")
    return {"run": run_relative,
            "alpha": (float(raw_alpha) if raw_alpha is not None else None),
            "rounds": rows}


def candidate_measurement(run_relative: str, base_vector: np.ndarray) -> dict[str, object]:
    data = round_vectors(run_relative)
    rows = data["rounds"]
    if data["alpha"] is None or not np.isfinite(data["alpha"]) or data["alpha"] <= 0.0:
        return {"run": run_relative, "alpha": data["alpha"], "rounds": len(rows),
                "status": ("no candidate_relaxation recorded in config; step size is unknown, "
                           "so no per-step quantity is reported")}
    if not rows:
        return {"run": run_relative, "alpha": data["alpha"], "rounds": 0,
                "status": "no completed round"}
    signals = [float(np.linalg.norm(row["vector"] - base_vector)) for row in rows]
    noise = [float(np.linalg.norm(rows[i]["vector"] - rows[i - 1]["vector"]))
             for i in range(1, len(rows))]
    alpha = data["alpha"]
    return {"run": run_relative, "alpha": alpha, "rounds": len(rows),
            "last_endpoint_residuals": rows[-1]["endpoint_residuals"],
            "signal_last": signals[-1], "signal_first": signals[0],
            "signal_per_step_last": signals[-1] / alpha,
            "noise_last": (noise[-1] if noise else None),
            "noise_minimum": (min(noise) if noise else None),
            "signal_to_noise_last": (signals[-1] / noise[-1] if noise else None)}


def linearity_check(measurements: list[dict]) -> dict[str, object]:
    """Compare signal per unit step between successive tested step sizes."""
    usable = [row for row in measurements if row.get("signal_per_step_last")]
    usable.sort(key=lambda row: row["alpha"])
    pairs = []
    for coarse, fine in zip(usable[1:], usable[:-1]):
        ratio = fine["alpha"] / coarse["alpha"]
        coarse_rate = coarse["signal_per_step_last"]
        fine_rate = fine["signal_per_step_last"]
        pairs.append({"coarse_alpha": coarse["alpha"], "fine_alpha": fine["alpha"],
                      "step_ratio": ratio,
                      "coarse_signal_per_step": coarse_rate,
                      "fine_signal_per_step": fine_rate,
                      "relative_difference": abs(fine_rate - coarse_rate) / max(
                          abs(fine_rate), abs(coarse_rate)),
                      "linear": bool(abs(fine_rate - coarse_rate) / max(
                          abs(fine_rate), abs(coarse_rate)) <= LINEARITY_TOLERANCE
                          and abs(ratio - 0.5) <= 1e-9)})
    return {"pairs": pairs,
            "linearity_tolerance": LINEARITY_TOLERANCE,
            "halving_only": "only pairs whose step ratio is a half are judged"}


def recommendation(measurements: list[dict], linearity: dict) -> dict[str, object]:
    """Smallest tested step that clears both checks; never extrapolates below it."""
    # 通过半步自洽的一对里，两个步长都算"已在线性区"：细步长由与更粗步长的一致性背书。
    linear_alphas = set()
    for pair in linearity["pairs"]:
        if pair["linear"]:
            linear_alphas.update((pair["coarse_alpha"], pair["fine_alpha"]))
    candidates = [row for row in measurements
                  if row.get("signal_to_noise_last") is not None
                  and row["signal_to_noise_last"] >= SIGNAL_TO_NOISE_REQUIRED
                  and row["alpha"] in linear_alphas]
    if not candidates:
        return {"usable_step": None,
                "reason": "no tested step satisfies both signal/noise>=10 and the halving check",
                "signal_to_noise_required": SIGNAL_TO_NOISE_REQUIRED}
    best = min(candidates, key=lambda row: row["alpha"])
    return {"usable_step": best["alpha"], "run": best.get("run"),
            "signal_to_noise": best["signal_to_noise_last"],
            "signal_per_step": best["signal_per_step_last"],
            "signal_to_noise_required": SIGNAL_TO_NOISE_REQUIRED}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True,
                        help="candidate run with candidate_relaxation set (repeatable)")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    base_path = ROOT / BASE_RESIDUAL
    base_vector = np.asarray(np.load(base_path, allow_pickle=False), dtype=np.float64)
    measurements = [candidate_measurement(name, base_vector) for name in args.run]
    linearity = linearity_check(measurements)
    report = {"criterion": "signal(h)=||r(base+h*d)-r_base||; noise = round-to-round residual difference",
              "base_residual": {"path": BASE_RESIDUAL, "sha256": pipeline.sha256(base_path)},
              "measurements": measurements, "linearity": linearity,
              "recommendation": recommendation(measurements, linearity),
              "note": ("the usable step is the smallest tested step that clears both checks; "
                       "no step below the smallest tested one is ever asserted")}
    text = json.dumps(report, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
