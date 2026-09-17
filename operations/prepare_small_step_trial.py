"""Declare a smaller-α trial along an existing frozen encoded direction.

Motivation (see handoff/linux-runs/2026-09-17-extension-run-verdict.md): the
measured candidate-to-base encoded residual ratio is 1.0 at α→0 by construction
and 1.126 at α=0.0625, with no sign of a descent region. Before rebuilding the
direction, measure whether very small steps descend at all.

This never edits `operations/prepare_encoded_backtrack.py` (its hash is pinned by
existing runs) and never touches the source run: it imports that module's pure
`candidate_arrays` checks and the same trust-region guard.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "hpc"), str(ROOT / "src"), str(ROOT / "scripts")]
import pipeline
from operations.prepare_encoded_backtrack import (
    audit_native_trial, candidate_arrays, load_arrays)

STATE_BYTES = 10_099_884_032
STOPPED = ("diagnostic_round_complete", "budget_exhausted")
BASE_RESIDUAL = "outputs/phase7b9f_base_material_residual.npy"
OLD_TIME_LEVEL = "outputs/phase7b4r_depth128_phase2048.npz"


def build_trial(source_trial: dict, old: dict, baseline_residual: np.ndarray,
                relaxation: float) -> tuple[dict, dict]:
    """Smaller-α trial with every provenance and trust-region check in place."""
    previous = float(source_trial["relaxation"])
    if not np.isfinite(relaxation) or not 0.0 < relaxation < previous:
        raise SystemExit(
            f"relaxation must satisfy 0 < alpha < source alpha ({previous}); got {relaxation}")
    trial, gates = candidate_arrays(source_trial, old, baseline_residual, relaxation)
    return trial, {"trust_region_and_provenance": gates, "source_alpha": previous,
                   "declared_alpha": relaxation, "ratio_to_source": relaxation / previous}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", required=True,
                        help="stopped run whose trial carries the frozen direction")
    parser.add_argument("--warm-seed", required=True,
                        help="existing radiation state used as the numerical initial guess")
    parser.add_argument("--run", required=True, help="new run directory")
    parser.add_argument("--relaxation", type=float, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--maximum-maps", type=int, default=4)
    parser.add_argument("--radiation-threshold", type=float, default=2.5e-4)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-native-audit", action="store_true",
                        help="local self-test only; never use for a platform run")
    args = parser.parse_args()

    source = pipeline.safe_path(ROOT, args.source_run)
    run = pipeline.safe_path(ROOT, args.run)
    seed_path = pipeline.safe_path(ROOT, args.warm_seed)
    if not run.is_relative_to(ROOT / "outputs/hpc"):
        raise SystemExit("run must live under outputs/hpc/")
    if run.exists():
        raise SystemExit(f"run directory exists: {run}")
    if not 1 <= args.workers <= 16 or args.maximum_maps < 2:
        raise SystemExit("invalid workers/map budget")
    if args.radiation_threshold not in pipeline.THRESHOLDS:
        raise SystemExit(f"threshold must be one of {sorted(pipeline.THRESHOLDS)}")

    state = pipeline.read(source / "state.json")
    if state["status"] not in STOPPED or state.get("active_map") or state.get("pending_feedback"):
        raise SystemExit(f"source run is not stopped and settled: {state['status']}")
    if pipeline.sha256(source / "config.json") != state["config_sha256"]:
        raise SystemExit("source config changed since the run was written")
    config = pipeline.read(source / "config.json")
    trial_path = source / "trial_material.npz"
    source_trial = load_arrays(trial_path)
    old = load_arrays(ROOT / OLD_TIME_LEVEL)
    baseline = np.load(ROOT / BASE_RESIDUAL, allow_pickle=False)
    trial, trial_gates = build_trial(source_trial, old, baseline, args.relaxation)

    if seed_path.stat().st_size != STATE_BYTES:
        raise SystemExit("warm seed has the wrong size")
    seed = pipeline.claim(seed_path)

    claim(trial)  # 形状与有限性检查在 savez 之前完成
    config = deepcopy(config)
    config.update({
        "run": run.relative_to(ROOT).as_posix(),
        "workers": args.workers,
        "maximum_maps": args.maximum_maps,
        "radiation_threshold": args.radiation_threshold,
        "seed": "warm",
        "warm_seed": seed,
        "candidate_relaxation": args.relaxation,
        "small_step_source_run": source.relative_to(ROOT).as_posix(),
        "seed_provenance": ("nearby radiation field as numerical initial guess only; "
                            "not a Jacobian and not a frozen response"),
        "physics_scope": (f"one fixed alpha={args.relaxation} encoded-direction trial; "
                          "same annulus, same physical dt, same gates"),
    })
    declaration = {
        "classification": "bounded small-step descent test; no accepted material step",
        "source_run": source.relative_to(ROOT).as_posix(),
        "source_trial": pipeline.claim(trial_path),
        "base_residual": pipeline.claim(ROOT / BASE_RESIDUAL),
        "physical_old_time_level": pipeline.claim(ROOT / OLD_TIME_LEVEL),
        "definition": "encoded = source base_encoded_state + alpha * source finite_direction",
        "trial_gates": trial_gates,
        "warm_seed": seed,
        "purpose": args.purpose,
        "science_acceptance_gates_changed": False,
        "physical_dt_changed": False,
        "direction_unchanged": True,
        "why": ("the 0.0625 candidate raises the encoded residual ratio to 1.126 and the "
                "0.03125 branch leaves the physical domain; this tests whether any small "
                "step descends before rebuilding the direction"),
    }
    if args.dry_run:
        # 原生核验是只读的，放在 dry-run 之前，使试运行也能覆盖它。
        audit = {"skipped": True, "reason": "local self-test flag"} if args.skip_native_audit \
            else audit_native_trial(config, trial)
        print(json.dumps({"dry_run": True, "run": config["run"], "alpha": args.relaxation,
                          "source_alpha": trial_gates["source_alpha"],
                          "trial_gates": trial_gates["trust_region_and_provenance"],
                          "native_trial_audit": audit,
                          "warm_seed": seed, "workers": args.workers,
                          "maximum_maps": args.maximum_maps}, indent=2))
        return

    run.mkdir(parents=True)
    trial_out = run / "trial_material.npz"
    np.savez(trial_out, **trial)
    protocol = run / "small_step_declaration.json"
    pipeline.write_json(protocol, declaration)
    config["sources"] = list(config.get("sources", [])) + [
        pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix(".sbatch")),
        pipeline.claim(source / "state.json"), pipeline.claim(trial_path),
        pipeline.claim(protocol), pipeline.claim(trial_out)]
    audit = {"skipped": True, "reason": "local self-test flag"} if args.skip_native_audit \
        else audit_native_trial(config, trial)
    pipeline.write_json(run / "native_trial_audit.json", audit)
    pipeline.write_json(run / "config.json", config)
    pipeline.write_json(run / "trial_migration.json", {
        "source": pipeline.claim(trial_path), "destination": pipeline.claim(trial_out),
        "method": "new smaller-alpha encoded candidate, decoded on Linux",
        "base_and_direction_unchanged": True, "declaration": pipeline.claim(protocol)})
    pipeline.write_json(run / "state.json", {
        "config_sha256": pipeline.sha256(run / "config.json"), "status": "initializing",
        "initialization_blocks": [], "history": [],
        "slots": [pipeline.relative(run / f"state_{i}.dat") for i in range(3)],
        "current_slot": 0, "active_map": None})
    print(json.dumps({"prepared": config["run"], "alpha": args.relaxation,
                      "config_sha256": pipeline.sha256(run / "config.json")}))


def claim(trial: dict) -> None:
    """Fail before writing anything if the built trial is malformed."""
    required = ("temperature_k", "hydrogen_fraction", "helium_fraction",
                "specific_material_energy_erg_g", "encoded_state",
                "base_encoded_state", "finite_direction", "base_residual", "relaxation")
    for name in required:
        if name not in trial:
            raise SystemExit(f"built trial is missing {name}")
    for name in required[:-1]:
        values = np.asarray(trial[name])
        if not np.all(np.isfinite(values)):
            raise SystemExit(f"built trial has non-finite {name}")
    if not np.all(np.asarray(trial["temperature_k"]) > 0.0):
        raise SystemExit("built trial has non-positive temperature")


if __name__ == "__main__":
    main()
