"""Compare 2/4/8 workers on one frozen full map inside one Slurm allocation.

These are independent copies of one seed, never scientific continuation maps.
No numerical source or running diagnostic declaration is modified.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "hpc"), str(ROOT / "src"), str(ROOT)]
import pipeline


def prepare_case(template, seed, run, workers):
    config = {**template, "run": pipeline.relative(run), "seed": "warm",
              "warm_seed": seed, "workers": workers, "maximum_maps": 1,
              "seed_provenance": "fixed Linux seed; CPU scaling benchmark only"}
    run.mkdir(parents=True, exist_ok=False)
    pipeline.write_json(run / "config.json", config)
    pipeline.write_json(run / "state.json", {
        "config_sha256": pipeline.sha256(run / "config.json"),
        "status": "initializing", "initialization_blocks": [], "history": [],
        "slots": [f"{config['run']}/state_{i}.dat" for i in range(3)],
        "current_slot": 0, "active_map": None})


def compare_cases(cases):
    baseline = cases[0]
    for case in cases:
        case["bitwise_equal_to_workers2"] = (
            case["output_sha256"] == baseline["output_sha256"])
        case["map_speedup_vs_workers2"] = baseline["wall_s"] / case["wall_s"]
        case["total_speedup_vs_workers2"] = baseline["total_wall_s"] / case["total_wall_s"]
    # A differing hash is an investigation trigger, not a cross-CPU physics claim.
    if not all(c["bitwise_equal_to_workers2"] for c in cases):
        raise RuntimeError("Worker-count output differs; investigate before changing science resources")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--seed-run", required=True)
    args = p.parse_args()
    pipeline.require_allocation(8)
    run = pipeline.safe_path(ROOT, args.run)
    if not run.is_relative_to(ROOT / "outputs/hpc"):
        p.error("benchmark must be under outputs/hpc")
    run.mkdir(parents=True, exist_ok=False)
    template = pipeline.read(pipeline.safe_path(ROOT, args.template) / "config.json")
    source_run = pipeline.safe_path(ROOT, args.seed_run)
    source_state = pipeline.read(source_run / "state.json")
    if source_state.get("active_map") or source_state.get("pending_feedback"):
        raise RuntimeError("seed run has unfinished work")
    if source_state["status"] not in {"diagnostic_round_complete", "one_material_trial_accepted",
                                       "material_trial_not_accepted", "budget_exhausted"}:
        raise RuntimeError("seed run is not stopped at a terminal boundary")
    source = ROOT / source_state["slots"][source_state["current_slot"]]
    seed = {"path": pipeline.relative(source), "size_bytes": source.stat().st_size,
            "sha256": source_state["current_sha256"]}
    report = {"status": "running", "science_run": False, "seed": seed, "cases": [],
              "environment": pipeline.environment(), "script_sha256": pipeline.sha256(Path(__file__)),
              "note": "one map per count; cache/order effects are not controlled repetitions"}
    result_path = run / "benchmark.json"
    pipeline.write_json(result_path, report)
    child = None
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGUSR1)

    signal.signal(signal.SIGUSR1, stop)
    try:
        if pipeline.verify_claims(ROOT, [seed], hash_files=True):
            raise RuntimeError("frozen Linux seed differs from its committed hash")
        for workers in (2, 4, 8):
            if stopping:
                raise RuntimeError("stopped at benchmark boundary; no automatic restart")
            case = run / f"workers{workers}"
            prepare_case(template, seed, case, workers)
            started = time.monotonic()
            with (case / "pipeline.log").open("x") as log:
                child = subprocess.Popen([sys.executable, str(ROOT / "hpc/pipeline.py"), "run",
                    "--run", pipeline.relative(case), "--maps-per-job", "1", "--no-feedback"],
                    cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                code = child.wait()
            state = pipeline.read(case / "state.json")
            if code or len(state["history"]) != 1 or state.get("active_map") or state["status"] == "resource_gate_failed":
                raise RuntimeError(f"workers={workers}: exit={code}, incomplete map or resource failure")
            report["cases"].append({"workers": workers, "run": pipeline.relative(case),
                                   "total_wall_s": time.monotonic() - started, **state["history"][0]})
            pipeline.write_json(result_path, report)
        compare_cases(report["cases"])
        report["status"] = "complete"
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        pipeline.write_json(result_path, report)


if __name__ == "__main__":
    main()
