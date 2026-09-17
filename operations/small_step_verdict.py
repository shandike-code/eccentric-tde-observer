"""Assemble the small-step descent verdict from recorded rounds.

Read-only. Joins each recorded feedback round with its endpoints' radiation
residuals and applies the criterion fixed in the handoff:

    ratio(alpha) = ||r(candidate)||_2 / ||r(base)||_2,  base L2 = 15.588864...

A round only counts once **both** endpoints satisfy the authorized stage-B inner
radiation threshold (2.5e-4). Earlier rounds are reported as provisional and are
never used for the decision, because a comparison across differently converged
radiation states is exactly what this project forbids.

Verdict per alpha:
  * `descending`      - a qualifying round has ratio < 1
  * `not_descending`  - a qualifying round has ratio >= 1
  * `pending`         - no qualifying round yet
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
from operations.collect_encoded_ratios import BASE_RESIDUAL, collect_run

QUALIFYING_THRESHOLD = 2.5e-4          # stage-B authorized inner radiation gate


def endpoint_residuals(state: dict) -> dict[int, float]:
    return {int(row["iteration"]): float(row["residual"]) for row in state.get("history", [])}


def qualifying(round_row: dict, residuals: dict[int, float],
               threshold: float = QUALIFYING_THRESHOLD) -> bool:
    """Both endpoints must be recorded and below the authorized threshold."""
    endpoints = round_row.get("endpoints") or []
    if len(endpoints) != 2:
        return False
    values = [residuals.get(int(iteration)) for iteration in endpoints]
    if any(value is None for value in values):
        return False
    return all(value <= threshold for value in values)


def verdict_for(rows: list[dict]) -> dict[str, object]:
    """Last qualifying round decides; provisional rounds are kept for the record."""
    decided = [row for row in rows if row["qualifies"]]
    if not decided:
        return {"verdict": "pending", "reason": "no round has both endpoints at or below 2.5e-4",
                "qualifying_rounds": 0, "rounds_recorded": len(rows)}
    last = decided[-1]
    ratio = float(last["ratio_to_base"])
    return {"verdict": "descending" if ratio < 1.0 else "not_descending",
            "deciding_round": last.get("round"),
            "deciding_endpoints": last.get("endpoints"),
            "deciding_endpoint_residuals": last["endpoint_residuals"],
            "ratio_to_base": ratio,
            "qualifying_rounds": len(decided), "rounds_recorded": len(rows)}


def analyse(name: str, base_l2: float, threshold: float) -> dict[str, object]:
    run = collect_run(name, base_l2)
    state = pipeline.read(pipeline.safe_path(ROOT, name) / "state.json")
    residuals = endpoint_residuals(state)
    rows = []
    for row in run["rounds"]:
        endpoints = row.get("endpoints") or []
        values = [residuals.get(int(iteration)) for iteration in endpoints]
        rows.append({**row, "endpoint_residuals": values,
                     "qualifies": qualifying(row, residuals, threshold)})
    return {"run": run["run"], "status": run["status"], "maps": run["maps"],
            "last_residual": run["last_residual"], "rounds": rows,
            **verdict_for(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True)
    parser.add_argument("--threshold", type=float, default=QUALIFYING_THRESHOLD)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    base_path = ROOT / BASE_RESIDUAL
    base_l2 = float(np.linalg.norm(np.asarray(np.load(base_path, allow_pickle=False), dtype=float)))
    report = {"criterion": "||r(candidate)||_2 / ||r(base)||_2",
              "base_l2": base_l2, "base_sha256": pipeline.sha256(base_path),
              "qualifying_threshold": args.threshold,
              "runs": [analyse(name, base_l2, args.threshold) for name in args.run],
              "note": ("provisional rounds are never used for the decision; the last qualifying "
                       "round decides, and a missing qualifying round reports 'pending'")}
    text = json.dumps(report, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
