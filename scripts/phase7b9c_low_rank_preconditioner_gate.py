"""Phase 7B9c：单真实割线的低秩非局域预条件器门。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import matplotlib
import numpy as np
from scipy.sparse.linalg import LinearOperator, gmres

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
    ground_state_material_trial_within_trust_region,
)
from eccentric_tde_observer.low_rank_secant_preconditioner import (
    LowRankInverseSecantPreconditioner,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)
from eccentric_tde_observer.source import PhysicalDomainError


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
EXPECTED_PROTOCOL_SHA256 = (
    "2b746715010a41f007d2c451543f1146605a3e4c8337a9272ceff52293943308"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(16 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _write_npz_atomic(path: Path, **arrays: np.ndarray) -> None:
    temporary = path.with_name(f"{path.stem}.tmp.npz")
    np.savez(temporary, **arrays)
    os.replace(temporary, path)


def _load_protocol(path: Path) -> dict[str, object]:
    if _sha256(path) != EXPECTED_PROTOCOL_SHA256:
        raise RuntimeError("frozen Phase 7B9c protocol changed")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    for source in protocol["sources"].values():
        if _sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"frozen Phase 7B9c source changed: {source['path']}")
    return protocol


def _half_rates(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path) as rates:
        photoionization = np.array(rates["half_photoionization_s1"], copy=True)
        recombination = np.array(rates["half_total_recombination_cm3_s"], copy=True)
        heating_key = (
            "half_atomic_rate_heating_erg_s_cm3"
            if "half_atomic_rate_heating_erg_s_cm3" in rates
            else "half_rate_material_heating_erg_s_cm3"
        )
        heating = np.array(rates[heating_key], copy=True)
    return photoionization, recombination, heating


def _response(
    density: np.ndarray,
    old_temperature: np.ndarray,
    old_hydrogen: np.ndarray,
    old_helium: np.ndarray,
    duration: float,
    rate_path: Path,
):
    photoionization, recombination, heating = _half_rates(rate_path)
    return frozen_radiation_material_response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        photoionization,
        recombination,
        heating,
    )


def _first_trust_relaxation(
    codec: GroundStateLogSimplexCodec,
    current: np.ndarray,
    direction: np.ndarray,
    configuration: dict[str, object],
) -> float:
    for relaxation in configuration["candidate_relaxations"]:
        try:
            accepted = ground_state_material_trial_within_trust_region(
                codec,
                current,
                current + float(relaxation) * direction,
                maximum_relative_temperature_change=float(
                    configuration["maximum_relative_temperature_change_per_trial"]
                ),
                maximum_absolute_material_energy_increment_fraction=float(
                    configuration[
                        "maximum_absolute_material_energy_increment_fraction_per_trial"
                    ]
                ),
                maximum_population_fraction_change=float(
                    configuration["maximum_population_fraction_change_per_trial"]
                ),
            )
        except PhysicalDomainError:
            accepted = False
        if accepted:
            return float(relaxation)
    raise RuntimeError("no preregistered trust-region relaxation was feasible")


def _manufactured_control(configuration: dict[str, object]):
    dimension = int(configuration["manufactured_dimension"])
    rank = int(configuration["manufactured_rank"])
    rng = np.random.default_rng(int(configuration["manufactured_random_seed"]))
    residual_secants, _ = np.linalg.qr(rng.normal(size=(dimension, rank)))
    correction = 0.12 * rng.normal(size=(dimension, rank))
    true_inverse = -np.eye(dimension) + correction @ residual_secants.T
    jacobian = np.linalg.inv(true_inverse)
    state_secants = true_inverse @ residual_secants
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        state_secants,
        residual_secants,
        base_inverse_scale=float(configuration["base_inverse_scale"]),
        maximum_gram_condition_number=float(
            configuration["maximum_residual_gram_condition_number"]
        ),
    )
    basis = np.eye(dimension)
    recovered_inverse = np.column_stack(
        [preconditioner.apply(basis[:, index]) for index in range(dimension)]
    )
    inverse_error = float(
        np.linalg.norm(recovered_inverse - true_inverse) / np.linalg.norm(true_inverse)
    )
    right_hand_side = rng.normal(size=dimension)
    unpreconditioned_history: list[float] = []
    _, unpreconditioned_info = gmres(
        jacobian,
        right_hand_side,
        rtol=1.0e-11,
        atol=0.0,
        restart=dimension,
        maxiter=dimension,
        callback=unpreconditioned_history.append,
        callback_type="pr_norm",
    )
    preconditioned_history: list[float] = []
    solution, preconditioned_info = gmres(
        LinearOperator((dimension, dimension), matvec=lambda value: jacobian @ value),
        right_hand_side,
        M=preconditioner.as_linear_operator(),
        rtol=1.0e-11,
        atol=0.0,
        restart=dimension,
        maxiter=dimension,
        callback=preconditioned_history.append,
        callback_type="pr_norm",
    )
    solve_residual = float(
        np.linalg.norm(jacobian @ solution - right_hand_side)
        / np.linalg.norm(right_hand_side)
    )
    if unpreconditioned_info != 0 or preconditioned_info != 0:
        raise ArithmeticError("manufactured GMRES did not converge")
    return {
        "inverse_error": inverse_error,
        "solve_residual": solve_residual,
        "unpreconditioned_history": np.asarray(unpreconditioned_history),
        "preconditioned_history": np.asarray(preconditioned_history),
    }


def _plot(
    path: Path,
    mass_centre: np.ndarray,
    residual_zero: np.ndarray,
    residual_one: np.ndarray,
    coupling: np.ndarray,
    picard_relaxation: float,
    low_rank_relaxation: float,
    manufactured: dict[str, object],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12.5, 8.3), constrained_layout=True)
    labels = ("Thermal", "H", "He II", "He III")
    for index, label in enumerate(labels):
        axes[0, 0].plot(
            mass_centre,
            residual_one[:, index] - residual_zero[:, index],
            label=label,
        )
    axes[0, 0].axhline(0.0, color="0.25", ls=":")
    axes[0, 0].set(
        xlabel="Mass fraction from surface",
        ylabel="Observed residual secant",
        title="(a) One actual directional-map secant",
    )
    axes[0, 0].legend(frameon=False, fontsize=8.5)
    image = axes[0, 1].imshow(
        coupling,
        origin="lower",
        aspect="auto",
        cmap="magma",
        extent=(mass_centre[0], mass_centre[-1], mass_centre[0], mass_centre[-1]),
    )
    axes[0, 1].set(
        xlabel="Input mass fraction",
        ylabel="Output mass fraction",
        title="(b) Dense rank-one cross-depth correction",
    )
    figure.colorbar(image, ax=axes[0, 1], label="4x4 block Frobenius norm")
    axes[1, 0].bar(
        (0, 1),
        (picard_relaxation, low_rank_relaxation),
        color=("#7896b2", "#b5654d"),
    )
    axes[1, 0].set(
        xticks=(0, 1),
        xticklabels=("Base -I\n(Picard direction)", "Rank-one inverse\n(direction only)"),
        ylabel="Largest preregistered trust relaxation",
        title="(c) Physical-domain geometry, not convergence",
    )
    unpreconditioned = np.asarray(manufactured["unpreconditioned_history"])
    preconditioned = np.asarray(manufactured["preconditioned_history"])
    axes[1, 1].semilogy(
        np.arange(1, unpreconditioned.size + 1),
        unpreconditioned,
        "o-",
        label="Unpreconditioned",
    )
    axes[1, 1].semilogy(
        np.arange(1, preconditioned.size + 1),
        preconditioned,
        "s-",
        label="Exact low-rank control",
    )
    axes[1, 1].set(
        xlabel="GMRES iteration",
        ylabel="Preconditioned residual norm",
        title="(d) Manufactured low-rank inverse control",
    )
    axes[1, 1].legend(frameon=False)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run(protocol_path: Path) -> dict[str, object]:
    protocol = _load_protocol(protocol_path)
    configuration = protocol["configuration"]
    gates = protocol["gates"]
    started = time.perf_counter()
    phase = int(configuration["phase_index"])
    with np.load(ROOT / protocol["sources"]["physical_old_time_level"]["path"]) as old:
        density = np.array(old["density_g_cm3"][phase], copy=True)
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
        duration = float(old["step_duration_s"][phase])
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)
    with np.load(ROOT / protocol["sources"]["current_material_state"]["path"]) as current:
        current_temperature = np.array(current["temperature_k"], copy=True)
        current_hydrogen = np.array(current["hydrogen_fraction"], copy=True)
        current_helium = np.array(current["helium_fraction"], copy=True)
    codec = GroundStateLogSimplexCodec(int(configuration["cell_count"]))
    state_zero = np.asarray(codec.encode(old_temperature, old_hydrogen, old_helium))
    state_one = np.asarray(
        codec.encode(current_temperature, current_hydrogen, current_helium)
    )
    response_zero = _response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        ROOT / protocol["sources"]["first_feedback"]["path"],
    )
    response_one = _response(
        density,
        old_temperature,
        old_hydrogen,
        old_helium,
        duration,
        ROOT / protocol["sources"]["current_feedback"]["path"],
    )
    image_zero = np.asarray(
        codec.encode(
            response_zero.temperature_k,
            response_zero.hydrogen_fraction,
            response_zero.helium_fraction,
        )
    )
    image_one = np.asarray(
        codec.encode(
            response_one.temperature_k,
            response_one.hydrogen_fraction,
            response_one.helium_fraction,
        )
    )
    residual_zero = image_zero - state_zero
    residual_one = image_one - state_one
    state_secant = state_one - state_zero
    residual_secant = residual_one - residual_zero
    preconditioner = LowRankInverseSecantPreconditioner.from_secants(
        state_secant[:, None],
        residual_secant[:, None],
        base_inverse_scale=float(configuration["base_inverse_scale"]),
        maximum_gram_condition_number=float(
            configuration["maximum_residual_gram_condition_number"]
        ),
    )
    recovered_secant = preconditioner.apply(residual_secant)
    secant_error = float(
        np.linalg.norm(recovered_secant - state_secant)
        / max(np.linalg.norm(recovered_secant), np.linalg.norm(state_secant))
    )
    picard_direction = residual_one
    low_rank_direction = -preconditioner.apply(residual_one)
    picard_relaxation = _first_trust_relaxation(
        codec, state_one, picard_direction, configuration
    )
    low_rank_relaxation = _first_trust_relaxation(
        codec, state_one, low_rank_direction, configuration
    )

    rejected_later_responses: dict[str, bool] = {}
    for label, source_name in (
        ("secant", "secant_feedback"),
        ("backtracked", "backtracked_feedback"),
    ):
        rejected = False
        try:
            _response(
                density,
                old_temperature,
                old_hydrogen,
                old_helium,
                duration,
                ROOT / protocol["sources"][source_name]["path"],
            )
        except PhysicalDomainError as error:
            rejected = "no positive gas heat" in str(error)
        rejected_later_responses[label] = rejected

    manufactured = _manufactured_control(configuration)
    encoded_basis = np.eye(codec.vector_size)
    correction_dense = np.column_stack(
        [
            preconditioner.apply(encoded_basis[:, index])
            - float(configuration["base_inverse_scale"])
            * encoded_basis[:, index]
            for index in range(codec.vector_size)
        ]
    )
    cell_coupling = np.linalg.norm(
        correction_dense.reshape(128, 4, 128, 4), axis=(1, 3)
    )
    wall_runtime = time.perf_counter() - started
    all_later_rejected = all(rejected_later_responses.values())
    decision = {
        "frozen_sources_passed": True,
        "actual_directional_secant_identity_passed": bool(
            secant_error
            < float(gates["actual_secant_identity_relative_residual_below"])
            and preconditioner.secant_count
            == int(gates["actual_secant_count_exactly"])
            and preconditioner.gram_condition_number
            < float(gates["actual_secant_gram_condition_number_below"])
        ),
        "later_physical_domain_rejections_preserved": all_later_rejected,
        "manufactured_low_rank_control_passed": bool(
            manufactured["inverse_error"]
            < float(gates["manufactured_maximum_inverse_error_below"])
            and len(manufactured["preconditioned_history"])
            <= int(gates["manufactured_preconditioned_gmres_iterations_at_most"])
            and len(manufactured["unpreconditioned_history"])
            > int(gates["manufactured_unpreconditioned_iterations_strictly_above"])
        ),
        "runtime_gate_passed": wall_runtime
        < float(gates["wall_runtime_strictly_below_s"]),
        "actual_secant_is_inner_converged": False,
        "preconditioner_used_as_residual_substitute": False,
        "new_full_frequency_residual_evaluated": False,
        "full_frequency_jv_evaluated": False,
        "accepted_as_dynamic_NLTE_solution": False,
        "full_orbit_authorized": False,
        "phase4_replacement_authorized": False,
        "uvot_authorized": False,
    }
    decision["phase7b9c_gate_passed"] = all(
        decision[name]
        for name in (
            "actual_directional_secant_identity_passed",
            "later_physical_domain_rejections_preserved",
            "manufactured_low_rank_control_passed",
            "runtime_gate_passed",
        )
    )
    decision["one_recoverable_inner_converged_base_residual_design_authorized"] = bool(
        decision["phase7b9c_gate_passed"]
    )
    artifact_path = OUTPUT / "phase7b9c_low_rank_preconditioner.npz"
    _write_npz_atomic(
        artifact_path,
        mass_fraction_centre=0.5 * (mass_edge[:-1] + mass_edge[1:]),
        state_zero=state_zero,
        state_one=state_one,
        residual_zero=residual_zero,
        residual_one=residual_one,
        state_secant=state_secant,
        residual_secant=residual_secant,
        low_rank_direction=low_rank_direction,
        cell_coupling=cell_coupling,
        manufactured_unpreconditioned_history=manufactured[
            "unpreconditioned_history"
        ],
        manufactured_preconditioned_history=manufactured["preconditioned_history"],
    )
    figure_path = OUTPUT / "phase7b9c_low_rank_preconditioner.png"
    _plot(
        figure_path,
        0.5 * (mass_edge[:-1] + mass_edge[1:]),
        residual_zero.reshape(-1, 4),
        residual_one.reshape(-1, 4),
        cell_coupling,
        picard_relaxation,
        low_rank_relaxation,
        manufactured,
    )
    report = {
        "phase": protocol["phase"],
        "classification": "[A-preregistered]+[V]+[O]",
        "protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "phase_index": phase,
        "encoded_unknown_count": codec.vector_size,
        "actual_observed_secant_count": preconditioner.secant_count,
        "actual_secant_gram_condition_number": preconditioner.gram_condition_number,
        "actual_secant_identity_relative_residual": secant_error,
        "actual_state_secant_l2_norm": float(np.linalg.norm(state_secant)),
        "actual_residual_secant_l2_norm": float(np.linalg.norm(residual_secant)),
        "actual_state_residual_secant_cosine": float(
            np.dot(state_secant, residual_secant)
            / (np.linalg.norm(state_secant) * np.linalg.norm(residual_secant))
        ),
        "current_directional_residual_l2_norm": float(np.linalg.norm(residual_one)),
        "base_picard_largest_trust_relaxation": picard_relaxation,
        "low_rank_largest_trust_relaxation": low_rank_relaxation,
        "low_rank_direction_vs_picard_cosine": float(
            np.dot(low_rank_direction, picard_direction)
            / (np.linalg.norm(low_rank_direction) * np.linalg.norm(picard_direction))
        ),
        "later_response_physical_rejections": rejected_later_responses,
        "manufactured_inverse_relative_error": manufactured["inverse_error"],
        "manufactured_solve_relative_residual": manufactured["solve_residual"],
        "manufactured_unpreconditioned_gmres_iterations": len(
            manufactured["unpreconditioned_history"]
        ),
        "manufactured_preconditioned_gmres_iterations": len(
            manufactured["preconditioned_history"]
        ),
        "wall_runtime_s": wall_runtime,
        "artifact_path": str(artifact_path.relative_to(ROOT)),
        "artifact_sha256": _sha256(artifact_path),
        "decision": decision,
        "figures": [figure_path.name],
    }
    _write_json_atomic(OUTPUT / "phase7b9c_low_rank_preconditioner_summary.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=OUTPUT / "phase7b9c_preregistered_low_rank_preconditioner.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.protocol), indent=2))


if __name__ == "__main__":
    main()
