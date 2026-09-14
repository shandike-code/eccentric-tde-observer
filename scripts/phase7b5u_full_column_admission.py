"""Phase 7B5u：执行完整动态柱的资源与特征线准入审计。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.mixed_frame_ale import (
    mixed_frame_frequency_stencil_from_active_edges,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S
from eccentric_tde_observer.radiative_transfer_1d import (
    gauss_legendre_split_mu_weights,
)

try:
    from scripts.phase7b4s_implicit_ale_radiation import (
        _load_material_reference,
        centred_full_column_trajectory,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b4s_implicit_ale_radiation import (  # type: ignore[no-redef]
        _load_material_reference,
        centred_full_column_trajectory,
    )


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "895225b50a7feccd5563dec5ef580947e90bca4f48c08d0e2eef9ed9e60d363c"
)
GIB = 1024**3


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


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    temporary = path.with_name(f"{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    digest = _sha256_file(path)
    if digest != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError(f"frozen Phase 7B5u protocol changed: {digest}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        source_path = ROOT / source["path"]
        if _sha256_file(source_path) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B5u source changed: {source_path}")
    return protocol


def _physical_memory_bytes() -> int:
    value = subprocess.run(
        ["sysctl", "-n", "hw.memsize"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    memory = int(value)
    if memory <= 0:
        raise RuntimeError("sysctl returned a non-positive physical memory size")
    return memory


def _identified_live_bytes(
    active_groups: int,
    collision_groups: int,
    outer_groups: int,
    angle_count: int,
    depth_count: int,
) -> tuple[int, list[dict[str, object]]]:
    shapes = (
        ("initial_active", active_groups, depth_count),
        ("outer_guard_template", outer_groups, depth_count),
        ("lab_extinction", active_groups, depth_count),
        ("current_active", active_groups, depth_count),
        ("outer_work", outer_groups, depth_count),
        ("comoving_angle_intensity", collision_groups, depth_count),
        ("lab_emissivity", active_groups, depth_count),
        ("updated_active", active_groups, depth_count),
        ("transport_face_intensity", active_groups, depth_count + 1),
    )
    rows = []
    total = 0
    for name, groups, depth in shapes:
        size = int(groups * angle_count * depth * np.dtype(np.float64).itemsize)
        total += size
        rows.append(
            {
                "array": name,
                "frequency_groups": groups,
                "angular_directions": angle_count,
                "depth_entries": depth,
                "bytes": size,
                "gib": size / GIB,
            }
        )
    return total, rows


def _plot(
    path: Path,
    phase: np.ndarray,
    maximum_face_beta: np.ndarray,
    reversal_fraction: np.ndarray,
    minimum_mu: float,
    physical_memory: int,
    identified_live: int,
    block_memory: list[tuple[int, int]],
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.3), constrained_layout=True)
    axes[0, 0].bar(
        ["Physical memory", "Monolithic\nidentified live set"],
        [physical_memory / GIB, identified_live / GIB],
        color=["C0", "C3"],
    )
    axes[0, 0].axhline(0.75 * physical_memory / GIB, color="0.25", ls="--")
    axes[0, 0].set_ylabel("Memory (GiB)")
    axes[0, 0].set_title("(a) Current solver memory admission")

    axes[0, 1].plot(phase, maximum_face_beta, color="C1", lw=1.0)
    axes[0, 1].axhline(minimum_mu, color="0.25", ls="--", label="Smallest |mu|")
    axes[0, 1].set_xlabel("Orbital phase")
    axes[0, 1].set_ylabel("Maximum |mesh velocity| / c")
    axes[0, 1].set_title("(b) Grazing-ray reversal condition")
    axes[0, 1].legend(frameon=False)

    axes[1, 0].plot(phase, reversal_fraction, color="C4", lw=1.0)
    axes[1, 0].set_xlabel("Orbital phase")
    axes[1, 0].set_ylabel("Reversing angular-weight fraction")
    axes[1, 0].set_title("(c) Phases requiring turning-ray treatment")

    block_group = np.array([item[0] for item in block_memory])
    block_gib = np.array([item[1] for item in block_memory]) / GIB
    axes[1, 1].plot(block_group, block_gib, marker="o", color="C2")
    axes[1, 1].axhline(6.0, color="0.25", ls="--", label="6 GiB probe cap")
    axes[1, 1].set_xscale("log", base=2)
    axes[1, 1].set_yscale("log", base=2)
    axes[1, 1].set_xlabel("Core frequency groups per block")
    axes[1, 1].set_ylabel("Identified live set (GiB)")
    axes[1, 1].set_title("(d) Bounded-memory block sizing")
    axes[1, 1].legend(frameon=False)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run(protocol_path: Path, output_dir: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    material_path = ROOT / protocol["sources"]["phase7b4r_material"]["path"]
    master_path = ROOT / protocol["sources"]["phase7b5p_master_input"]["path"]
    material = _load_material_reference(material_path)
    full = centred_full_column_trajectory(material)
    accepted = protocol["accepted_single_cell_configuration"]
    phase_count = int(material["orbital_phase"].size)
    material_depth = int(full["density_g_cm3"].shape[1])
    radiation_depth = material_depth * int(accepted["radiation_subcells_per_parent"])
    with np.load(master_path) as master:
        active_edge = np.array(master["active_edge_hz"], copy=True)
        maximum_beta = float(master["maximum_beta"])
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        active_edge, maximum_beta
    )
    angle_count = int(accepted["angular_direction_count"])
    mu, angular_weight = gauss_legendre_split_mu_weights(angle_count, 0.0)

    old_edge = full["edges_cm"]
    new_edge = np.roll(old_edge, -1, axis=0)
    duration = material["step_duration_s"]
    face_beta = (new_edge - old_edge) / (
        duration[:, None] * LIGHT_SPEED_CM_S
    )
    maximum_face_beta = np.max(np.abs(face_beta), axis=1)
    phase_minimum = np.min(face_beta, axis=1)
    phase_maximum = np.max(face_beta, axis=1)
    reversing = (mu[:, None] > phase_minimum[None, :]) & (
        mu[:, None] < phase_maximum[None, :]
    )
    reversal_count = np.sum(reversing, axis=0)
    reversal_fraction = 0.5 * np.sum(
        angular_weight[:, None] * reversing, axis=0
    )
    rows = [
        {
            "phase_index": index,
            "orbital_phase": float(material["orbital_phase"][index]),
            "step_duration_s": float(duration[index]),
            "minimum_face_velocity_beta": float(phase_minimum[index]),
            "maximum_face_velocity_beta": float(phase_maximum[index]),
            "maximum_absolute_face_velocity_beta": float(maximum_face_beta[index]),
            "reversing_direction_count": int(reversal_count[index]),
            "reversing_angular_weight_fraction": float(reversal_fraction[index]),
        }
        for index in range(phase_count)
    ]

    physical_memory = _physical_memory_bytes()
    identified_live, memory_rows = _identified_live_bytes(
        stencil.physical_group_count,
        stencil.comoving_collision_group_count,
        stencil.outer_lab_group_count,
        angle_count,
        radiation_depth,
    )
    probe_sizes = (128, 256, 512, 1024, 2048, 4096, 9632)
    block_memory = []
    for group_count in probe_sizes:
        # 中文：块内额外四组近似两层 Doppler 守护，仅用于资源预估。
        block_stencil_groups = min(stencil.physical_group_count, group_count)
        block_collision = block_stencil_groups + 2
        block_outer = block_stencil_groups + 4
        size, _ = _identified_live_bytes(
            block_stencil_groups,
            block_collision,
            block_outer,
            angle_count,
            radiation_depth,
        )
        block_memory.append((group_count, size))

    half = full["density_g_cm3"].shape[1] // 2
    half_scale = float(np.max(full["half_thickness_cm"]))
    mirror_residual = max(
        float(np.max(np.abs(old_edge[:, half])) / half_scale),
        float(
            np.max(
                np.abs(
                    full["density_g_cm3"]
                    - full["density_g_cm3"][:, ::-1]
                )
            )
            / np.max(full["density_g_cm3"])
        ),
    )
    memory_admitted = identified_live < (
        protocol["memory_accounting"][
            "monolithic_admission_fraction_of_physical_memory"
        ]
        * physical_memory
    )
    reversing_phase_count = int(np.count_nonzero(reversal_count))
    pure_step_admitted = reversing_phase_count == 0
    integrity = {
        "phase_count_exact": phase_count
        == protocol["full_column_shape"]["orbital_phase_count"],
        "material_depth_exact": material_depth
        == protocol["full_column_shape"]["material_cell_count"],
        "radiation_depth_exact": radiation_depth
        == protocol["full_column_shape"]["radiation_depth_cell_count"],
        "all_durations_positive": bool(
            np.all(np.isfinite(duration)) and np.all(duration > 0.0)
        ),
        "mirror_residual_passed": mirror_residual
        <= protocol["gates"][
            "centred_full_column_mirror_residual_at_most"
        ],
    }
    summary = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_path": str(protocol_path),
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "accepted_single_cell_configuration": accepted,
        "full_column": {
            "orbital_phase_count": phase_count,
            "material_cell_count": material_depth,
            "radiation_depth_cell_count": radiation_depth,
            "physical_frequency_groups": stencil.physical_group_count,
            "collision_frequency_groups": stencil.comoving_collision_group_count,
            "outer_frequency_groups": stencil.outer_lab_group_count,
            "angular_direction_count": angle_count,
            "radiation_unknown_count": int(
                stencil.physical_group_count * angle_count * radiation_depth
            ),
            "single_active_intensity_array_bytes": int(
                stencil.physical_group_count
                * angle_count
                * radiation_depth
                * np.dtype(np.float64).itemsize
            ),
        },
        "memory": {
            "physical_memory_bytes": physical_memory,
            "identified_live_array_bytes": identified_live,
            "identified_live_over_physical_memory": identified_live
            / physical_memory,
            "memory_rows": memory_rows,
            "excluded_from_lower_bound": protocol["memory_accounting"][
                "excluded_from_lower_bound"
            ],
            "monolithic_memory_admitted": memory_admitted,
            "block_probe": [
                {
                    "core_frequency_groups": groups,
                    "identified_live_array_bytes": size,
                    "identified_live_array_gib": size / GIB,
                }
                for groups, size in block_memory
            ],
        },
        "characteristics": {
            "angular_split_mu": 0.0,
            "minimum_absolute_quadrature_mu": float(np.min(np.abs(mu))),
            "maximum_absolute_mesh_face_beta": float(np.max(maximum_face_beta)),
            "minimum_quadrature_to_face_beta_distance": float(
                np.min(np.abs(mu[:, None, None] - face_beta[None, :, :]))
            ),
            "reversing_phase_count": reversing_phase_count,
            "reversing_phase_fraction": reversing_phase_count / phase_count,
            "maximum_reversing_direction_count": int(np.max(reversal_count)),
            "maximum_reversing_angular_weight_fraction": float(
                np.max(reversal_fraction)
            ),
            "ever_reversing_direction_cosines": [
                float(value) for value in mu[np.any(reversing, axis=1)]
            ],
            "pure_step_characteristics_admitted": pure_step_admitted,
        },
        "integrity": integrity,
        "decision": {
            "audit_integrity_passed": bool(all(integrity.values())),
            "monolithic_full_column_admitted": memory_admitted,
            "pure_step_full_column_admitted": pure_step_admitted,
            "requires_frequency_streaming": not memory_admitted,
            "requires_turning_ray_treatment": not pure_step_admitted,
            "production_full_column_admitted": bool(
                memory_admitted and pure_step_admitted and all(integrity.values())
            ),
            "next_phase": (
                "bounded-memory full-grid frequency streaming plus a separately "
                "verified conservative turning-ray treatment"
            ),
        },
    }
    _write_csv(output_dir / "phase7b5u_characteristic_phases.csv", rows)
    _write_csv(output_dir / "phase7b5u_memory_arrays.csv", memory_rows)
    _plot(
        output_dir / "phase7b5u_full_column_admission.png",
        material["orbital_phase"],
        maximum_face_beta,
        reversal_fraction,
        float(np.min(np.abs(mu))),
        physical_memory,
        identified_live,
        block_memory,
    )
    _write_json_atomic(output_dir / "phase7b5u_full_column_admission.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b5u_preregistered_full_column_admission.json",
    )
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    summary_path = args.output_dir / "phase7b5u_full_column_admission.json"
    if summary_path.exists() and not args.force:
        raise FileExistsError(f"refusing to overwrite {summary_path}; pass --force")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = run(args.protocol, args.output_dir)
    print(json.dumps(summary["decision"], indent=2), flush=True)


if __name__ == "__main__":
    main()
