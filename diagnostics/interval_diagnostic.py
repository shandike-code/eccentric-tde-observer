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
the atomic block commits -- and changes the control flow around it. Nothing under
src/, scripts/ or hpc/ is modified, and no threshold, timestep, clipping, floor or
energy definition is touched.

Run-control guarantees (each corresponds to a reported defect)
--------------------------------------------------------------
* A round owns its protocol, work directory, outputs and manifests **from
  creation**; nothing is moved afterwards, so the paths recorded inside the
  generated manifests stay valid. A round directory that already exists is
  read-only: identical content returns idempotently, different content raises.
  Nothing is ever rmtree'd.
* Legacy run-root artifacts are never silently treated as "the previous round";
  they are recorded in a migration index with their old path and SHA.
* A ledger subprocess failure leaves the round `diagnosis_incomplete` instead of
  registering a completed round, and the resume path redoes only the missing step.
* Pending feedback is persisted with both endpoint paths and SHAs and is always
  resumed **before** any new map, so a map cannot overtake an owed feedback and
  the three rotating slots cannot clobber the endpoints unnoticed.
* A stop request is propagated to `pipeline.STOP`, the flag `pipeline.batches`
  actually reads, so the current block batch commits and no further worker starts.
* Terminal-state priority is explicit: fault > accepted > pending feedback >
  normal running > budget exhausted. Budget exhaustion never overwrites a fault
  or an acceptance.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "hpc")]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline  # noqa: E402  (reused, never modified)

DIAGNOSTICS_DIR = Path(__file__).resolve().parent
DECLARATION = "diagnostic_declaration.json"
MIGRATION_INDEX = "migration_index.json"
LEDGER = DIAGNOSTICS_DIR / "material_energy_ledger.py"

# Terminal-state priority, most severe first. `stop` means "do not submit more".
FAULT_STATUSES = ("resource_gate_failed", "failed")
ACCEPTED_STATUSES = ("one_material_trial_accepted",)
CONTINUE_STATUSES = ("initializing", "radiation")
# Artifacts a round writes into its own directory.
ROUND_ARTIFACTS = (
    "feedback_summary.json", "feedback.png", "previous_feedback.npz",
    "final_feedback.npz", "target_material.npz", "material_residual.npy",
)

STOP = False


def signal_stop(_number, _frame):
    """Set both our flag and the one `pipeline.batches` actually consults."""
    global STOP
    STOP = True
    pipeline.STOP = True
    print("Stop requested; finish and commit the current block batch.", flush=True)


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def claim(path: Path) -> dict:
    return {"path": relative(path), "size_bytes": path.stat().st_size,
            "sha256": pipeline.sha256(path)}


def diagnostics_sources() -> dict:
    return {
        relative(p): pipeline.sha256(p)
        for p in sorted(DIAGNOSTICS_DIR.glob("*.py")) + sorted(DIAGNOSTICS_DIR.glob("*.sbatch"))
    }


def ensure_declaration(run: Path, config: dict, args) -> dict:
    """Pin the diagnostics actually executing, their SHAs, the git commit and the
    execution parameters. `pipeline.prepare` only ever pinned src/scripts/hpc, so
    without this the files doing the work are unpinned."""
    path = run / DECLARATION
    current = {
        "git_commit": pipeline.environment().get("git_commit"),
        "sources": diagnostics_sources(),
        "parameters": {"maps_per_job": args.maps_per_job,
                       "feedback_every": args.feedback_every,
                       "workers": config["workers"],
                       "maximum_maps": config["maximum_maps"],
                       "radiation_threshold": config["radiation_threshold"]},
    }
    if path.exists():
        recorded = pipeline.read(path)
        problems = sorted(name for name in recorded["sources"].keys() | current["sources"].keys()
                          if recorded["sources"].get(name) != current["sources"].get(name))
        if problems:
            raise RuntimeError(
                f"diagnostic sources changed since the run was declared: {problems}; "
                "create a new named run instead of reusing this one")
        for key, value in recorded["parameters"].items():
            if current["parameters"][key] != value:
                raise RuntimeError(
                    f"diagnostic parameter {key} changed ({value} -> "
                    f"{current['parameters'][key]}); the run's declaration is immutable")
        return recorded
    pipeline.write_json(path, current)
    return current


def record_legacy(run: Path, path: Path, reason: str) -> None:
    """Record a moved/removed legacy artifact with old path and SHA. The index is
    append-only; a later round never rewrites it."""
    if not path.exists():
        return
    index_path = run / MIGRATION_INDEX
    index = pipeline.read(index_path) if index_path.exists() else {"entries": []}
    index["entries"].append({"old_path": relative(path), "sha256": pipeline.sha256(path),
                             "reason": reason})
    pipeline.write_json(index_path, index)


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
        "iteration": active["iteration"], "input_path": relative(first),
        "input_sha256": state["current_sha256"], "output_path": relative(output),
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


def pending_round(state: dict):
    return state.get("pending_feedback")


def start_round(run: Path, config: dict, state: dict, state_path: Path) -> dict:
    """Persist the owed feedback -- including both endpoint paths and SHAs --
    before any work happens, so a crash resumes the feedback instead of mapping on."""
    index = len(state.get("diagnostic", {}).get("rounds", [])) + 1
    previous, final = state["history"][-2:]
    round_dir = run / f"feedback-round{index}"
    if round_dir.exists():
        raise RuntimeError(f"round directory already exists: {round_dir}")
    pending = {
        "round": index,
        "round_dir": relative(round_dir),
        "endpoints": [previous["iteration"], final["iteration"]],
        "previous": {"input_path": previous["input_path"],
                     "input_sha256": previous["input_sha256"],
                     "output_path": previous["output_path"],
                     "output_sha256": previous["output_sha256"]},
        "final": {"input_path": final["input_path"],
                  "input_sha256": final["input_sha256"],
                  "output_path": final["output_path"],
                  "output_sha256": final["output_sha256"]},
        "stage": "protocol",
        "history_rows": [dict(previous), dict(final)],
    }
    state["pending_feedback"] = pending
    pipeline.write_json(state_path, state)
    # Persist ownership before mkdir: interruption here can safely recreate the
    # directory; an unregistered pre-existing directory is still rejected above.
    round_dir.mkdir(parents=True)
    return pending


def build_round_protocol(run: Path, config: dict, state: dict, round_dir: Path) -> Path:
    """Generate the unchanged payload in a round-owned input directory.

    Do not read/remove a cached run-root protocol. It may belong to a different
    pair. Inputs, including the template, are never shared across round outputs.
    """
    inputs = round_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    trial = inputs / "trial_material.npz"
    source_trial = run / "trial_material.npz"
    if trial.exists():
        if pipeline.sha256(trial) != pipeline.sha256(source_trial):
            raise RuntimeError("round-owned trial input changed")
    else:
        temporary = inputs / "trial_material.npz.tmp"
        shutil.copyfile(source_trial, temporary)
        os.replace(temporary, trial)
    staged_config = {**config, "run": relative(inputs)}
    pending = pending_round(state)
    staged_state = {**state, "history": pending["history_rows"]} if pending else state
    base = pipeline.feedback_protocol(staged_config, staged_state)
    payload = json.loads(Path(base).read_text())
    previous, final = staged_state["history"][-2:]
    if previous["output_sha256"] != final["input_sha256"]:
        raise RuntimeError("pending feedback endpoints are not consecutive")
    for label, row in (("previous", previous), ("final", final)):
        declared = payload["sources"][f"{label}_radiation"]
        if declared["path"] != row["input_path"] or declared["sha256"] != row["input_sha256"]:
            raise RuntimeError("cached round protocol belongs to different endpoints")
    cfg = payload["configuration"]
    cfg["feedback_work_directory"] = relative(round_dir / "feedback")
    cfg["summary_path"] = relative(round_dir / "feedback_summary.json")
    cfg["figure_path"] = relative(round_dir / "feedback.png")
    cfg["target_material_output"] = relative(round_dir / "target_material.npz")
    cfg["encoded_residual_output"] = relative(round_dir / "material_residual.npy")
    for label in ("previous", "final"):
        cfg[f"{label}_feedback_output"] = relative(round_dir / f"{label}_feedback.npz")
    target = round_dir / "feedback_protocol.json"
    if target.exists():
        if pipeline.read(target) != payload:
            raise RuntimeError("round protocol already exists with different content")
    else:
        pipeline.write_json(target, payload)
    return target


def run_ledger(run: Path, round_dir: Path, feedback_claims: dict) -> dict:
    """Run the ledger with an argument list and a checked exit; verify it exists,
    parses, and describes exactly this round's inputs."""
    output = round_dir / "material_energy_ledger.json"
    log = round_dir / "ledger.log"
    with log.open("w") as stream:
        subprocess.run(
            [sys.executable, str(LEDGER), "--run", relative(run),
             "--feedback-source", relative(round_dir), "--json", str(output)],
            cwd=ROOT, check=True, stdout=stream, stderr=subprocess.STDOUT,
        )
    if not output.is_file():
        raise RuntimeError("ledger reported success but wrote no JSON")
    report = json.loads(output.read_text())
    json.dumps(report, allow_nan=False)
    for label in ("previous", "final"):
        recorded = report["inputs"][f"{label}_feedback"]["sha256"]
        expected = feedback_claims[label]["sha256"]
        if recorded != expected:
            raise RuntimeError(
                f"ledger input hash mismatch for {label}: {recorded} != {expected}")
    return report


def validate_completed_feedback(round_dir: Path, pending: dict, report: dict) -> dict:
    """Check small feedback files against the protocol, manifests and summary.

    Radiation input hashes and feedback-NPZ hashes are distinct identities.
    This check also runs when recovering a ledger, without recomputing physics.
    """
    protocol = ROOT / pending["protocol_path"]
    if pipeline.sha256(protocol) != pending["protocol_sha256"]:
        raise RuntimeError("committed round protocol changed")
    payload = pipeline.read(protocol)
    small_sources = [source for name, source in payload["sources"].items()
                     if name not in {"previous_radiation", "final_radiation"}
                     and not source["path"].endswith(".dat")]
    failures = pipeline.verify_claims(ROOT, small_sources, hash_files=True)
    if failures:
        raise RuntimeError(f"completed feedback small inputs changed: {failures}")
    if report.get("protocol_sha256") != pending["protocol_sha256"]:
        raise RuntimeError("feedback summary belongs to another protocol")
    claims = {}
    for label in ("previous", "final"):
        source = payload["sources"][f"{label}_radiation"]
        endpoint = pending[label]
        if (source["path"] != endpoint["input_path"]
                or source["sha256"] != endpoint["input_sha256"]):
            raise RuntimeError("protocol radiation inputs differ from pending endpoints")
        artifact = round_dir / f"{label}_feedback.npz"
        info = report[f"{label}_feedback"]
        manifest = pipeline.read(round_dir / "feedback" / f"{label}_manifest.json")
        checks = (
            info["feedback_artifact_path"] == relative(artifact),
            manifest["protocol_sha256"] == pending["protocol_sha256"],
            manifest["status"] == "complete",
            manifest["state_path"] == endpoint["input_path"],
            manifest["state_sha256"] == endpoint["input_sha256"],
            manifest["feedback_artifact_path"] == relative(artifact),
            manifest["feedback_artifact_sha256"] == info["feedback_artifact_sha256"],
            pipeline.sha256(artifact) == info["feedback_artifact_sha256"],
        )
        if not all(checks):
            raise RuntimeError(f"completed {label} feedback lineage/hash mismatch")
        claims[label] = {"path": relative(artifact), "size_bytes": artifact.stat().st_size,
                         "sha256": info["feedback_artifact_sha256"]}
    return claims


def complete_round(run: Path, config: dict, state: dict, state_path: Path) -> dict:
    """Finish the persisted pending round, resuming from its recorded stage."""
    pending = pending_round(state)
    round_dir = ROOT / pending["round_dir"]
    endpoints = {"previous": pending["previous"], "final": pending["final"]}
    if pending["stage"] not in {"protocol", "feedback", "ledger"}:
        raise RuntimeError("unknown pending feedback stage")
    if not round_dir.exists():
        if pending["stage"] != "protocol":
            raise RuntimeError("registered feedback artifacts are missing")
        round_dir.mkdir(parents=True)

    if pending["stage"] == "protocol":
        protocol = build_round_protocol(run, config, state, round_dir)
        pending["protocol_path"] = relative(protocol)
        pending["protocol_sha256"] = pipeline.sha256(protocol)
        pending["stage"] = "feedback"
        pending["endpoints_claim"] = {
            label: {"path": endpoints[label]["input_path"],
                    "sha256": endpoints[label]["input_sha256"],
                    "size_bytes": pipeline.STATE_BYTES}
            for label in ("previous", "final")
        }
        pending["slot_reuse_note"] = (
            "radiation state slots rotate across three files; the retained small "
            "artifacts stay verifiable, but these large states may later be "
            "overwritten and the round may then not be re-runnable at these paths")
        pipeline.write_json(state_path, state)

    if pending["stage"] == "feedback":
        protocol = ROOT / pending["protocol_path"]
        if pipeline.sha256(protocol) != pending["protocol_sha256"]:
            raise RuntimeError("committed round protocol changed")
        from scripts import phase7b9_formal_feedback_pair_adapter as pair
        started = time.monotonic()
        report = pair.run_pair(protocol, pending["protocol_sha256"])
        pending["feedback_wall_s"] = time.monotonic() - started
        pending["feedback_claims"] = validate_completed_feedback(round_dir, pending, report)
        summary_path = round_dir / "feedback_summary.json"
        if pipeline.read(summary_path) != report:
            raise RuntimeError("returned feedback differs from persisted summary")
        pending["feedback_summary_sha256"] = pipeline.sha256(summary_path)
        pending["stage"] = "ledger"
        pipeline.write_json(state_path, state)
    else:
        # Resuming after a ledger failure: the physics is already done and must not
        # be recomputed. The adapter returns the existing summary when the protocol
        # hash matches, so this reads the same object it wrote.
        summary_path = round_dir / "feedback_summary.json"
        if not summary_path.is_file():
            raise RuntimeError("round is at the ledger stage but has no feedback summary")
        if pipeline.sha256(summary_path) != pending["feedback_summary_sha256"]:
            raise RuntimeError("completed feedback summary changed before ledger recovery")
        report = json.loads(summary_path.read_text())
        claims = validate_completed_feedback(round_dir, pending, report)
        if claims != pending["feedback_claims"]:
            raise RuntimeError("committed feedback claims changed before ledger recovery")

    # Ledger: a failure here must leave the round incomplete, not completed. The
    # pending record stays at stage "ledger", so a rerun redoes only this step.
    try:
        ledger = run_ledger(run, round_dir, pending["feedback_claims"])
        sources = pipeline.read(ROOT / pending["protocol_path"])["sources"]
        for field, source in (("trial_material", "trial_material"),
                              ("old_time_level", "physical_old_time_level")):
            if source in sources and ledger["inputs"][field]["sha256"] != sources[source]["sha256"]:
                raise RuntimeError(f"ledger {field} does not match the frozen feedback input")
    except Exception:
        state["status"] = "diagnosis_incomplete"
        pipeline.write_json(state_path, state)
        raise
    checks = report["gate_checks"]
    accepted = bool(all(checks.values())
                    and report["decision"].get("finite_trial_accepted_as_one_nonlinear_step", False))
    summary = {
        "round": pending["round"],
        "endpoints": pending["endpoints"],
        "protocol_sha256": pending["protocol_sha256"],
        "endpoints_claim": pending.get("endpoints_claim"),
        "slot_reuse_note": pending.get("slot_reuse_note"),
        "feedback_wall_s": pending.get("feedback_wall_s"),
        "accepted": accepted,
        "failed_gates": sorted(k for k, v in checks.items() if not v),
        "decision": report["decision"],
        "ledger": relative(round_dir / "material_energy_ledger.json"),
        "ledger_heating_ratio": ledger["heating_stability"]["metrics"][
            "atomic_rate_heating_erg_s_cm3"]["ratio"],
    }
    completed_path = round_dir / "round_summary.json"
    if completed_path.exists():
        if pipeline.read(completed_path) != summary:
            raise RuntimeError("completed round summary already exists with different content")
    else:
        pipeline.write_json(completed_path, summary)
    state.setdefault("diagnostic", {}).setdefault("rounds", []).append(summary)
    state.pop("pending_feedback", None)
    if accepted:
        state["status"] = "one_material_trial_accepted"
    elif state["status"] == "diagnosis_incomplete":
        state["status"] = "radiation"
    pipeline.write_json(state_path, state)
    print(json.dumps({"feedback_round": summary}, ensure_ascii=False), flush=True)
    return summary


def should_run_feedback(completed: int, feedback_every: int, rounds_done: int, stop: bool) -> bool:
    """Fire the formal feedback exactly once per `feedback_every` completed maps."""
    if stop or completed <= 0 or feedback_every < 1:
        return False
    if completed % feedback_every != 0:
        return False
    return completed // feedback_every > rounds_done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--maps-per-job", type=int, default=1)
    parser.add_argument("--feedback-every", type=int, default=4)
    args = parser.parse_args()
    if args.maps_per_job < 0 or args.feedback_every < 2:
        parser.error("maps-per-job must be nonnegative and feedback-every must be >= 2")

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
        ensure_declaration(run, config, args)
        pipeline.write_json(run / f"environment-{os.environ['SLURM_JOB_ID']}.json",
                            pipeline.environment())

        # Priority 1: fault. Nothing further runs and nothing overwrites it.
        if state["status"] in FAULT_STATUSES:
            print(json.dumps({"status": state["status"], "action": "stopped on fault"}))
            return
        if state["status"] in ACCEPTED_STATUSES:
            return
        # A map commit and pending-record creation are separate atomic writes.
        # Reconstruct a due boundary before any new map, including at the budget.
        if (state["status"] == "radiation" and not pending_round(state) and not STOP):
            done = len(state["history"])
            rounds_done = len(state.get("diagnostic", {}).get("rounds", []))
            if done // args.feedback_every > rounds_done:
                if done % args.feedback_every:
                    raise RuntimeError("a past feedback boundary was skipped; inspect retained endpoints")
                start_round(run, config, state, state_path)
        # An owed feedback is settled before any new map can rotate a slot.
        if pending_round(state) and not STOP:
            complete_round(run, config, state, state_path)
        if state["status"] in ACCEPTED_STATUSES:
            print(json.dumps({"status": state["status"], "action": "accepted; terminal"}))
            pipeline.write_json(state_path, state)
            return

        rounds_done = len(state.get("diagnostic", {}).get("rounds", []))
        for _ in range(args.maps_per_job):
            if STOP or state["status"] != "radiation":
                break
            if len(state["history"]) >= config["maximum_maps"]:
                break
            if not run_one_map(run, config, state, state_path):
                return
            done = len(state["history"])
            if (state["status"] == "radiation" and not STOP
                    and should_run_feedback(done, args.feedback_every, rounds_done, STOP)
                    and not pending_round(state)):
                start_round(run, config, state, state_path)
                complete_round(run, config, state, state_path)
                rounds_done = len(state["diagnostic"]["rounds"])

        if state["status"] in FAULT_STATUSES:
            print(json.dumps({"status": state["status"], "action": "stopped on fault"}))
            pipeline.write_json(state_path, state)
            return
        # Priority 5: budget only bounds new maps. A last owed feedback still runs.
        if (not STOP and len(state["history"]) >= config["maximum_maps"]
                and state["status"] == "radiation" and not pending_round(state)):
            state["status"] = "diagnostic_round_complete"
        pipeline.write_json(state_path, state)
        print(json.dumps({"status": state["status"], "maps": len(state["history"]),
                          "rounds": len(state.get("diagnostic", {}).get("rounds", [])),
                          "pending_feedback": bool(pending_round(state))}), flush=True)


if __name__ == "__main__":
    main()
