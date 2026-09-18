"""Prepare a new run that continues an existing stopped chain from its own state.

`hpc/pipeline.py prepare --seed warm` is hard-wired to the Mac handoff checkpoint
in `handoff/restart_manifest.json`, so it cannot seed from a school-side state.
This entry point inherits the source run's configuration (same frozen material
candidate, direction, sources and physical time level) and overrides only the
run identity, worker count, map budget, feedback cadence, radiation threshold and
the warm seed. It never edits the source run or any frozen dependency.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "hpc")]
import pipeline

STATE_BYTES = 10_099_884_032
STOPPED = ("diagnostic_round_complete", "budget_exhausted")


def recorded_hashes(state: dict) -> dict[str, str]:
    """Every sha256 the source run itself recorded, keyed by state path.

    A slot rotates, so the same path legitimately holds different bytes over the
    life of a run. Only the *last* write to a path can be compared with the file
    on disk now; using an earlier record would reject healthy runs (observed on
    hhe-r025-cont64, whose slots are intact).
    """
    recorded: dict[str, str] = {}
    for row in state.get("history", []):
        if row.get("output_path") and row.get("output_sha256"):
            recorded[row["output_path"]] = row["output_sha256"]
    for row in state.get("diagnostic", {}).get("rounds", []):
        for label in ("previous", "final"):
            claim = row.get("endpoints_claim", {}).get(label)
            if claim:
                recorded.setdefault(claim["path"], claim["sha256"])
    return recorded


def carry_trial(source_run: Path, run: Path) -> dict[str, object]:
    """Copy the source run's material trial into the new run and assert identity.

    Why this exists: `hpc/pipeline.py::run_pipeline` calls `migrate_trial()` when the
    new run has no `trial_material.npz`, and that silently substitutes the fixed
    `MATERIAL` (the alpha=0.0625 candidate). On 2026-09-18 this replaced two
    small-step candidates and invalidated a verdict (see
    `handoff/linux-runs/2026-09-18-RETRACTION-trial-identity-error.md`). The encoded
    vector *is* the experiment, so it is copied explicitly and compared bitwise.
    """
    source_trial = source_run / "trial_material.npz"
    if not source_trial.is_file():
        raise SystemExit(f"source run has no trial_material.npz: {source_trial}")
    destination = run / "trial_material.npz"
    shutil.copyfile(source_trial, destination)
    with np.load(source_trial, allow_pickle=False) as before, \
            np.load(destination, allow_pickle=False) as after:
        for field in ("encoded_state", "base_encoded_state", "finite_direction",
                      "base_residual"):
            if not np.array_equal(before[field], after[field]):
                raise SystemExit(f"copied trial changed {field}; refusing to continue")
        if float(before["relaxation"]) != float(after["relaxation"]):
            raise SystemExit("copied trial changed relaxation; refusing to continue")
        relaxation = float(after["relaxation"])
        size = int(np.asarray(after["encoded_state"]).size)
    return {"source": pipeline.claim(source_trial), "destination": pipeline.claim(destination),
            "relaxation": relaxation, "encoded_vector_size": size,
            "note": "carried explicitly so pipeline.migrate_trial cannot substitute MATERIAL"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True, help="stopped run to continue")
    parser.add_argument("--source-state", required=True, help="state_N.dat inside that run")
    parser.add_argument("--run", required=True, help="new run directory")
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--maximum-maps", type=int, required=True)
    parser.add_argument("--feedback-every", type=int, default=4)
    parser.add_argument("--radiation-threshold", type=float, default=1.0e-4)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="run every check and print the planned config without writing")
    args = parser.parse_args()

    source = pipeline.safe_path(ROOT, args.source_run)
    run = pipeline.safe_path(ROOT, args.run)
    seed = pipeline.safe_path(ROOT, args.source_state)
    if not run.is_relative_to(ROOT / "outputs/hpc"):
        raise SystemExit("run must live under outputs/hpc/")
    if run.exists():
        raise SystemExit(f"run directory exists: {run}")
    if not seed.is_relative_to(source):
        raise SystemExit("seed state must belong to the source run")
    if not 1 <= args.workers <= 16 or args.maximum_maps < 2 or args.feedback_every < 2:
        raise SystemExit("invalid workers/budget/cadence")
    if args.radiation_threshold not in pipeline.THRESHOLDS:
        raise SystemExit(f"threshold must be one of {sorted(pipeline.THRESHOLDS)}")

    state = pipeline.read(source / "state.json")
    if state["status"] not in STOPPED or state.get("active_map") or state.get("pending_feedback"):
        raise SystemExit(f"source run is not stopped and settled: {state['status']}")
    if pipeline.sha256(source / "config.json") != state["config_sha256"]:
        raise SystemExit("source config changed since the run was written")
    config = pipeline.read(source / "config.json")
    if seed.stat().st_size != STATE_BYTES:
        raise SystemExit("seed state has the wrong size")
    claim = pipeline.claim(seed)
    # 记录来源端点身份：seed 必须出现在该 run 的历史或回合端点声明中。
    recorded = recorded_hashes(state)
    if claim["path"] not in recorded:
        raise SystemExit("seed state is not a recorded endpoint of the source run")
    if recorded[claim["path"]] != claim["sha256"]:
        raise SystemExit(
            f"seed state bytes no longer match the run's own record for {claim['path']}; "
            "the slot was overwritten, so this chain can no longer be continued from it")
    # 续跑点必须是这条链的最新态：当前槽位就是最后一次 map 的输出。
    history = state.get("history", [])
    latest = history[-1] if history else None
    if not latest or latest.get("output_path") != claim["path"] \
            or latest.get("output_sha256") != claim["sha256"]:
        raise SystemExit("seed must be the output of the run's most recent map")
    if state["slots"][state["current_slot"]] != claim["path"]:
        raise SystemExit("seed is not the run's current slot")

    config.update({
        "run": run.relative_to(ROOT).as_posix(),
        "workers": args.workers,
        "maximum_maps": args.maximum_maps,
        "feedback_every": args.feedback_every,
        "radiation_threshold": args.radiation_threshold,
        "seed": "warm",
        "warm_seed": claim,
        "seed_provenance": ("school-side state of the same chain; prepared by "
                            "operations/prepare_extension_run.py because "
                            "pipeline.prepare --seed warm is hard-wired to the Mac handoff"),
        "extension_of": source.relative_to(ROOT).as_posix(),
        "extension_purpose": args.purpose,
        "authorized_stage_b_threshold": 2.5e-4,
        "threshold_note": ("stage-B authorized threshold is unchanged at 2.5e-4; this run "
                           "deliberately continues below it to test the measured R-scaling"),
    })
    if args.dry_run:
        trial_source = pipeline.claim(source / "trial_material.npz") \
            if (source / "trial_material.npz").is_file() else None
        print(json.dumps({"dry_run": True, "run": config["run"], "seed": claim,
                          "source_trial": trial_source,
                          "source_trial_relaxation": (
                              float(np.load(source / "trial_material.npz", allow_pickle=False)["relaxation"])
                              if trial_source else None),
                          "workers": args.workers, "maximum_maps": args.maximum_maps,
                          "feedback_every": args.feedback_every,
                          "radiation_threshold": args.radiation_threshold,
                          "config_keys": sorted(config),
                          "sources_count": len(config.get("sources", []))}))
        return
    run.mkdir(parents=True)
    # 先落 trial：pipeline 初始化在 trial 缺失时会复制 MATERIAL（0.0625 候选），
    # 那会静默换掉实验对象（2026-09-18 撤回事件的根因）。
    trial = carry_trial(source, run)
    config_path = run / "config.json"
    config["sources"] = list(config.get("sources", [])) + [trial["source"], trial["destination"]]
    config_path.write_text(json.dumps(config, indent=2, allow_nan=False) + "\n")
    pipeline.write_json(run / "state.json", {
        "config_sha256": pipeline.sha256(config_path),
        "status": "initializing",
        "initialization_blocks": [],
        "history": [],
        "slots": [f"{config['run']}/state_{i}.dat" for i in range(3)],
        "current_slot": 0,
        "active_map": None,
    })
    pipeline.write_json(run / "extension_declaration.json", {
        "source_run": source.relative_to(ROOT).as_posix(),
        "source_state": claim,
        "carried_trial": trial,
        "purpose": args.purpose,
        "workers": args.workers,
        "maximum_maps": args.maximum_maps,
        "feedback_every": args.feedback_every,
        "radiation_threshold": args.radiation_threshold,
        "science_gates_changed": False,
        "accepted_material_step": False,
        "note": ("new named run; the source run, its budget and its outputs are untouched "
                 "and remain the reference for the same-scale comparison"),
    })
    print(json.dumps({"prepared": config["run"], "seed": claim["path"],
                      "workers": args.workers, "maximum_maps": args.maximum_maps,
                      "config_sha256": pipeline.sha256(config_path)}))


if __name__ == "__main__":
    main()
