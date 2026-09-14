"""Phase 7B5w：冻结频率切片平移不变的局域交叠积分门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
SOURCES = {
    "phase7b5v_summary": OUTPUT / "phase7b5v_streaming_turning_summary.json",
    "phase7b5p_master_input": OUTPUT / "phase7b5p_master_worker_input.npz",
    "mixed_frame_ale": ROOT / "src/eccentric_tde_observer/mixed_frame_ale.py",
    "mixed_frame_frequency": (
        ROOT / "src/eccentric_tde_observer/mixed_frame_frequency.py"
    ),
    "mixed_frame_streaming": (
        ROOT / "src/eccentric_tde_observer/mixed_frame_streaming.py"
    ),
}
EXPECTED_SHA256 = {
    "phase7b5v_summary": (
        "d885916120991971427dcee2f31908f9c5acc0f052d4466e1f79238f829227d3"
    ),
    "phase7b5p_master_input": (
        "c55d52b15fb01387c7c349262f06da58f1051d38b8a3c7edf284ae2bc3fcec70"
    ),
    "mixed_frame_ale": (
        "cbb2f816135a573963ad068f9c270ae76e7faf6825666db1d0c3b5807bb1fd3c"
    ),
    "mixed_frame_frequency": (
        "84f883966242c5e569e9cac8a65520b8163d489fc5cd5e11e5d5d93d4443aea1"
    ),
    "mixed_frame_streaming": (
        "0d3ba7c792ab0e3540f04fa2f676503e49fa8214d2d3dc2c09c7daf6ebb23c3f"
    ),
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def build_protocol() -> dict[str, object]:
    hashes = {name: _sha256_file(path) for name, path in SOURCES.items()}
    if hashes != EXPECTED_SHA256:
        raise RuntimeError(f"frozen Phase 7B5w sources changed: {hashes}")
    previous = json.loads(SOURCES["phase7b5v_summary"].read_text(encoding="utf-8"))
    decision = previous["decision"]
    if decision["phase7b5v_gate_passed"] is not False:
        raise RuntimeError("Phase 7B5w requires the retained Phase 7B5v failure")
    if decision["small_one_iteration_equivalence_passed"] is not False:
        raise RuntimeError("Phase 7B5w requires the retained one-map failure")
    return {
        "phase": "7B5w translation-invariant local-overlap remap gate",
        "protocol_version": 1,
        "classification": (
            "[A-preregistered] roundoff repair; [V] slice invariance and actual "
            "fixed-point equivalence; [O] full-depth block resource"
        ),
        "sources": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": hashes[name]}
            for name, path in SOURCES.items()
        },
        "retained_failure": previous["one_iteration_streaming_control"],
        "candidate": {
            "frequency_integral": (
                "direct ordered sum over only the source groups overlapping each "
                "shifted target interval"
            ),
            "global_frequency_edges_changed": False,
            "core_frequency_groups": 256,
            "posthoc_tolerance_change": False,
        },
        "gates": {
            "synthetic_slice_invariance_strictly_below": 2.0e-15,
            "actual_one_iteration_stream_vs_monolithic_strictly_below": 1.0e-12,
            "actual_fixed_point_tolerance": 1.0e-10,
            "actual_fixed_point_intensity_error_strictly_below": 1.0e-10,
            "actual_fixed_point_spectrum_l1_strictly_below": 1.0e-10,
            "actual_scalar_error_strictly_below": 1.0e-10,
            "new_monolithic_vs_phase7b5v_scalar_error_strictly_below": 5.0e-9,
            "worker_peak_rss_strictly_below_mib": 6144.0,
            "minimum_intensity_at_least": 0.0,
            "physical_group_count_exactly": 9632,
            "active_edge_hash_unchanged": True,
        },
        "authorization": {
            "translation_invariant_remap_gate_authorized": True,
            "full_depth_block_resource_probe_authorized_if_gate_passes": True,
            "full_orbit_authorized": False,
            "matter_feedback_authorized": False,
            "phase4_replacement_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT / "phase7b5w_preregistered_translation_invariant_remap.json",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {args.output}; pass --force")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(args.output, build_protocol())
    print(_sha256_file(args.output))


if __name__ == "__main__":
    main()
