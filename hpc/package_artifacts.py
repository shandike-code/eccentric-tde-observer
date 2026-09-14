"""Create a transfer bundle without reading or copying radiation checkpoint arrays."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tarfile

from preflight import ROOT, sha256


def selected(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if not path.is_file() or path.is_symlink() or path.name == ".DS_Store":
        return False
    if "__pycache__" in relative.parts or relative.parts[:2] == ("outputs", "hpc"):
        return False
    return not ("checkpoints" in relative.parts and path.suffix == ".dat")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--profile", choices=("historical", "runtime"), default="historical")
    args = parser.parse_args()
    if args.archive.resolve().is_relative_to((ROOT / "outputs").resolve()):
        parser.error("write the archive outside outputs/")
    if args.archive.exists():
        parser.error("refusing to overwrite an existing bundle")
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    files = {}
    runtime_arrays = {
        "phase7b9de_half_trial_material_state.npz", "phase7b4r_depth128_phase2048.npz",
        "phase7b5p_master_worker_input.npz", "phase7b9f_base_material_residual.npy",
        "phase7b7h_second_material_iterate.npz", "phase7b7d_damped_material_state.npz",
        "phase7b7g_assembled_atomic_rates.npz",
    }
    with tarfile.open(args.archive, "w:gz", compresslevel=3) as archive:
        for path in sorted((ROOT / "outputs").rglob("*")):
            if not selected(path):
                continue
            if args.profile == "runtime" and path.suffix != ".json" and path.name not in runtime_arrays:
                continue
            relative = path.relative_to(ROOT).as_posix()
            files[relative] = {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
            archive.add(path, arcname=relative, recursive=False)
            if len(files) % 2000 == 0:
                print(f"Packed {len(files)} small-artifact files", flush=True)
    result = {"archive": args.archive.name, "release_tag": "handoff-2026-09-14", "profile": args.profile,
              "size_bytes": args.archive.stat().st_size, "sha256": sha256(args.archive),
              "unpacked_bytes": sum(x["size_bytes"] for x in files.values()),
              "contains_radiation_checkpoints": False, "files": files}
    name = "runtime_bundle.json" if args.profile == "runtime" else "artifact_bundle.json"
    (ROOT / "handoff" / name).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
