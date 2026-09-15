"""Inner-precision diagnostic driver: keep mapping past `pair_ready`, re-check the
formal H/He feedback plus the per-cell energy ledger every N completed maps.

Why this exists
---------------
`hpc/pipeline.py` treats `pair_ready` as the end of the radiation phase: the map
loop breaks on the next iteration, the formal feedback runs once, and the run
lands in a terminal status. With a seed that already satisfies the relaxed
2.5e-4 gate that means one feedback round after two maps and no further
inner-precision push.

This driver reuses that module's own machinery unchanged -- `worker`, `batches`,
`aggregate`, `feedback_protocol`, `verify_claims`, `block_hash`, the run lock and
the atomic block commits -- and changes exactly one thing: the map loop keys on
the run's own map budget instead of on `pair_ready`. The formal feedback is then
invoked deliberately every `--feedback-every` maps, and each round is archived so
a later round cannot overwrite it.

Nothing under src/, scripts/ or hpc/ is modified. No threshold, timestep,
clipping, floor or energy definition is touched.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "hpc")]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline  # noqa: E402  (reused, never modified)

STOP = False
ARCHIVE = (
    "feedback_summary.json", "feedback.png", "feedback_protocol.json",
    "feedback_template.json", "previous_feedback.npz", "final_feedback.npz",
    "target_material.npz", "material_residual.npy",
)


def signal_stop(_number, _frame):
    global STOP
    STOP = True
    print("Stop requested; finish and commit the current block batch.", flush=True)


def should_run_feedback(completed: int, feedback_every: int, rounds_done: int, stop: bool) -> bool:
    """Fire the formal feedback exactly once per `feedback_every` completed maps."""
    if stop or completed <= 0 or feedback_every < 1:
        return False
    if completed % feedback_every != 0:
        return False
    return completed // feedback_every > rounds_done


def run_one_map(run: Path, config: dict, state: dict, state_path: Path) -> bool:
    """One complete frequency map, using pipeline.batches/aggregate unchanged."""
    first = ROOT / state["slots"][state["current_slot"]]
    if pipeline.sha256(first) != state["current_sha256"]:
        raise RuntimeError("Committed input state changed")
    next_slot = (state["current_slot"] + 1) % 3
    output = ROOT / state["slots"][next_slot]
    if state["active_map"] is None:
        state["active_map"] = {
            "iteration": len(state["history"]) + 1, "records": [],
            "input_sha256": state["current_sha256"], "wall_s": 0.0,
        }
        pipeline.write_json(state_path, state)
    active = state["active_map"]
    if active["input_sha256"] != state["current_sha256"]:
        raise RuntimeError("Partial map belongs to another input")
    started = time.monotonic()
    complete = pipeline.batches(
        config, state, "map", first, output, active["records"],
        run / f"map{active['iteration']:04d}", state_path,
    )
    active["wall_s"] += time.monotonic() - started
    if not complete:
        pipeline.write_json(state_path, state)
        return False
    metrics = pipeline.aggregate(active["records"])
    row = {
        "iteration": active["iteration"], "input_path": pipeline.relative(first),
        "input_sha256": state["current_sha256"], "output_path": pipeline.relative(output),
        "output_sha256": pipeline.sha256(output), "wall_s": active["wall_s"], **metrics,
    }
    state["history"].append(row)
    state.update(current_slot=next_slot, current_sha256=row["output_sha256"], active_map=None)
    if metrics["maximum_worker_rss_mib"] >= 6144:
        state["status"] = "resource_gate_failed"
    pipeline.write_json(state_path, state)
    print(json.dumps({"map": row["iteration"], "residual": row["residual"],
                      "boundary_l1": row["boundary_l1"],
                      "boundary_bolometric": row["boundary_bolometric"],
                      "wall_s": row["wall_s"]}), flush=True)
    return True


def archive_round(run: Path, round_dir: Path):
    """Move a round's artifacts out of the run root into the round directory.

    It moves rather than copies on purpose. `run_pair` refuses to run when
    `feedback_summary.json` is present with a different `protocol_sha256`
    ("formal feedback-pair summary lineage changed"); leaving an earlier round's
    summary in the run root makes the next round unresumable. Clearing the root
    also keeps "the run root holds the current round" true.
    """
    for name in ARCHIVE:
        source = run / name
        if source.is_file():
            os.replace(source, round_dir / name)
    work = run / "feedback"
    if work.is_dir():
        target = round_dir / "feedback"
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(work), str(target))


def feedback_round(run: Path, config: dict, state: dict, index: int) -> dict:
    """Formal feedback pair on the last two adjacent states, plus the energy ledger."""
    round_dir = run / f"feedback-round{index}"
    round_dir.mkdir(parents=True, exist_ok=True)
    # Anything still in the run root predates this round. Move it aside first:
    # pipeline.feedback_protocol would otherwise reuse an earlier round's cached
    # protocol, and run_pair would refuse on the earlier round's summary.
    archive_round(run, round_dir)

    path = pipeline.feedback_protocol(config, state)
    protocol_hash = pipeline.sha256(path)
    from scripts import phase7b9_formal_feedback_pair_adapter as pair

    started = time.monotonic()
    report = pair.run_pair(path, protocol_hash)
    elapsed = time.monotonic() - started
    checks = report["gate_checks"]
    accepted = bool(
        all(checks.values())
        and report["decision"].get("finite_trial_accepted_as_one_nonlinear_step", False)
    )

    ledger_json = round_dir / "material_energy_ledger.json"
    os.system(
        f"{sys.executable} {Path(__file__).with_name('material_energy_ledger.py')} "
        f"--run {pipeline.relative(run)} --json {ledger_json} > {round_dir}/ledger.log 2>&1"
    )
    archive_round(run, round_dir)

    result = {
        "round": index,
        "maps_completed": len(state["history"]),
        "endpoints": [row["iteration"] for row in state["history"][-2:]],
        "protocol_sha256": protocol_hash,
        "wall_s": elapsed,
        "accepted": accepted,
        "failed_gates": sorted(k for k, v in checks.items() if not v),
        "decision": report["decision"],
        "ledger": str(ledger_json.relative_to(ROOT)),
    }
    pipeline.write_json(round_dir / "round_summary.json", result)
    state.setdefault("diagnostic", {})["rounds"] = (
        state.get("diagnostic", {}).get("rounds", []) + [result]
    )
    print(json.dumps({"feedback_round": result}, ensure_ascii=False), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--maps-per-job", type=int, default=1)
    parser.add_argument("--feedback-every", type=int, default=4)
    args = parser.parse_args()

    run = pipeline.safe_path(ROOT, args.run)
    config = pipeline.read(run / "config.json")
    pipeline.require_allocation(config["workers"])
    failures = pipeline.verify_claims(ROOT, config["sources"], hash_files=True)
    if failures:
        raise RuntimeError(f"Frozen sources changed: {failures[:5]}")
    config_hash = pipeline.sha256(run / "config.json")
    state_path = run / "state.json"
    signal.signal(signal.SIGUSR1, signal_stop)

    with (run / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another job is writing this run")
        state = pipeline.read(state_path)
        if state["config_sha256"] != config_hash:
            raise RuntimeError("Configuration changed after preparation")
        pipeline.write_json(run / f"environment-{os.environ['SLURM_JOB_ID']}.json",
                            pipeline.environment())

        completed = len(state["history"])
        for _ in range(args.maps_per_job):
            if STOP or state["status"] != "radiation":
                break
            if completed >= config["maximum_maps"]:
                break
            if not run_one_map(run, config, state, state_path):
                return
            completed = len(state["history"])

        done = len(state["history"])
        already = len(state.get("diagnostic", {}).get("rounds", []))
        if should_run_feedback(done, args.feedback_every, already, STOP):
            feedback_round(run, config, state, done // args.feedback_every)

        if len(state["history"]) >= config["maximum_maps"]:
            state["status"] = "diagnostic_round_complete"
        pipeline.write_json(state_path, state)
        print(json.dumps({"status": state["status"],
                          "maps": len(state["history"]),
                          "rounds": len(state.get("diagnostic", {}).get("rounds", []))}), flush=True)


if __name__ == "__main__":
    main()
