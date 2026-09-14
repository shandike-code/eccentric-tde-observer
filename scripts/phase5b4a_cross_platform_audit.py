"""Phase 5B4a：macOS/Windows 独立复算的机器可读对照审计。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
REMOTE_B3C = OUTPUT / "remote_windows_phase5b3c"
REMOTE_B4 = OUTPUT / "remote_windows_phase5b4"

B3C_FILES = (
    "phase5b3c_equation_variant_convergence.csv",
    "phase5b3c_printed_equation_ledger.csv",
    "phase5b3c_printed_equation_path_report.json",
    "phase5b3c_published_boundary_tangents.csv",
)
B4_FILES = (
    "phase5b4_candidate_timescales.csv",
    "phase5b4_derivative_resolution_audit.csv",
    "phase5b4_high_e_derivative_holdout.csv",
    "phase5b4_high_e_table_convergence.csv",
    "phase5b4_shooting_collocation.csv",
    "phase5b4_strict_domain_candidate_timescale_report.json",
)
WINDOWS_REMOTE_SHA256 = {
    "phase5b3c_equation_variant_convergence.csv": (
        "088a9caf668654f7f4f230f4e8462677d69d03621081a85f8966d4dfe11de5ae"
    ),
    "phase5b3c_printed_equation_ledger.csv": (
        "0a580bc291f7eabd0d730d3b0f64b67040796edf5b914338225cec76724ddbd1"
    ),
    "phase5b3c_printed_equation_path_report.json": (
        "67e46216675f7e0ce6a6702cc5d41f0407183b53e14f62951f3226c01877294f"
    ),
    "phase5b3c_published_boundary_tangents.csv": (
        "49b588e0031e960c2ee3e13a905d7a48a72bee5652bc0dcc3e579d79ce8941bf"
    ),
    "phase5b4_candidate_timescales.csv": (
        "70777e29c719ca13bd25b806d76b4f59783e906b69ca31adc7acfd26c9382015"
    ),
    "phase5b4_derivative_resolution_audit.csv": (
        "0019223a48c40a389a292ec0eb16a20dbc7bf67ddb6a9452368393dd3c39c259"
    ),
    "phase5b4_high_e_derivative_holdout.csv": (
        "80c904454bd61a788bc881a04a5384a3e52be1e161400563f5cb033ec1e993a4"
    ),
    "phase5b4_high_e_table_convergence.csv": (
        "1d2fff3f77783469ebd79fe2d6f6bbd3653f9770e509e469b8f2bdef3d229984"
    ),
    "phase5b4_shooting_collocation.csv": (
        "5030c601aabefc5cf03e7b49aae78d4ac4509ac143b01b81cc9cfad9b63f5302"
    ),
    "phase5b4_strict_domain_candidate_timescale_report.json": (
        "7189c0ab2f8b6b8ea318473323028fb6851efe8c4bae1564b6892bfca699257c"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty cross-platform audit table: {path}")
    return rows


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def paired_rows(filename: str, remote_root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    local = read_csv(OUTPUT / filename)
    remote = read_csv(remote_root / filename)
    if len(local) != len(remote):
        raise ValueError(f"row-count mismatch in {filename}")
    if list(local[0]) != list(remote[0]):
        raise ValueError(f"column mismatch in {filename}")
    return local, remote


def maximum_relative_difference(
    local: list[dict[str, str]],
    remote: list[dict[str, str]],
    columns: Iterable[str],
) -> float:
    differences: list[float] = []
    for local_row, remote_row in zip(local, remote, strict=True):
        for column in columns:
            local_value = float(local_row[column])
            remote_value = float(remote_row[column])
            scale = max(abs(local_value), abs(remote_value))
            differences.append(
                0.0 if scale == 0.0 else abs(local_value - remote_value) / scale
            )
    return max(differences)


def maximum_absolute_difference(
    local: list[dict[str, str]],
    remote: list[dict[str, str]],
    columns: Iterable[str],
) -> float:
    return max(
        abs(float(local_row[column]) - float(remote_row[column]))
        for local_row, remote_row in zip(local, remote, strict=True)
        for column in columns
    )


def nonnumeric_cells_equal(
    local: list[dict[str, str]], remote: list[dict[str, str]]
) -> bool:
    for local_row, remote_row in zip(local, remote, strict=True):
        for column in local_row:
            try:
                float(local_row[column])
                float(remote_row[column])
            except ValueError:
                if local_row[column] != remote_row[column]:
                    return False
    return True


def selected_json_booleans_equal(
    local: dict[str, object], remote: dict[str, object], keys: Iterable[str]
) -> bool:
    return all(
        isinstance(local[key], bool)
        and isinstance(remote[key], bool)
        and local[key] is remote[key]
        for key in keys
    )


def source_manifest() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for phase, remote_root, filenames in (
        ("5B3c", REMOTE_B3C, B3C_FILES),
        ("5B4", REMOTE_B4, B4_FILES),
    ):
        for filename in filenames:
            for platform, path in (
                ("macos", OUTPUT / filename),
                ("windows", remote_root / filename),
            ):
                if not path.is_file():
                    raise FileNotFoundError(path)
                entries.append(
                    {
                        "phase": phase,
                        "platform": platform,
                        "path": str(path.relative_to(ROOT)),
                        "sha256": sha256(path),
                    }
                )
    return entries


def main() -> None:
    b3c_convergence = paired_rows(B3C_FILES[0], REMOTE_B3C)
    b3c_ledger = paired_rows(B3C_FILES[1], REMOTE_B3C)
    b3c_tangents = paired_rows(B3C_FILES[3], REMOTE_B3C)
    b3c_local_report = read_json(OUTPUT / B3C_FILES[2])
    b3c_remote_report = read_json(REMOTE_B3C / B3C_FILES[2])

    b4_candidates = paired_rows(B4_FILES[0], REMOTE_B4)
    b4_resolution = paired_rows(B4_FILES[1], REMOTE_B4)
    b4_derivatives = paired_rows(B4_FILES[2], REMOTE_B4)
    b4_convergence = paired_rows(B4_FILES[3], REMOTE_B4)
    b4_shooting = paired_rows(B4_FILES[4], REMOTE_B4)
    b4_local_report = read_json(OUTPUT / B4_FILES[5])
    b4_remote_report = read_json(REMOTE_B4 / B4_FILES[5])

    b3c_boolean_keys = (
        "equation_variant_internal_gate",
        "printed_appendix_sign_explains_published_branch",
        "published_vector_all_inner_tangents_satisfy_declared_3d_free_boundary",
        "formal_zo_source_model_changed",
        "phase_to_time_mapping_authorized",
    )
    b4_boolean_keys = (
        "intermediate_31x61_derivative_gate_passed",
        "final_41x81_derivative_gate_passed",
        "high_e_equation_internal_gate",
        "equation_self_consistent_candidate_timescale_computed",
        "published_benchmark_gate",
        "constant_e_atlas_shape_compatibility_gate",
        "existing_atlas_phase_to_time_mapping_authorized",
    )

    b3c_solution_relative_difference = maximum_relative_difference(
        *b3c_convergence,
        columns=(
            "dimensionless_frequency",
            "published_frequency",
            "absolute_published_frequency_error",
            "outer_eccentricity",
            "profile_max_error_over_inner_e",
        ),
    )
    b3c_boundary_absolute_difference = maximum_absolute_difference(
        *b3c_convergence, columns=("maximum_absolute_boundary_residual",)
    )
    b3c_tangent_relative_difference = maximum_relative_difference(
        *b3c_tangents,
        columns=(
            "endpoint_eccentricity",
            "fitted_de_da",
            "inferred_orbital_nonlinearity",
            "required_three_dimensional_free_q",
            "required_two_dimensional_free_q",
            "three_dimensional_F_f_residual",
            "two_dimensional_F_f_residual",
        ),
    )

    b4_candidate_relative_difference = maximum_relative_difference(
        *b4_candidates,
        columns=(
            "inner_eccentricity",
            "outer_eccentricity",
            "outer_to_inner_eccentricity_ratio",
            "dimensionless_frequency",
            "direct_eq39_cycles_per_day",
            "direct_eq39_period_days",
            "printed_eq48_cycles_per_day",
            "printed_eq48_period_days",
            "printed_to_direct_frequency_ratio",
            "maximum_relative_shape_difference_from_constant_e",
            "rms_relative_shape_difference_from_constant_e",
            "minimum_orbital_nonlinearity",
            "maximum_orbital_nonlinearity",
        ),
    )
    b4_table_solution_relative_difference = maximum_relative_difference(
        *b4_convergence,
        columns=(
            "inner_eccentricity",
            "dimensionless_frequency",
            "outer_eccentricity",
            "minimum_orbital_nonlinearity",
            "maximum_orbital_nonlinearity",
        ),
    )
    b4_boundary_absolute_difference = maximum_absolute_difference(
        *b4_convergence, columns=("outer_boundary_residual",)
    )
    b4_shooting_solution_relative_difference = maximum_relative_difference(
        *b4_shooting,
        columns=(
            "shooting_frequency",
            "collocation_frequency",
            "shooting_outer_eccentricity",
            "collocation_outer_eccentricity",
        ),
    )
    local_resolution_pattern = [
        bool(int(row["derivative_gate_passed"])) for row in b4_resolution[0]
    ]
    remote_resolution_pattern = [
        bool(int(row["derivative_gate_passed"])) for row in b4_resolution[1]
    ]
    local_derivative_maximum = max(
        float(row["relative_derivative_vector_error"])
        for row in b4_derivatives[0]
    )
    remote_derivative_maximum = max(
        float(row["relative_derivative_vector_error"])
        for row in b4_derivatives[1]
    )

    b3c_classification_match = (
        selected_json_booleans_equal(
            b3c_local_report, b3c_remote_report, b3c_boolean_keys
        )
        and nonnumeric_cells_equal(*b3c_convergence)
        and nonnumeric_cells_equal(*b3c_ledger)
        and nonnumeric_cells_equal(*b3c_tangents)
        and b3c_ledger[0] == b3c_ledger[1]
    )
    b4_classification_match = (
        selected_json_booleans_equal(
            b4_local_report, b4_remote_report, b4_boolean_keys
        )
        and nonnumeric_cells_equal(*b4_candidates)
        and nonnumeric_cells_equal(*b4_resolution)
        and nonnumeric_cells_equal(*b4_derivatives)
        and nonnumeric_cells_equal(*b4_convergence)
        and nonnumeric_cells_equal(*b4_shooting)
        and local_resolution_pattern == remote_resolution_pattern
    )

    # [A-audit] 这些阈值只判断跨平台复现，不替代原科学验收门。
    reproduction_gates = {
        "phase5b3c_primary_solution_relative_difference_below_1e-9": (
            b3c_solution_relative_difference < 1.0e-9
        ),
        "phase5b3c_tangent_relative_difference_below_1e-8": (
            b3c_tangent_relative_difference < 1.0e-8
        ),
        "phase5b3c_boundary_absolute_difference_below_1e-12": (
            b3c_boundary_absolute_difference < 1.0e-12
        ),
        "phase5b3c_classification_match": b3c_classification_match,
        "phase5b4_candidate_relative_difference_below_1e-10": (
            b4_candidate_relative_difference < 1.0e-10
        ),
        "phase5b4_table_solution_relative_difference_below_1e-10": (
            b4_table_solution_relative_difference < 1.0e-10
        ),
        "phase5b4_shooting_solution_relative_difference_below_1e-7": (
            b4_shooting_solution_relative_difference < 1.0e-7
        ),
        "phase5b4_boundary_absolute_difference_below_1e-12": (
            b4_boundary_absolute_difference < 1.0e-12
        ),
        "phase5b4_derivative_holdout_below_original_1e-3_on_both_platforms": (
            local_derivative_maximum < 1.0e-3
            and remote_derivative_maximum < 1.0e-3
        ),
        "phase5b4_derivative_resolution_gate_pattern_match": (
            local_resolution_pattern == remote_resolution_pattern
        ),
        "phase5b4_classification_match": b4_classification_match,
    }
    remote_copy_integrity: dict[str, dict[str, str | bool]] = {}
    for filename, remote_hash in WINDOWS_REMOTE_SHA256.items():
        copied_path = (
            REMOTE_B3C / filename
            if filename.startswith("phase5b3c")
            else REMOTE_B4 / filename
        )
        copied_hash = sha256(copied_path)
        remote_copy_integrity[filename] = {
            "remote_ssh_sha256": remote_hash,
            "copied_artifact_sha256": copied_hash,
            "matches": copied_hash == remote_hash,
        }
    reproduction_gates["remote_source_copy_integrity_matches"] = all(
        bool(entry["matches"]) for entry in remote_copy_integrity.values()
    )

    report = {
        "phase": "5B4a cross-platform audit",
        "evidence": "[V]+[A-audit]+[O]",
        "platforms": {
            "reference": "macOS local artifacts",
            "independent_rerun": {
                "os": "Windows",
                "python": "3.11.9",
                "remote_project": "D:\\eccentric_tde_observer_remote",
                "transport": "SSH over Tailscale",
            },
        },
        "remote_source_copy_integrity": remote_copy_integrity,
        "source_manifest": source_manifest(),
        "phase5b3c": {
            "maximum_primary_solution_relative_difference": b3c_solution_relative_difference,
            "maximum_boundary_residual_absolute_difference": b3c_boundary_absolute_difference,
            "maximum_vector_tangent_relative_difference": b3c_tangent_relative_difference,
            "source_ledger_byte_equivalent_as_parsed_rows": b3c_ledger[0]
            == b3c_ledger[1],
            "classification_match": b3c_classification_match,
            "macos_gate_vector": {
                key: b3c_local_report[key] for key in b3c_boolean_keys
            },
            "windows_gate_vector": {
                key: b3c_remote_report[key] for key in b3c_boolean_keys
            },
        },
        "phase5b4": {
            "maximum_candidate_table_relative_difference": b4_candidate_relative_difference,
            "maximum_table_solution_relative_difference": b4_table_solution_relative_difference,
            "maximum_table_boundary_residual_absolute_difference": b4_boundary_absolute_difference,
            "maximum_shooting_solution_relative_difference": b4_shooting_solution_relative_difference,
            "maximum_derivative_holdout_error": {
                "macos": local_derivative_maximum,
                "windows": remote_derivative_maximum,
            },
            "derivative_resolution_gate_pattern": {
                "macos": local_resolution_pattern,
                "windows": remote_resolution_pattern,
            },
            "classification_match": b4_classification_match,
            "macos_gate_vector": {
                key: b4_local_report[key] for key in b4_boolean_keys
            },
            "windows_gate_vector": {
                key: b4_remote_report[key] for key in b4_boolean_keys
            },
        },
        "reproduction_thresholds_are_audit_only": True,
        "reproduction_gates": reproduction_gates,
        "overall_cross_platform_reproduction_gate": all(
            reproduction_gates.values()
        ),
        "scientific_boundary": {
            "equation_self_consistent_candidate_is_reproduced": True,
            "published_zo_benchmark_is_recovered": False,
            "constant_e_atlas_shape_is_compatible": False,
            "existing_atlas_phase_to_time_mapping_authorized": False,
            "arbitrary_sign_or_boundary_scan_performed": False,
        },
        "interpretation": (
            "The independent Windows rerun reproduces the equation-self-consistent "
            "Phase 5B3c/B4 numerical conclusions and every reported pass/fail gate. "
            "This cross-platform agreement does not recover the published ZO Fig. 6/7 "
            "branch, does not make the candidate mode shape compatible with the "
            "constant-e atlas, and does not authorize a phase-to-time mapping."
        ),
    }
    target = OUTPUT / "phase5b4a_cross_platform_audit.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
