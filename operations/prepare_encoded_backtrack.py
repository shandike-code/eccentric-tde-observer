"""Declare one new candidate along the original frozen encoded direction.

The old run, base vector, direction, physical time level and numerical kernels
remain unchanged. A previous radiation field is only a numerical warm seed.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "hpc")]
import pipeline
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec, ground_state_material_trial_within_trust_region)


def candidate_arrays(source, old, baseline_residual, relaxation):
    """Check provenance identities before decoding a smaller, exact trial."""
    previous = float(source["relaxation"])
    if not np.isfinite(relaxation) or not 0 < relaxation < previous:
        raise ValueError("backtrack must be a positive smaller relaxation")
    base = np.asarray(source["base_encoded_state"])
    direction = np.asarray(source["finite_direction"])
    if not np.array_equal(source["encoded_state"], base + previous * direction):
        raise RuntimeError("source candidate is not on its declared frozen direction")
    if not np.array_equal(source["base_residual"], baseline_residual):
        raise RuntimeError("source base residual differs from formal acceptance baseline")
    phase = int(source["phase_index"])
    if (float(source["step_duration_s"]) != float(old["step_duration_s"][phase])
            or not np.array_equal(source["density_g_cm3"], old["density_g_cm3"][phase])):
        raise RuntimeError("physical old time level, dt or density changed")
    codec = GroundStateLogSimplexCodec(len(source["temperature_k"]))
    previous_decoded = codec.decode(source["encoded_state"])
    for name in ("temperature_k", "hydrogen_fraction", "helium_fraction"):
        if not np.array_equal(source[name], getattr(previous_decoded, name)):
            raise RuntimeError("source trial is not the exact frozen decode")
    encoded = base + relaxation * direction
    candidate = codec.decode(encoded)
    trust = ground_state_material_trial_within_trust_region(
        codec, base, encoded, maximum_relative_temperature_change=0.5,
        maximum_absolute_material_energy_increment_fraction=0.25,
        maximum_population_fraction_change=0.05)
    gates = {
        "trust_region": bool(trust),
        "encoded_definition": bool(np.array_equal(encoded, base + relaxation * direction)),
        "positive_temperature": bool(np.all(candidate.temperature_k > 0)),
        "positive_material_energy": bool(np.all(candidate.specific_material_energy_erg_g > 0)),
        "nonnegative_population": bool(np.all(candidate.hydrogen_fraction >= 0)
                                       and np.all(candidate.helium_fraction >= 0)),
        "simplex": all(float(np.max(np.abs(np.sum(a, axis=1) - 1))) < 4*np.finfo(float).eps
                       for a in (candidate.hydrogen_fraction, candidate.helium_fraction)),
        "finite": all(np.all(np.isfinite(a)) for a in (base, direction, encoded,
                      candidate.temperature_k, candidate.specific_material_energy_erg_g,
                      candidate.hydrogen_fraction, candidate.helium_fraction)),
    }
    if not all(gates.values()):
        raise RuntimeError(f"candidate physical/trust gates failed: {gates}")
    result = {k: np.array(v, copy=True) for k, v in source.items()}
    for name in ("temperature_k", "hydrogen_fraction", "helium_fraction", "specific_material_energy_erg_g"):
        result[name] = np.array(getattr(candidate, name), copy=True)
    result.update(encoded_state=encoded, relaxation=np.array(relaxation))
    return result, gates


def load_arrays(path):
    with np.load(path, allow_pickle=False) as data:
        return {k: np.array(data[k], copy=True) for k in data.files}


def audit_native_trial(cfg, trial):
    native, fixed, template, context = pipeline.configure_native(cfg, ROOT / cfg["warm_seed"]["path"])
    material = native.base.phase7b7i._second_full_material(template)
    for field, parent in (("density_g_cm3", "density_parent"), ("temperature_k", "temperature_parent"),
                          ("hydrogen_fraction", "hydrogen_parent"), ("helium_fraction", "helium_parent")):
        expected = np.concatenate((trial[field], trial[field][::-1]), axis=0)
        if not np.array_equal(material[parent], expected):
            raise RuntimeError(f"native worker did not consume new trial: {field}")
    if context["phase"] != int(trial["phase_index"]) or context["duration_s"] != float(trial["step_duration_s"]):
        raise RuntimeError("native physical phase or dt changed")
    return {"trial_source": fixed["sources"]["current_material_state"],
            "native_mirrored_material_exact": True, "physical_phase_and_dt_exact": True}


def verified_source_trial(source_run, state):
    """Historical diagnostic states may omit trial_sha256; use the formal pair."""
    rounds = state.get("diagnostic", {}).get("rounds", [])
    if not rounds:
        raise RuntimeError("source candidate has no completed formal feedback to anchor its identity")
    protocol_path = (ROOT / rounds[-1]["ledger"]).parent / "feedback_protocol.json"
    if pipeline.sha256(protocol_path) != rounds[-1]["protocol_sha256"]:
        raise RuntimeError("last completed formal protocol changed")
    frozen_trial = pipeline.read(protocol_path)["sources"]["trial_material"]
    if pipeline.verify_claims(ROOT, [frozen_trial], hash_files=True):
        raise RuntimeError("last completed formal trial changed")
    digest = pipeline.sha256(source_run / "trial_material.npz")
    if digest != frozen_trial["sha256"] or state.get("trial_sha256", digest) != digest:
        raise RuntimeError("source trial differs from formal feedback or state claim")
    return [pipeline.claim(protocol_path), frozen_trial]


def prepare(run, source_run, relaxation, workers, maximum_maps):
    pipeline.require_allocation(workers)
    if (not run.is_relative_to(ROOT / "outputs/hpc") or workers != 4
            or maximum_maps != 8 or relaxation != 0.03125):
        raise ValueError("this declaration permits only the 0.03125 / 4-worker / 8-map experiment")
    if run.exists():
        cfg = pipeline.read(run / "config.json")
        if (cfg.get("candidate_relaxation") != relaxation or cfg["workers"] != workers
                or cfg["maximum_maps"] != maximum_maps
                or cfg.get("backtrack_source_run") != pipeline.relative(source_run)):
            raise RuntimeError("existing run belongs to another declaration")
        if pipeline.verify_claims(ROOT, cfg["sources"], hash_files=True):
            raise RuntimeError("declared backtrack inputs changed")
        if pipeline.sha256(run / "config.json") != pipeline.read(run / "state.json")["config_sha256"]:
            raise RuntimeError("backtrack configuration changed")
        return
    state = pipeline.read(source_run / "state.json")
    if state["status"] != "diagnostic_round_complete" or state.get("active_map") or state.get("pending_feedback"):
        raise RuntimeError("source run must be stopped with all feedback settled")
    template = pipeline.read(source_run / "config.json")
    if pipeline.verify_claims(ROOT, template["sources"], hash_files=True):
        raise RuntimeError("source run's frozen inputs changed")
    if pipeline.sha256(source_run / "config.json") != state["config_sha256"]:
        raise RuntimeError("source configuration changed")
    trial_path = source_run / "trial_material.npz"
    formal_sources = verified_source_trial(source_run, state)
    source = load_arrays(trial_path)
    if float(source["relaxation"]) != 0.0625:
        raise RuntimeError("this is specifically the second dyadic backtrack from 0.0625")
    trial, gates = candidate_arrays(source, load_arrays(ROOT / pipeline.OLD),
        np.load(ROOT / "outputs/phase7b9f_base_material_residual.npy", allow_pickle=False), relaxation)
    seed = {"path": state["slots"][state["current_slot"]], "size_bytes": pipeline.STATE_BYTES,
            "sha256": state["current_sha256"]}
    run.mkdir(parents=True, exist_ok=False)
    trial_out = run / "trial_material.npz"
    np.savez(trial_out, **trial)
    # Both the new trial and the old direction source are separately hash-pinned.
    dependencies = [pipeline.claim(p) for p in (
        trial_path, source_run / "config.json", source_run / "state.json",
        ROOT / "operations/prepare_encoded_backtrack.py", ROOT / "operations/encoded_backtrack.sbatch")]
    dependencies.extend(formal_sources)
    declaration = {"classification": "bounded exploratory material backtrack; no accepted matter step",
        "source_run": pipeline.relative(source_run), "sources": dependencies,
        "source_relaxation": 0.0625, "candidate_relaxation": relaxation,
        "definition": "unchanged base_encoded_state + relaxation * unchanged finite_direction",
        "gates": gates, "trial": pipeline.claim(trial_out), "radiation_seed": seed,
        "physical_dt_changed": False, "science_acceptance_gates_changed": False,
        "seed_is_solution_for_new_material": False,
        "maximum_new_maps": maximum_maps, "feedback_every": 4,
        "budget_reason": "test one smaller candidate; do not extend the rejected old run",
        "prior_heating_stability_passed": False,
        "prior_failure_is_not_proof_all_static_solutions_fail": True}
    protocol = run / "backtrack_declaration.json"
    pipeline.write_json(protocol, declaration)
    cfg = deepcopy(template)
    cfg.update(run=pipeline.relative(run), seed="warm", warm_seed=seed, workers=workers,
               maximum_maps=maximum_maps, candidate_relaxation=relaxation,
               backtrack_source_run=pipeline.relative(source_run),
               physics_scope="one fixed 0.03125 encoded-direction trial; same annulus and physical dt",
               seed_provenance="previous candidate field as numerical initial guess only")
    cfg["sources"].extend(dependencies + [pipeline.claim(protocol), pipeline.claim(trial_out)])
    audit = audit_native_trial(cfg, trial)
    pipeline.write_json(run / "native_trial_audit.json", audit)
    pipeline.write_json(run / "config.json", cfg)
    pipeline.write_json(run / "trial_migration.json", {
        "source": pipeline.claim(trial_path), "destination": pipeline.claim(trial_out),
        "method": "new encoded candidate, decoded on Linux; not a roundoff migration",
        "base_and_direction_unchanged": True, "old_physical_time_unchanged": True,
        "declaration": pipeline.claim(protocol)})
    pipeline.write_json(run / "state.json", {
        "config_sha256": pipeline.sha256(run / "config.json"), "status": "initializing",
        "initialization_blocks": [], "history": [],
        "slots": [pipeline.relative(run / f"state_{i}.dat") for i in range(3)],
        "current_slot": 0, "active_map": None})
    print(f"Declared new bounded backtrack: {pipeline.relative(run)}", flush=True)


def initialize_declared_trial(run):
    cfg = pipeline.read(run / "config.json")
    if cfg.get("candidate_relaxation") != 0.03125 or not (run / "trial_material.npz").is_file():
        raise RuntimeError("initialization requires the declared new trial; no legacy fallback")
    # The API supports zero maps. The historical CLI intentionally accepts only
    # 1..20, so do not send --maps-per-job 0 through that CLI.
    pipeline.run_pipeline(run, maps_per_job=0, do_feedback=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True)
    p.add_argument("--source-run", required=True)
    p.add_argument("--initialize-only", action="store_true")
    args = p.parse_args()
    run = pipeline.safe_path(ROOT, args.run)
    if args.initialize_only:
        initialize_declared_trial(run)
    else:
        prepare(run, pipeline.safe_path(ROOT, args.source_run),
                relaxation=0.03125, workers=4, maximum_maps=8)


if __name__ == "__main__":
    main()
