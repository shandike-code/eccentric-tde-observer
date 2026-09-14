"""Recoverable CPU pipeline: initialize -> radiation pair -> H/He matter trial.

New HPC protocols own their thresholds and source hashes. Historical protocols
are not edited. The native phase workers supply the actual physics kernels.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts"), str(ROOT / "hpc")]
from preflight import environment, safe_path, sha256, verify_claims

SHAPE = (9632, 32, 4096)
STATE_BYTES = 10_099_884_032
MATERIAL = "outputs/phase7b9de_half_trial_material_state.npz"
OLD = "outputs/phase7b4r_depth128_phase2048.npz"
MASTER = "outputs/phase7b5p_master_worker_input.npz"
FIXED = "outputs/phase7b9dh_fixed_material_radiation_worker_template.json"
THRESHOLDS = (1e-4, 2e-4, 2.5e-4, 3e-4)
STOP = False


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(temporary, path)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def claim(path: Path) -> dict:
    return {"path": relative(path), "size_bytes": path.stat().st_size, "sha256": sha256(path)}


def signal_stop(_number, _frame):
    global STOP
    STOP = True
    print("Stop requested; finish and commit the current block batch.", flush=True)


def require_allocation(workers: int):
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("Heavy pipeline work requires a Slurm allocation.")
    if workers > int(os.environ.get("SLURM_CPUS_PER_TASK", "0")):
        raise RuntimeError("Worker count exceeds allocated CPUs.")
    memory = os.environ.get("SLURM_MEM_PER_NODE")
    if memory and float(memory) < workers * 6144 + 2048:
        raise RuntimeError("Request at least 6 GiB per worker plus 2 GiB parent headroom.")


def prepare(run: Path, workers: int, threshold: float, maximum_maps: int, seed: str):
    if run.exists():
        raise RuntimeError("Run directory exists; use run/status to resume it.")
    if not 1 <= workers <= 16 or threshold not in THRESHOLDS or maximum_maps < 2:
        raise ValueError("Invalid worker count, threshold or map budget")
    required = [ROOT / x for x in (MATERIAL, OLD, MASTER, FIXED,
                "outputs/phase7b7i_preregistered_second_radiation_map.json",
                "outputs/phase7b7j_preregistered_second_assembled_feedback.json",
                "outputs/phase7b9bu_preregistered_trial_residual_acceptance.json",
                "outputs/phase7b9f_base_material_residual.npy")]
    missing = [relative(p) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError(f"Restore the input artifact bundle first: {missing}")
    # Pin the small native worker dependencies actually reused by this adapter.
    for template_name in ("outputs/phase7b7i_preregistered_second_radiation_map.json",
                          "outputs/phase7b7j_preregistered_second_assembled_feedback.json"):
        for source in read(ROOT / template_name)["sources"].values():
            if not source["path"].endswith(".dat"):
                required.append(ROOT / source["path"])
    required = sorted(set(required))
    missing = [relative(p) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError(f"Native worker dependencies missing: {missing}")
    sources = [claim(p) for folder in ("src", "scripts", "hpc")
               for p in sorted((ROOT / folder).rglob("*.py"))]
    sources.extend(claim(p) for p in required)
    warm = None
    if seed == "warm":
        snapshot = read(ROOT / "handoff/restart_manifest.json")
        warm = snapshot["checkpoints"][0]
        # Byte hashing is deferred to a compute job, not the login shell.
        if verify_claims(ROOT, [warm], hash_files=False):
            raise RuntimeError("Warm seed is missing; use cold or transfer the checkpoint.")
    run.mkdir(parents=True)
    config = {"version": 1, "run": relative(run), "workers": workers,
              "radiation_threshold": threshold, "boundary_threshold": 1e-3,
              "maximum_maps": maximum_maps, "shape": list(SHAPE), "seed": seed,
              "warm_seed": warm, "sources": sources,
              "physics_scope": "one fixed 0.0625 material trial; one annulus and physical step",
              "material_trial_accepted": False, "full_disc_complete": False,
              "original_strict_threshold": 1e-4,
              "threshold_classification": "explicit HPC sensitivity experiment",
              "source_path": "native positive phase workers; no physical kernel modifications"}
    write_json(run / "config.json", config)
    write_json(run / "state.json", {"config_sha256": sha256(run / "config.json"),
               "status": "initializing", "initialization_blocks": [], "history": [],
               "slots": [relative(run / f"state_{i}.dat") for i in range(3)],
               "current_slot": 0, "active_map": None})
    print(json.dumps({"prepared": relative(run), "config_sha256": sha256(run / "config.json"),
                      "next": "submit pipeline through Slurm"}))


def configure_native(config: dict, input_path: Path):
    """Explicit adapter for a NEW HPC protocol using unchanged native kernels."""
    from scripts import phase7b9ac_global_positive_picard_map as native
    fixed = read(ROOT / FIXED)
    trial_path = ROOT / config["run"] / "trial_material.npz"
    if trial_path.exists():
        fixed["sources"]["current_material_state"] = claim(trial_path)
    native.base.phase7b9d._configure_worker(fixed, input_path)
    template = native.base.phase7b7i._load_protocol(ROOT / FIXED, validate_sources=False)
    context = native.base.phase7b7i.phase7b7e.phase7b5x._context(template)
    return native, fixed, template, context


def worker(config_path: Path, operation: str, block_index: int, input_path: Path,
           output_path: Path, report_path: Path, input_hash: str):
    import numpy as np
    config = read(config_path)
    native, fixed, template, context = configure_native(config, input_path)
    block = context["blocks"][block_index]
    if operation == "initialize":
        phase7b5x = native.base.phase7b7i.phase7b7e.phase7b5x
        parent = phase7b5x._parent_boosted_planck_outer(
            block.local_stencil.outer_lab_edge_hz, context["mu"], context["weight"],
            context["parent_beta"], context["full"]["temperature_k"][context["phase"]],
        )
        start = block.core_group_start + context["stencil"].active_outer_group_start - block.outer_group_start
        count = block.core_group_stop - block.core_group_start
        values = np.repeat(parent[start:start + count], 16, axis=2)
        if values.shape != (count, SHAPE[1], SHAPE[2]):
            raise ArithmeticError("Initialization core/halo mapping has the wrong shape")
        if not np.all(np.isfinite(values)) or np.any(values < 0):
            raise ArithmeticError("Planck seed is not finite and nonnegative")
        out = np.memmap(output_path, mode="r+", dtype="<f8", shape=SHAPE)
        out[block.core_group_start:block.core_group_stop] = values
        out.flush()
        write_json(report_path, {"block_index": block_index,
                   "core_group_start": block.core_group_start, "core_group_stop": block.core_group_stop})
        return
    # The historical loader is not used on a new protocol. Native _run_worker
    # receives a separately validated explicit configuration, as in older adapters.
    protocol = {"sources": {"finite_trial_protocol": {"path": FIXED},
                             "phase7b5p_master_input": {"path": MASTER}},
                "configuration": {"physical_frequency_groups": SHAPE[0],
                    "angular_direction_count": SHAPE[1], "radiation_depth_cell_count": SHAPE[2],
                    "input_state_path": relative(input_path), "input_state_sha256": input_hash,
                    "diagnostic_fixed_iteration_count": 1, "spatial_scheme": "hybrid_step_turning_upwind",
                    "source_map_only": True}}
    native.EXPECTED_PROTOCOL_SHA256 = sha256(config_path)
    native._load_protocol = lambda _path, validate_sources=False: protocol
    native.base.phase7b9i._load_protocol = lambda _path, validate_sources=False: fixed
    native._run_worker(config_path, block_index, output_path, report_path)


def block_hash(path: Path, first: int, last: int) -> str:
    from scripts.phase7b9d_inner_converged_base_radiation import _block_sha256
    return _block_sha256(path, SHAPE, first, last)


def batches(config: dict, state: dict, operation: str, input_path: Path, output_path: Path,
            records: list[dict], report_dir: Path, state_path: Path):
    """Commit complete block batches; hashes make interrupted jobs recoverable."""
    report_dir.mkdir(parents=True, exist_ok=True)
    for row in records:
        if block_hash(output_path, row["core_group_start"], row["core_group_stop"]) != row["output_block_sha256"]:
            raise RuntimeError("A committed output block changed; do not discard its provenance.")
    done = {r["block_index"] for r in records}
    pending = [i for i in range(76) if i not in done]
    config_path = ROOT / config["run"] / "config.json"
    for offset in range(0, len(pending), config["workers"]):
        if STOP:
            return False
        indices = pending[offset:offset + config["workers"]]
        processes = []
        for index in indices:
            cmd = [sys.executable, str(Path(__file__).resolve()), "worker", "--config", str(config_path),
                   "--operation", operation, "--block", str(index), "--input", str(input_path),
                   "--output", str(output_path), "--report", str(report_dir / f"block{index:02d}.json"),
                   "--input-hash", state.get("current_sha256", "initializing")]
            processes.append(subprocess.Popen(cmd, cwd=ROOT))
        codes = [p.wait() for p in processes]
        if any(codes):
            raise RuntimeError(f"Worker batch failed: {codes}; completed batches remain restartable")
        for index in indices:
            row = read(report_dir / f"block{index:02d}.json")
            if row["block_index"] != index:
                raise RuntimeError("Block report identity mismatch")
            if operation == "map" and (row.get("protocol_sha256") != sha256(config_path)
                    or row.get("input_state_sha256") != state["current_sha256"]):
                raise RuntimeError("Block report belongs to another input/configuration")
            row["output_block_sha256"] = block_hash(output_path, row["core_group_start"], row["core_group_stop"])
            records.append(row)
        records.sort(key=lambda x: x["block_index"])
        write_json(state_path, state)
        print(json.dumps({"operation": operation, "completed_blocks": len(records), "total": 76}), flush=True)
    return True


def aggregate(rows: list[dict], frequency_groups: int = SHAPE[0]) -> dict:
    import math
    ownership = [0] * frequency_groups
    for row in rows:
        if not 0 <= row["core_group_start"] < row["core_group_stop"] <= frequency_groups:
            raise ValueError("Invalid frequency ownership range")
        for i in range(row["core_group_start"], row["core_group_stop"]):
            ownership[i] += 1
        for key, value in row.items():
            if isinstance(value, (float, int)) and not math.isfinite(value):
                raise ArithmeticError(f"Nonfinite block metric: {key}")
    if any(x != 1 for x in ownership):
        raise ArithmeticError("Frequency ownership has gaps/duplicates")
    if min(r["minimum_input_intensity"] for r in rows) < 0 or min(r["minimum_mapped_intensity"] for r in rows) < 0:
        raise ArithmeticError("Negative intensity")
    def ratio(n, d):
        if d == 0:
            if n == 0: return 0.0
            raise ArithmeticError("Nonzero numerator with zero normalization")
        return n / d
    scale = max(r["maximum_radiation_scale"] for r in rows)
    current = sum(r["current_boundary_bolometric"] for r in rows)
    mapped = sum(r["mapped_boundary_bolometric"] for r in rows)
    return {"residual": ratio(max(r["maximum_absolute_radiation_change"] for r in rows), scale),
            "boundary_l1": ratio(sum(r["boundary_spectrum_l1_numerator"] for r in rows),
                max(sum(r["current_boundary_absolute_scale"] for r in rows),
                    sum(r["mapped_boundary_absolute_scale"] for r in rows))),
            "boundary_bolometric": ratio(abs(mapped - current), max(abs(current), abs(mapped))),
            "maximum_worker_rss_mib": max(r["peak_process_rss_mib"] for r in rows)}


def pair_ready(history: list[dict], threshold: float) -> bool:
    return len(history) >= 2 and all(r["residual"] < threshold and r["boundary_l1"] < 1e-3
           and r["boundary_bolometric"] < 1e-3 for r in history[-2:])


def migrate_trial(run: Path):
    """Re-decode the frozen encoded vector on this architecture; audit roundoff."""
    import numpy as np
    from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
    with np.load(ROOT / MATERIAL) as source:
        data = {k: np.array(source[k], copy=True) for k in source.files}
    decoded = GroundStateLogSimplexCodec(128).decode(data["encoded_state"])
    changes = {}
    for name in ("temperature_k", "hydrogen_fraction", "helium_fraction"):
        a = data[name]; b = np.asarray(getattr(decoded, name))
        # A global roundoff audit, not a physical state-repair operation.
        delta = float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(a))), 1.0))
        changes[name] = delta
        if delta > 2e-12:
            raise ArithmeticError("Cross-platform decode differs beyond roundoff; investigate")
        data[name] = b
    np.savez(run / "trial_material.npz", **data)
    write_json(run / "trial_migration.json", {"source": claim(ROOT / MATERIAL),
               "destination": claim(run / "trial_material.npz"), "relative_changes": changes,
               "encoded_state_changed": False, "physical_kernel_changed": False})


def feedback_protocol(config: dict, state: dict) -> Path:
    """Build a new explicit threshold protocol consumed by the existing pair engine."""
    from scripts import phase7b9_formal_feedback_pair_adapter as pair
    run = ROOT / config["run"]
    path = run / "feedback_protocol.json"
    if path.exists():
        return path
    previous, final = state["history"][-2:]
    if previous["output_sha256"] != final["input_sha256"]:
        raise RuntimeError("Feedback endpoints are not consecutive")
    template = read(ROOT / "outputs/phase7b7j_preregistered_second_assembled_feedback.json")
    migration = []
    for name, old in template["sources"].items():
        if name in {"mapped_radiation_state", "second_material_iterate", "physical_old_time_level"}:
            continue
        now = claim(ROOT / old["path"])
        migration.append({"name": name, "historical": old, "hpc": now})
        template["sources"][name] = now
    write_json(run / "feedback_template.json", template)
    write_json(run / "feedback_dependency_migration.json", {"changes": migration,
        "reason": "Explicit new HPC protocol; historical manifests remain unchanged",
        "required_validation": "positive-path source migration controls and Linux smoke/benchmark"})
    gates = deepcopy(read(ROOT / "outputs/phase7b9bu_preregistered_trial_residual_acceptance.json")["gates"])
    gates["each_global_original_operator_residual_below"] = config["radiation_threshold"]
    sources = {"trial_material": claim(run / "trial_material.npz"),
       "physical_old_time_level": claim(ROOT / OLD),
       "base_residual": claim(ROOT / "outputs/phase7b9f_base_material_residual.npy"),
       "phase7b7j_protocol": claim(run / "feedback_template.json"),
       "adapter_runner": claim(ROOT / "scripts/phase7b9_formal_feedback_pair_adapter.py"),
       "previous_radiation": {"path": previous["input_path"], "size_bytes": STATE_BYTES, "sha256": previous["input_sha256"]},
       "final_radiation": {"path": final["input_path"], "size_bytes": STATE_BYTES, "sha256": final["input_sha256"]}}
    cfg = {"physical_frequency_groups": 9632, "core_frequency_groups": 128, "block_count": 76,
       "angular_direction_count": 32, "radiation_depth_cell_count": 4096, "material_cell_count": 128,
       "rate_quadrature_order_per_group": 16, "maximum_concurrent_processes": config["workers"],
       "feedback_work_directory": relative(run / "feedback"),
       "summary_path": relative(run / "feedback_summary.json"), "figure_path": relative(run / "feedback.png"),
       "target_material_output": relative(run / "target_material.npz"),
       "encoded_residual_output": relative(run / "material_residual.npy")}
    for label, row in (("previous", previous), ("final", final)):
        cfg[f"{label}_feedback_output"] = relative(run / f"{label}_feedback.npz")
        cfg[f"{label}_global_original_operator_residual"] = row["residual"]
        cfg[f"{label}_boundary_spectrum_l1"] = row["boundary_l1"]
        cfg[f"{label}_boundary_bolometric_fraction"] = row["boundary_bolometric"]
    formal_gates = pair._formal_state_gates()
    formal_gates["each_state_wall_time_strictly_below_s"] = 7200.0
    payload = {"phase": "HPC explicit inner-tolerance experiment", "classification": "HPC trial only",
       "sources": sources, "configuration": cfg, "formal_state_gates": formal_gates,
       "acceptance_gates": gates, "authorization": {"accept_dynamic_nlte_solution": False,
       "phase4_replacement": False, "full_orbit": False},
       "resource_change": "2 h wall gate per feedback state; science gates unchanged except inner tolerance"}
    write_json(path, payload)
    return path


def run_pipeline(run: Path, maps_per_job: int, do_feedback: bool):
    config = read(run / "config.json")
    require_allocation(config["workers"])
    failures = verify_claims(ROOT, config["sources"], hash_files=True)
    if failures:
        raise RuntimeError(f"Frozen sources changed: {failures[:5]}")
    config_hash = sha256(run / "config.json")
    state_path = run / "state.json"
    signal.signal(signal.SIGUSR1, signal_stop)
    with (run / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another job is writing this run")
        state = read(state_path)
        if state["config_sha256"] != config_hash:
            raise RuntimeError("Configuration changed after preparation")
        write_json(run / f"environment-{os.environ['SLURM_JOB_ID']}.json", environment())
        if state["status"] == "initializing":
            needed = sum(STATE_BYTES for x in state["slots"] if not (ROOT / x).exists()) + 8 * 1024**3
            if shutil.disk_usage(run).free < needed:
                raise RuntimeError("Need space for three 9.40625 GiB states plus 8 GiB margin")
            for slot in state["slots"]:
                path = ROOT / slot
                if not path.exists():
                    with path.open("xb") as stream: stream.truncate(STATE_BYTES)
                elif path.stat().st_size != STATE_BYTES:
                    raise RuntimeError("Work state size mismatch")
            if not (run / "trial_material.npz").exists():
                migrate_trial(run)
            first = ROOT / state["slots"][0]
            if config["seed"] == "warm":
                if verify_claims(ROOT, [config["warm_seed"]], hash_files=True):
                    raise RuntimeError("Warm seed bytes changed")
                shutil.copyfile(ROOT / config["warm_seed"]["path"], first)
            elif not batches(config, state, "initialize", first, first, state["initialization_blocks"], run / "initialization", state_path):
                return
            state.update(status="radiation", current_sha256=sha256(first))
            state["trial_sha256"] = sha256(run / "trial_material.npz")
            write_json(state_path, state)
        if sha256(run / "trial_material.npz") != state["trial_sha256"]:
            raise RuntimeError("Frozen HPC trial material changed")
        for _ in range(maps_per_job):
            if STOP or state["status"] != "radiation": break
            if len(state["history"]) >= config["maximum_maps"]:
                state["status"] = "budget_exhausted"
                write_json(state_path, state)
                break
            first = ROOT / state["slots"][state["current_slot"]]
            if sha256(first) != state["current_sha256"]:
                raise RuntimeError("Committed input state changed")
            next_slot = (state["current_slot"] + 1) % 3
            output = ROOT / state["slots"][next_slot]
            if state["active_map"] is None:
                state["active_map"] = {"iteration": len(state["history"]) + 1, "records": [],
                    "input_sha256": state["current_sha256"], "wall_s": 0.0}
                write_json(state_path, state)
            active = state["active_map"]
            if active["input_sha256"] != state["current_sha256"]:
                raise RuntimeError("Partial map belongs to another input")
            started = time.monotonic()
            complete = batches(config, state, "map", first, output, active["records"],
                               run / f"map{active['iteration']:04d}", state_path)
            active["wall_s"] += time.monotonic() - started
            if not complete:
                write_json(state_path, state)
                return
            metrics = aggregate(active["records"])
            row = {"iteration": active["iteration"], "input_path": relative(first),
                   "input_sha256": state["current_sha256"], "output_path": relative(output),
                   "output_sha256": sha256(output), "wall_s": active["wall_s"], **metrics}
            state["history"].append(row)
            state.update(current_slot=next_slot, current_sha256=row["output_sha256"], active_map=None)
            if metrics["maximum_worker_rss_mib"] >= 6144:
                state["status"] = "resource_gate_failed"
            elif pair_ready(state["history"], config["radiation_threshold"]):
                state["status"] = "feedback_ready"
            write_json(state_path, state)
            print(json.dumps({"status": state["status"], **row}), flush=True)
        if state["status"] in {"feedback_ready", "feedback_running"} and do_feedback and not STOP:
            from scripts import phase7b9_formal_feedback_pair_adapter as pair
            path = feedback_protocol(config, state)
            protocol_hash = sha256(path)
            if state.get("feedback_protocol_sha256", protocol_hash) != protocol_hash:
                raise RuntimeError("Committed feedback protocol changed")
            state["feedback_protocol_sha256"] = protocol_hash
            state["status"] = "feedback_running"
            write_json(state_path, state)
            report = pair.run_pair(path, protocol_hash)
            # The legacy failure report labels a computed pair as 'passed' even
            # when a stability check fails. Require ALL explicit gate checks here.
            checks = report["gate_checks"]
            accepted = all(checks.values()) and report["decision"].get("finite_trial_accepted_as_one_nonlinear_step", False)
            state["status"] = "one_material_trial_accepted" if accepted else "material_trial_not_accepted"
            state["feedback_report_sha256"] = sha256(run / "feedback_summary.json")
            state["full_disc_complete"] = False
            write_json(state_path, state)
            print(json.dumps({"status": state["status"], "failed_gates": [k for k, v in checks.items() if not v],
                  "next": "coupled-column continuation requires a separate outer-iteration milestone"}), flush=True)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--run", required=True)
    prep.add_argument("--workers", type=int, default=2)
    prep.add_argument("--threshold", type=float, default=2.5e-4)
    prep.add_argument("--maximum-maps", type=int, default=256)
    prep.add_argument("--seed", choices=("cold", "warm"), default="cold")
    run = sub.add_parser("run")
    run.add_argument("--run", required=True)
    run.add_argument("--maps-per-job", type=int, default=8)
    run.add_argument("--no-feedback", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--run", required=True)
    w = sub.add_parser("worker")
    w.add_argument("--config", type=Path, required=True)
    w.add_argument("--operation", choices=("initialize", "map"), required=True)
    w.add_argument("--block", type=int, required=True)
    for name in ("input", "output", "report"): w.add_argument(f"--{name}", type=Path, required=True)
    w.add_argument("--input-hash", required=True)
    args = p.parse_args()
    if args.command == "worker":
        worker(args.config, args.operation, args.block, args.input, args.output, args.report, args.input_hash)
        return
    path = safe_path(ROOT, args.run)
    if not path.is_relative_to(ROOT / "outputs/hpc"):
        p.error("run must be below outputs/hpc/")
    if args.command == "prepare": prepare(path, args.workers, args.threshold, args.maximum_maps, args.seed)
    elif args.command == "status":
        state = read(path / "state.json")
        print(json.dumps({"status": state["status"], "maps": len(state["history"]),
                          "latest": state["history"][-1] if state["history"] else None,
                          "active_blocks": len((state.get("active_map") or {}).get("records", []))}, indent=2))
    else:
        if not 1 <= args.maps_per_job <= 20: p.error("maps per job must be 1..20")
        run_pipeline(path, args.maps_per_job, not args.no_feedback)


if __name__ == "__main__":
    main()
