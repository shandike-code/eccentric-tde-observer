"""Collect the candidate-to-base encoded residual ratio from recorded feedback.

This is the single criterion the small-step descent test is judged by:

    ratio(alpha) = ||r(candidate)||_2 / ||r(base)||_2

with `r(base) = outputs/phase7b9f_base_material_residual.npy`. The tool reads
only recorded artifacts (state.json, each round's feedback_summary.json and
material_residual.npy); it never recomputes a material response, never touches an
acceptance gate, and never rewrites history.

Both layouts are supported: interval-driven runs keep one summary per round under
`feedback-roundN/`, while `hpc/pipeline.py` runs keep a single summary at the run
root.
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

BASE_RESIDUAL = "outputs/phase7b9f_base_material_residual.npy"


def ratio_of(residual_path: Path, base_l2: float) -> dict[str, object]:
    """L2 ratio of one recorded residual; no renormalisation, no flooring."""
    vector = np.load(residual_path, allow_pickle=False)
    values = np.asarray(vector, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"recorded residual is not finite: {residual_path}")
    l2 = float(np.linalg.norm(values))
    if base_l2 <= 0.0:
        raise ValueError("base residual has no positive L2")
    return {"residual_path": pipeline.relative(residual_path), "components": int(values.size),
            "l2": l2, "ratio_to_base": l2 / base_l2, "sha256": pipeline.sha256(residual_path)}


def collect_round(run_dir: Path, summary_path: Path, base_l2: float) -> dict[str, object]:
    summary = pipeline.read(summary_path)
    residual_path = ROOT / summary["encoded_residual_path"]
    row = {"summary": pipeline.relative(summary_path), **ratio_of(residual_path, base_l2)}
    comparison = summary.get("comparison", {})
    if "atomic_heating_volume_l1" in comparison:
        row["atomic_heating_volume_l1"] = comparison["atomic_heating_volume_l1"]
    gates = summary.get("gate_checks", {})
    row["gates"] = {name: bool(value) for name, value in gates.items() if isinstance(value, bool)}
    return row


def collect_run(run_relative: str, base_l2: float) -> dict[str, object]:
    run_dir = pipeline.safe_path(ROOT, run_relative)
    state = pipeline.read(run_dir / "state.json")
    rows = []
    for entry in state.get("diagnostic", {}).get("rounds", []):
        ledger = ROOT / entry["ledger"]
        summary_path = ledger.parent / "feedback_summary.json"
        if not summary_path.is_file():
            raise SystemExit(f"round {entry.get('round')} has no feedback_summary.json yet")
        row = {"round": entry.get("round"), "endpoints": entry.get("endpoints"),
               **collect_round(run_dir, summary_path, base_l2)}
        rows.append(row)
    if not rows:
        root_summary = run_dir / "feedback_summary.json"
        if root_summary.is_file():
            rows.append({"round": None, "endpoints": None,
                         **collect_round(run_dir, root_summary, base_l2)})
    return {"run": pipeline.relative(run_dir), "status": state["status"],
            "maps": len(state.get("history", [])),
            "last_residual": (state["history"][-1]["residual"] if state.get("history") else None),
            "rounds": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True,
                        help="run directory (repeatable)")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    base_path = ROOT / BASE_RESIDUAL
    base = np.asarray(np.load(base_path, allow_pickle=False), dtype=np.float64)
    base_l2 = float(np.linalg.norm(base))
    result = {"criterion": "||r(candidate)||_2 / ||r(base)||_2",
              "base_residual": {"path": BASE_RESIDUAL, "l2": base_l2,
                                "sha256": pipeline.sha256(base_path)},
              "runs": [collect_run(name, base_l2) for name in args.run]}
    text = json.dumps(result, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
