"""Slurm migration check on one real-size, synthetic frequency block.

Sparse full-shape files provide neighboring zero input. This checks adapters,
not full-column convergence, and never reads or modifies historical big states.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from pipeline import (ROOT, SHAPE, STATE_BYTES, claim, feedback_protocol,
                      migrate_trial, prepare, read, relative, require_allocation,
                      safe_path, sha256, write_json)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="outputs/hpc/block-check")
    parser.add_argument("--local-validation", action="store_true",
                        help="Allow this bounded single-block check on the development Mac only")
    parser.add_argument("--reference-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.local_validation:
        if sys.platform != "darwin":
            parser.error("School Linux checks must run through Slurm")
    else:
        require_allocation(1)
    run = safe_path(ROOT, args.run)
    if not run.is_relative_to(ROOT / "outputs/hpc"):
        parser.error("run must be under outputs/hpc")
    if args.reference_worker:
        from scripts import phase7b9du_exhausted_dp_picard_continuation as legacy
        protocol = ROOT / "outputs/phase7b9du_preregistered_exhausted_dp_picard_continuation.json"
        legacy._run_worker(protocol,
            "51a670f53f9bb7be7abc312e31b01d5f6d3102dc633fcab328c9c01bba78b15b",
            9, 0, run / "input.dat", read(run / "input_claim.json")["sha256"],
            run / "reference.dat", run / "reference.json")
        return
    prepare(run, 1, 2.5e-4, 2, "cold")
    migrate_trial(run)
    for name in ("input.dat", "mapped.dat", "reference.dat"):
        with (run / name).open("xb") as stream:
            stream.truncate(STATE_BYTES)
    def worker(operation, output, report, input_hash):
        subprocess.run([sys.executable, str(ROOT / "hpc/pipeline.py"), "worker",
            "--config", str(run / "config.json"), "--operation", operation,
            "--block", "0", "--input", str(run / "input.dat"),
            "--output", str(run / output), "--report", str(run / report),
            "--input-hash", input_hash], check=True, cwd=ROOT)
    worker("initialize", "input.dat", "initialization.json", "initializing")
    source = claim(run / "input.dat")
    write_json(run / "input_claim.json", source)
    worker("map", "mapped.dat", "mapped.json", source["sha256"])
    subprocess.run([sys.executable, str(Path(__file__).resolve()), "--run", args.run,
                    "--reference-worker"] + (["--local-validation"] if args.local_validation else []),
                   check=True, cwd=ROOT)
    import numpy as np
    actual = np.memmap(run / "mapped.dat", mode="r", dtype="<f8", shape=SHAPE)[:128]
    expected = np.memmap(run / "reference.dat", mode="r", dtype="<f8", shape=SHAPE)[:128]
    difference = float(np.max(np.abs(actual - expected)))
    scale = float(np.max(np.abs(expected)))
    error = difference / scale if scale else difference
    # Exact equality is reported. Tiny decoding/BLAS rounding on another CPU is
    # audited separately and must not be confused with changed source equations.
    passed = bool(np.all(np.isfinite(actual)) and np.all(actual >= 0) and error <= 1e-11)
    result = {"scope": "one 128 x 32 x 4096 block; synthetic zero neighbors; not a physical solution",
        "new_worker": read(run / "mapped.json"), "reference_worker": read(run / "reference.json"),
        "bitwise_equal": bool(np.array_equal(actual, expected)),
        "maximum_absolute_difference": difference, "global_relative_difference": error,
        "comparison_tolerance": 1e-11, "radiation_adapter_passed": passed,
        "material_migration": read(run / "trial_migration.json"),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "development_mac_validation": args.local_validation}
    write_json(run / "block_check.json", result)
    if not passed:
        raise ArithmeticError("Native radiation comparison failed; inspect block_check.json")
    # Exercise the formal-feedback adapter's actual microphysics on this block.
    # Duplicate synthetic endpoints are only fixtures; never invoke run_pair or
    # claim they form an independently converged feedback pair.
    row = {"input_path": source["path"], "input_sha256": source["sha256"],
           "output_sha256": source["sha256"], "residual": 0.0,
           "boundary_l1": 0.0, "boundary_bolometric": 0.0}
    protocol_path = feedback_protocol(read(run / "config.json"), {"history": [row, row]})
    from scripts import phase7b9_formal_feedback_pair_adapter as pair
    pair._validate_worker_template_sources(read(protocol_path))
    pair.run_worker_adapter(protocol_path, sha256(protocol_path), "final", 0,
                            run / "feedback_block.npz", run / "feedback_block.json")
    with np.load(run / "feedback_block.npz") as arrays:
        finite = all(np.all(np.isfinite(arrays[k])) for k in arrays.files
                     if np.issubdtype(arrays[k].dtype, np.number))
    result["feedback_adapter_finite"] = bool(finite)
    result["feedback_block_report"] = read(run / "feedback_block.json")
    result["full_column_or_material_acceptance_tested"] = False
    write_json(run / "block_check.json", result)
    if not finite:
        raise ArithmeticError("Nonfinite feedback block")
    print(f"Block adapter checks passed; see {relative(run / 'block_check.json')}")


if __name__ == "__main__":
    main()
