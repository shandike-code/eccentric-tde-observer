"""Quantify the numerical noise floor of the frozen-radiation material response.

Read-only. Answers the question the acceptance gates never evaluated: how much of
the material residual vector is solver noise rather than signal? Three
independent probes are used, none of which changes the physics, the declared dt,
the energy definition, or any acceptance gate:

1. internal iteration count of the population solve (production 96 vs 160);
2. a one-ulp perturbation of the frozen heating rate (emulating the
   cross-platform last-bit divergence already measured);
3. the independent ledger implementation of the same population update.

The output is compared against the same-scale candidate-vs-baseline differences
measured by `operations/replay_equation_baseline.py`, so the ratio
"noise / signal" is explicit instead of implied.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "hpc"), str(ROOT / "src"), str(ROOT / "scripts")]
import pipeline
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from operations.conservative_residual_diagnostic import equation_residual, norms
from operations.prepare_encoded_backtrack import load_arrays
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)
from eccentric_tde_observer.radiation_matter_feedback import (
    frozen_radiation_material_response,
)

# 同尺度比较中的候选减基态 L2 差值（71819 之前的 71918 结果），用于给出信噪比。
REFERENCE_CANDIDATE_MINUS_BASELINE_L2 = (22.318397, 22.405869, 22.408762, 43.706065)
# 已在 71916 实测的跨平台重放差（Mac 逐位、Linux 因 libm/BLAS 末位分叉）。
MEASURED_CROSS_PLATFORM_L2_DIFFERENCE = 2.4464231734195865e-11
MEASURED_CROSS_PLATFORM_MAXIMUM_DIFFERENCE = 7.776890242894297e-12


def solve(codec, encoded, density, old_temperature, old_hydrogen, old_helium, dt,
          feedback, *, iterations=96, heating_shift_ulp=0):
    """One frozen-radiation response and its encoded residual vector."""
    heating = np.asarray(feedback["half_atomic_rate_heating_erg_s_cm3"], dtype=np.float64)
    if heating_shift_ulp:
        for _ in range(heating_shift_ulp):
            heating = np.nextafter(heating, np.inf)
    solved = frozen_radiation_material_response(
        density, old_temperature, old_hydrogen, old_helium, dt,
        feedback["half_photoionization_s1"],
        feedback["half_total_recombination_cm3_s"],
        heating, bisection_iterations=iterations,
    )
    vector = np.asarray(codec.encode(solved.temperature_k, solved.hydrogen_fraction,
                                     solved.helium_fraction)) - encoded
    return vector, solved


def codec_identity_report(codec, encoded, trial) -> dict[str, object]:
    """Verify that the trial's physical arrays are the decoded encoded vector.

    The encoded vector is the authoritative object: `encode` maps the hydrogen
    simplex through `log(h+/(1-h+))`, and for the extreme ionization reached in
    this column (log-ratio ~19, so `1-h+ ~ 5e-9`) the subtraction
    `1 - hydrogen_ionized` loses about eight digits. The encode direction can
    therefore only round-trip to ~1e-8 and must not be used as an identity gate;
    the decode direction is exact and is what the migration guarantees.
    """
    decoded = codec.decode(encoded)
    decoded_difference = max(
        float(np.max(np.abs(np.asarray(getattr(decoded, name)) - np.asarray(trial[name]))))
        for name in ("temperature_k", "hydrogen_fraction", "helium_fraction"))
    reencoded = np.asarray(codec.encode(
        trial["temperature_k"], trial["hydrogen_fraction"], trial["helium_fraction"]))
    encoded_difference = reencoded - np.asarray(encoded, dtype=np.float64)
    per_component = [float(np.max(np.abs(encoded_difference.reshape(-1, 4)[:, index])))
                     for index in range(4)]
    return {
        "decode_versus_stored_maximum_absolute_difference": decoded_difference,
        "encode_roundtrip_maximum_absolute_difference": float(np.max(np.abs(encoded_difference))),
        "encode_roundtrip_per_component": per_component,
        "decode_identity_passed": decoded_difference <= 1.0e-15,
        "note": ("decode 方向是身份判据；encode 方向的 ~1e-8 来自 log-ratio 巨大时 "
                 "1-h+ 的相消，属已知表示误差，不是文件不一致"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="new diagnostics directory under outputs/hpc")
    parser.add_argument("--source-run", required=True, help="stopped run holding feedback rounds")
    parser.add_argument("--round", type=int, default=None,
                        help="round number to probe; default is the last recorded round")
    parser.add_argument("--reference-l2", type=float, default=None,
                        help="candidate-vs-baseline L2 difference to compare against")
    args = parser.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run)
    source = pipeline.safe_path(ROOT, args.source_run)
    if not out.is_relative_to(ROOT / "outputs/hpc") or out == source:
        raise ValueError("output must be a separate HPC directory")
    out.mkdir(parents=True, exist_ok=False)
    pipeline.write_json(out / "status.json", {"status": "running"})
    pipeline.write_json(out / "declaration.json", {
        "arguments": vars(args),
        "sources": [pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix(".sbatch"))],
        "scope": "read-only numerical noise floor; no new map, no acceptance, no gate change",
    })
    try:
        state = pipeline.read(source / "state.json")
        if state["status"] not in ("diagnostic_round_complete", "budget_exhausted") \
                or state.get("active_map") or state.get("pending_feedback"):
            raise RuntimeError("source run is not stopped and settled")
        if pipeline.sha256(source / "config.json") != state["config_sha256"]:
            raise RuntimeError("source config changed")
        config = pipeline.read(source / "config.json")
        if pipeline.verify_claims(ROOT, config["sources"], hash_files=True):
            raise RuntimeError("source frozen dependencies changed")
        rounds = state.get("diagnostic", {}).get("rounds", [])
        if not rounds:
            raise RuntimeError("source run has no completed feedback round to probe")
        if args.round is None:
            chosen = rounds[-1]
        else:
            matches = [r for r in rounds if r["round"] == args.round]
            if not matches:
                raise RuntimeError(f"round {args.round} is not recorded; available: "
                                   f"{[r['round'] for r in rounds]}")
            chosen = matches[0]
        folder = (ROOT / chosen["ledger"]).parent
        summary = pipeline.read(folder / "feedback_summary.json")
        if pipeline.sha256(folder / "feedback_protocol.json") != chosen["protocol_sha256"] \
                or summary["protocol_sha256"] != chosen["protocol_sha256"]:
            raise RuntimeError("round protocol lineage mismatch")
        trial_path = source / "trial_material.npz"
        trial = load_arrays(trial_path)
        old_path = ROOT / OLD_TIME_LEVEL
        old = load_arrays(old_path)
        phase = int(trial["phase_index"])
        dt = float(trial["step_duration_s"])
        density = np.asarray(trial["density_g_cm3"], dtype=np.float64)
        if dt != float(old["step_duration_s"][phase]) or not np.array_equal(density, old["density_g_cm3"][phase]):
            raise RuntimeError("physical old time level, dt or density changed")
        encoded = np.asarray(trial["encoded_state"], dtype=np.float64)
        codec = GroundStateLogSimplexCodec(len(density))
        identity = codec_identity_report(codec, encoded, trial)
        if not identity["decode_identity_passed"]:
            raise RuntimeError(
                "trial physical arrays are not the decode of encoded_state: "
                f"{identity['decode_versus_stored_maximum_absolute_difference']}")
        temperature = old["temperature_k"][phase]
        hydrogen = old["hydrogen_fraction"][phase]
        helium = old["helium_fraction"][phase]
        masses = old["cell_mass_g_cm2"]
        probes: dict[str, object] = {"round": chosen["round"], "endpoints": {}}
        input_claims = [pipeline.claim(source / "state.json"), pipeline.claim(trial_path),
                        pipeline.claim(old_path), pipeline.claim(folder / "feedback_summary.json"),
                        pipeline.claim(folder / "feedback_protocol.json")]
        for label in ("previous", "final"):
            claim = summary[f"{label}_feedback"]
            path = pipeline.safe_path(ROOT, claim["feedback_artifact_path"])
            if pipeline.sha256(path) != claim["feedback_artifact_sha256"]:
                raise RuntimeError(f"{label} feedback bytes changed")
            input_claims.append(pipeline.claim(path))
            feedback = load_arrays(path)
            production, production_response = solve(
                codec, encoded, density, temperature, hydrogen, helium, dt, feedback)
            tighter, _ = solve(codec, encoded, density, temperature, hydrogen, helium,
                               dt, feedback, iterations=160)
            perturbed, _ = solve(codec, encoded, density, temperature, hydrogen, helium,
                                 dt, feedback, heating_shift_ulp=1)
            led = ledger(feedback, density, dt, temperature, hydrogen, helium)
            # equation_residual 返回 (单元, 4)；统一压平到与 codec 编码向量相同的布局。
            ledger_vector = equation_residual(
                codec, encoded, led["total_old"], led["gas_old"],
                led["radiative_energy"], led["new_h"], led["new_he"]).reshape(-1)
            # 同定义对照：能量项与尺度取账本那份，布居换成生产实现的输出。
            # 直接把账本残差与旧 encoded 残差相减是无意义的，两者归一化不同。
            production_same_definition = equation_residual(
                codec, encoded, led["total_old"], led["gas_old"], led["radiative_energy"],
                production_response.hydrogen_fraction,
                production_response.helium_fraction).reshape(-1)
            ledger_populations = {
                "hydrogen_maximum_absolute_difference": float(np.max(np.abs(
                    led["new_h"] - production_response.hydrogen_fraction))),
                "helium_maximum_absolute_difference": float(np.max(np.abs(
                    led["new_he"] - production_response.helium_fraction))),
            }
            perturbations = {
                "iteration_count_96_vs_160": np.asarray(tighter) - np.asarray(production),
                "heating_rate_one_ulp": np.asarray(perturbed) - np.asarray(production),
                "ledger_versus_response_populations": ledger_vector - production_same_definition,
            }
            endpoint = {
                "production_norms": norms(production.reshape(-1, 4), masses),
                "ledger_norms": norms(ledger_vector.reshape(-1, 4), masses),
                "nonphysical_cells": int(np.count_nonzero(led["remaining"] <= 0)),
                "ledger_population_difference": ledger_populations,
                "perturbations": {
                    name: {
                        "l2": float(np.linalg.norm(delta)),
                        "maximum_absolute_difference": float(np.max(np.abs(delta))),
                        "over_production_l2": float(
                            np.linalg.norm(delta) / np.linalg.norm(production)),
                    }
                    for name, delta in perturbations.items()
                },
            }
            probes["endpoints"][label] = endpoint
        reference = args.reference_l2 if args.reference_l2 is not None \
            else float(np.median(REFERENCE_CANDIDATE_MINUS_BASELINE_L2))
        noise = max(
            row["perturbations"][name]["l2"]
            for row in probes["endpoints"].values()
            for name in row["perturbations"]
        )
        probes["signal_to_noise"] = {
            "reference_candidate_minus_baseline_l2": reference,
            "reference_choices_l2": list(REFERENCE_CANDIDATE_MINUS_BASELINE_L2),
            "worst_perturbation_l2": noise,
            "reference_over_noise": float(reference / noise) if noise > 0 else None,
            "measured_cross_platform_l2_difference": MEASURED_CROSS_PLATFORM_L2_DIFFERENCE,
            "measured_cross_platform_maximum_difference": MEASURED_CROSS_PLATFORM_MAXIMUM_DIFFERENCE,
            "reference_over_cross_platform_difference": float(
                reference / MEASURED_CROSS_PLATFORM_L2_DIFFERENCE),
            "definition": "candidate-vs-baseline L2 difference divided by the largest numerical perturbation L2",
            "scope": "numerical noise floor only; not an acceptance gate and not an error bound on the physics",
        }
        probes["sources"] = input_claims
        probes["environment"] = pipeline.environment()
        probes["classification"] = "read-only numerical noise floor; no acceptance implied"
        probes["codec_identity"] = identity
        pipeline.write_json(out / "noise_floor.json", probes)
        pipeline.write_json(out / "status.json", {
            "status": "complete",
            "signal_to_noise": probes["signal_to_noise"]["reference_over_noise"]})
    except Exception as exc:
        pipeline.write_json(out / "status.json", {"status": "failed", "error": str(exc)})
        raise


if __name__ == "__main__":
    main()
