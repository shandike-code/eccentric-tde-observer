"""Prepare a run seeded from a Linux-side radiation state.

`hpc/pipeline.py prepare --seed warm` always takes `handoff/restart_manifest.json`
`checkpoints[0]`, i.e. the Mac handoff endpoint -- it never picks up a newer state
produced on this cluster. That manifest is also the reference that
`handoff/fetch_warm_seed.py verify` checks against, so repointing it would break
the transfer tool's own self-check.

This module therefore writes the run's `config.json` and `state.json` directly,
declaring the chosen Linux state as `warm_seed`. The standard
`hpc/submit.sh pipeline` entry point then does the rest, unmodified:

* `verify_claims(..., hash_files=True)` hashes the declared seed in the job;
* `shutil.copyfile` copies it into slot 0 of the new run -- the new run owns its
  own buffers and the source run's states are never written to;
* `migrate_trial` re-decodes the frozen material candidate in-job.

Nothing under src/, scripts/ or hpc/ is touched, so every existing run keeps its
frozen source inventory intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def claim(path: Path) -> dict:
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True,
                        help="existing run whose config.json is copied")
    parser.add_argument("--source", required=True,
                        help="Linux radiation state to seed from (state_N.dat)")
    parser.add_argument("--run", required=True, help="new run directory")
    parser.add_argument("--maximum-maps", type=int, default=8)
    args = parser.parse_args()

    template = ROOT / args.template
    source = ROOT / args.source
    run = ROOT / args.run
    if not run.resolve().is_relative_to((ROOT / "outputs/hpc").resolve()):
        raise SystemExit("run must live under outputs/hpc/")
    if run.exists():
        raise SystemExit(f"run directory exists: {run}")
    if not source.is_file():
        raise SystemExit(f"seed state missing: {source}")

    config = json.loads((template / "config.json").read_text())
    warm_seed = claim(source)
    config["run"] = run.resolve().relative_to(ROOT.resolve()).as_posix()
    config["seed"] = "warm"
    config["warm_seed"] = warm_seed
    config["maximum_maps"] = args.maximum_maps
    config["seed_provenance"] = (
        "Linux-side converged state, not the Mac handoff endpoint; prepared by "
        "diagnostics/seed_from_linux_state.py because pipeline.prepare --seed warm "
        "is hard-wired to handoff/restart_manifest.json checkpoints[0]"
    )

    run.mkdir(parents=True)
    config_path = run / "config.json"
    config_path.write_text(json.dumps(config, indent=2, allow_nan=False) + "\n")
    config_hash = sha256(config_path)

    state = {
        "config_sha256": config_hash,
        "status": "initializing",
        "initialization_blocks": [],
        "history": [],
        "slots": [f"{config['run']}/state_{i}.dat" for i in range(3)],
        "current_slot": 0,
        "active_map": None,
    }
    state_path = run / "state.json"
    state_path.write_text(json.dumps(state, indent=2, allow_nan=False) + "\n")

    print(json.dumps({
        "prepared": config["run"],
        "config_sha256": config_hash,
        "warm_seed": warm_seed,
        "maximum_maps": args.maximum_maps,
        "note": "submit with: TDE_RUN=%s TDE_MAPS=1 bash hpc/submit.sh pipeline" % config["run"],
    }, indent=2))


if __name__ == "__main__":
    main()
