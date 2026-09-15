"""Per-cell material energy ledger for a frozen-radiation feedback endpoint.

Reproduces the exact arithmetic of `frozen_radiation_material_response` up to the
point where `ground_state_material_temperature_from_specific_energy_k` raises
`PhysicalDomainError("specific material energy leaves no positive gas heat")`,
and then reports the ledger instead of aborting.

Everything here is READ-ONLY analysis of existing artifacts:

* the population update is the original `charge_neutral_backward_euler_step`;
* the gas/ionization split uses the original module constants and private
  helpers (`_population_arrays`, `_composition_per_gram`);
* no clipping, flooring, rescaling or energy redefinition anywhere.

Kept outside src/scripts/hpc on purpose: `hpc/pipeline.py` pins the sha256 of
every .py in those three trees, so adding files here cannot disturb the frozen
source inventory of an already-prepared run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from eccentric_tde_observer import radiation_matter_feedback as rmf

ROOT = Path(__file__).resolve().parents[1]
OLD_TIME_LEVEL = "outputs/phase7b4r_depth128_phase2048.npz"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def per_gram_constants(composition=rmf.SOLAR_FULLY_IONIZED_H_HE):
    """Return (hydrogen, helium, nuclei) number per gram, as the solver does."""
    return rmf._composition_per_gram(composition)


def gas_specific_heat_erg_g(temperature, hydrogen, helium, composition):
    """1.5 kB T (nuclei + electrons) per gram -- identical to the solver's split."""
    hydrogen_per_gram, helium_per_gram, nuclei_per_gram = per_gram_constants(composition)
    electron_per_gram = hydrogen_per_gram * hydrogen[:, 1] + helium_per_gram * (
        helium[:, 1] + 2.0 * helium[:, 2]
    )
    return 1.5 * rmf.BOLTZMANN_ERG_K * np.asarray(temperature) * (
        nuclei_per_gram + electron_per_gram
    )


def ionization_specific_energy_erg_g(hydrogen, helium, composition):
    """Ionization energy per gram -- identical to the solver's split."""
    hydrogen_per_gram, helium_per_gram, _ = per_gram_constants(composition)
    return hydrogen_per_gram * hydrogen[:, 1] * rmf.HYDROGEN_IONIZATION_ERG + helium_per_gram * (
        helium[:, 1] * rmf.HELIUM_I_IONIZATION_ERG
        + helium[:, 2] * (rmf.HELIUM_I_IONIZATION_ERG + rmf.HELIUM_II_IONIZATION_ERG)
    )


def updated_populations(density, duration, photoionization, recombination, old_h, old_he):
    """Run the solver's own charge-neutral backward-Euler step per cell."""
    composition = rmf.SOLAR_FULLY_IONIZED_H_HE
    hydrogen_nuclei = composition.hydrogen_mass_fraction * np.asarray(density) / rmf.PROTON_MASS_G
    helium_nuclei = composition.helium_mass_fraction * np.asarray(density) / (4.0 * rmf.PROTON_MASS_G)
    cells = old_h.shape[0]
    new_h = np.empty_like(old_h)
    new_he = np.empty_like(old_he)
    electron = np.empty(cells)
    charge_residual = np.empty(cells)
    particle_residual = np.empty(cells)
    zeros = np.zeros(3)
    for cell in range(cells):
        step = rmf.charge_neutral_backward_euler_step(
            old_h[cell], old_he[cell],
            float(hydrogen_nuclei[cell]), float(helium_nuclei[cell]),
            float(duration),
            np.asarray(photoionization)[cell], zeros,
            np.asarray(recombination)[cell], zeros,
        )
        new_h[cell] = step.hydrogen_fraction
        new_he[cell] = step.helium_fraction
        electron[cell] = step.electron_density_cm3
        charge_residual[cell] = step.relative_charge_residual
        particle_residual[cell] = step.particle_conservation_residual
    return new_h, new_he, electron, charge_residual, particle_residual


def ledger(feedback, density, duration, old_temperature, old_h, old_he):
    """One endpoint's full per-cell energy ledger. Never raises on negative heat."""
    composition = rmf.SOLAR_FULLY_IONIZED_H_HE
    heating = np.asarray(feedback["half_atomic_rate_heating_erg_s_cm3"], dtype=np.float64)
    photoionization = np.asarray(feedback["half_photoionization_s1"], dtype=np.float64)
    recombination = np.asarray(feedback["half_total_recombination_cm3_s"], dtype=np.float64)

    gas_old = gas_specific_heat_erg_g(old_temperature, old_h, old_he, composition)
    ion_old = ionization_specific_energy_erg_g(old_h, old_he, composition)
    total_old = gas_old + ion_old
    # Self-check: the solver's own routine must agree with the split above.
    reference = rmf.ground_state_material_specific_energy_erg_g(
        old_temperature, old_h, old_he, composition=composition
    )
    split_error = float(np.max(np.abs(total_old - reference) / np.abs(reference)))

    new_h, new_he, electron, charge_residual, particle_residual = updated_populations(
        density, duration, photoionization, recombination, old_h, old_he
    )
    ion_new = ionization_specific_energy_erg_g(new_h, new_he, composition)
    q = heating
    radiative_energy = duration * q / np.asarray(density)
    target = total_old + radiative_energy
    remaining = target - ion_new

    return {
        "gas_old": gas_old, "ion_old": ion_old, "total_old": total_old,
        "ion_new": ion_new, "q": q, "radiative_energy": radiative_energy,
        "target": target, "remaining": remaining,
        "new_h": new_h, "new_he": new_he, "electron": electron,
        "charge_residual": charge_residual, "particle_residual": particle_residual,
        "split_self_check": split_error,
        "delta_ionization": ion_new - ion_old,
    }


def mass_weights(cell_mass_g_cm2):
    cell_mass = np.asarray(cell_mass_g_cm2, dtype=np.float64)
    return cell_mass / np.sum(cell_mass)


def endpoint_report(led, weights, index):
    remaining = led["remaining"]
    bad = remaining <= 0.0
    count = int(np.count_nonzero(bad))
    order = np.argsort(remaining)
    worst = int(order[0])
    shortfall = -remaining[bad] if count else np.array([])
    return {
        "endpoint": index,
        "cells": int(remaining.size),
        "failing_cells": count,
        "failing_mass_fraction": float(np.sum(weights[bad])) if count else 0.0,
        "minimum_remaining_erg_g": float(remaining[worst]),
        "worst_cell": worst,
        "failing_indices": np.nonzero(bad)[0].tolist(),
        "maximum_shortfall_erg_g": float(np.max(shortfall)) if count else 0.0,
        "maximum_shortfall_over_old_gas_heat": (
            float(np.max(shortfall) / led["gas_old"][worst]) if count else 0.0
        ),
        "minimum_remaining_over_old_gas_heat": float(
            remaining[worst] / led["gas_old"][worst]
        ),
        "maximum_charge_residual": float(np.max(led["charge_residual"])),
        "maximum_particle_residual": float(np.max(led["particle_residual"])),
        "split_self_check": led["split_self_check"],
    }


def worst_cell_ledger(led, cell, weights):
    return {
        "cell": int(cell),
        "mass_fraction": float(weights[cell]),
        "old_gas_heat_erg_g": float(led["gas_old"][cell]),
        "old_ionization_erg_g": float(led["ion_old"][cell]),
        "old_total_erg_g": float(led["total_old"][cell]),
        "new_ionization_erg_g": float(led["ion_new"][cell]),
        "delta_ionization_erg_g": float(led["delta_ionization"][cell]),
        "q_erg_s_cm3": float(led["q"][cell]),
        "dt_times_q_over_rho_erg_g": float(led["radiative_energy"][cell]),
        "target_total_erg_g": float(led["target"][cell]),
        "remaining_gas_heat_erg_g": float(led["remaining"][cell]),
        "remaining_over_old_gas_heat": float(led["remaining"][cell] / led["gas_old"][cell]),
        "old_hydrogen": led["new_h"][cell].tolist(),
        "old_helium": led["new_he"][cell].tolist(),
    }


HEATING_METRICS = (
    "photoionization_s1",
    "total_recombination_cm3_s",
    "atomic_rate_heating_erg_s_cm3",
    "source_direct_heating_erg_s_cm3",
    "source_formal_heating_erg_s_cm3",
)


def weighted_volume_terms(previous, final, width):
    """Reproduce `weighted_volume_l1` and also return per-depth numerator terms."""
    previous = np.asarray(previous, dtype=np.float64)
    final = np.asarray(final, dtype=np.float64)
    weight = np.asarray(width, dtype=np.float64).reshape(
        (np.size(width),) + (1,) * (previous.ndim - 1)
    )
    numerator = weight * np.abs(final - previous)
    denominator = weight * np.maximum(np.abs(previous), np.abs(final))
    return numerator, denominator


def heating_decomposition(previous, final):
    """Metric terms, depth localisation, and the absorption/emission cancellation."""
    width = np.asarray(previous["subcell_width_cm"], dtype=np.float64)
    metrics = {}
    numerators = {}
    for key in HEATING_METRICS:
        numerator, denominator = weighted_volume_terms(previous[key], final[key], width)
        # `weighted_volume_l1` sums over depth, divides per component, and the gate
        # then takes the worst component -- reproduce that order exactly.
        component_numerator = np.sum(numerator, axis=0)
        component_denominator = np.sum(denominator, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            component_ratio = np.where(
                component_denominator > 0.0,
                component_numerator / component_denominator,
                0.0,
            )
        metrics[key] = {
            "numerator": float(np.max(component_numerator)),
            "denominator": float(np.max(component_denominator)),
            "ratio": float(np.max(component_ratio)),
        }
        numerators[key] = np.sum(numerator.reshape(4096, -1), axis=1)

    key = "atomic_rate_heating_erg_s_cm3"
    per_depth = numerators[key]
    total = float(np.sum(per_depth))
    order = np.argsort(per_depth)[::-1]
    cumulative = np.cumsum(per_depth[order]) / total
    depths_for = {
        f"{int(100 * frac)}%": int(np.searchsorted(cumulative, frac)) + 1
        for frac in (0.5, 0.9, 0.99)
    }
    per_material_layer = per_depth.reshape(128, 32).sum(axis=1)
    top_layers = np.argsort(per_material_layer)[::-1][:5]

    absorbed = np.abs(np.asarray(previous["absorbed_power_erg_s_cm3"], dtype=np.float64))
    emitted = np.abs(np.asarray(previous["emitted_power_erg_s_cm3"], dtype=np.float64))
    net = np.asarray(previous[key], dtype=np.float64)
    closure = float(np.max(np.abs(absorbed - emitted - net)) / np.max(np.abs(net)))
    cancellation = np.abs(net) / (absorbed + emitted)

    components = {}
    for base in ("absorbed_power_erg_s_cm3", "emitted_power_erg_s_cm3",
                 "atomic_rate_heating_erg_s_cm3"):
        a = np.asarray(previous[base], dtype=np.float64)
        b = np.asarray(final[base], dtype=np.float64)
        components[base] = {
            "max_relative_change": float(
                np.max(np.abs(b - a)) / max(np.max(np.abs(a)), np.max(np.abs(b)))
            ),
            "minimum": float(np.min(a)), "maximum": float(np.max(a)),
            "negative_fraction": float(np.mean(a < 0.0)),
        }

    return {
        "metrics": metrics,
        "numerator_by_depth": {
            "active_depths": int(np.count_nonzero(per_depth)),
            "depths_holding_half": depths_for["50%"],
            "depths_holding_90pct": depths_for["90%"],
            "depths_holding_99pct": depths_for["99%"],
            "top_single_depth_share": float(per_depth[order[0]] / total),
            "top_layers": top_layers.tolist(),
            "top_layers_share": float(per_material_layer[top_layers].sum() / total),
        },
        "absorption_emission_cancellation": {
            "closure_error_relative": closure,
            "net_over_gross_median": float(np.median(cancellation)),
            "net_over_gross_p90": float(np.percentile(cancellation, 90)),
            "net_over_gross_max": float(np.max(cancellation)),
            "median_amplification": float(1.0 / np.median(cancellation)),
        },
        "component_changes": components,
        "note": (
            "ratio above threshold is an adjacent-endpoint change, not evidence of "
            "numerical divergence; compare with the component changes"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="outputs/hpc/hhe-r025-warm")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    run = ROOT / args.run

    with np.load(run / "trial_material.npz") as trial:
        phase = int(trial["phase_index"])
        duration = float(trial["step_duration_s"])
        density = np.array(trial["density_g_cm3"], copy=True)
    with np.load(ROOT / OLD_TIME_LEVEL) as old:
        if duration != float(old["step_duration_s"][phase]) or not np.array_equal(
            density, old["density_g_cm3"][phase]
        ):
            raise SystemExit("fixed physical time level changed; refusing to report")
        old_temperature = np.array(old["temperature_k"][phase], copy=True)
        old_hydrogen = np.array(old["hydrogen_fraction"][phase], copy=True)
        old_helium = np.array(old["helium_fraction"][phase], copy=True)
        cell_mass = np.array(old["cell_mass_g_cm2"], copy=True)
        mass_edge = np.array(old["mass_fraction_edges"], copy=True)

    weights = mass_weights(cell_mass)
    feedbacks = {
        name: dict(np.load(run / f"{name}_feedback.npz"))
        for name in ("previous", "final")
    }

    result = {
        "run": args.run,
        "phase_index": phase,
        "step_duration_s": duration,
        "material_cells": int(density.size),
        "inputs": {
            "trial_material": {"sha256": sha256(run / "trial_material.npz")},
            "old_time_level": {"sha256": sha256(ROOT / OLD_TIME_LEVEL), "phase": phase},
            "previous_feedback": {"sha256": sha256(run / "previous_feedback.npz")},
            "final_feedback": {"sha256": sha256(run / "final_feedback.npz")},
        },
        "units": {
            "specific_energy": "erg/g", "heating": "erg/s/cm3",
            "duration": "s", "density": "g/cm3", "cell_mass": "g/cm2",
        },
        "endpoints": {},
    }

    leds = {}
    for name in ("previous", "final"):
        led = ledger(feedbacks[name], density, duration, old_temperature, old_hydrogen, old_helium)
        leds[name] = led
        rep = endpoint_report(led, weights, name)
        rep["worst_cell_ledger"] = worst_cell_ledger(led, rep["worst_cell"], weights)
        result["endpoints"][name] = rep

    # Endpoint-to-endpoint sensitivity. Observed difference only, not an error bound.
    result["endpoint_difference"] = {
        "remaining_min_previous_erg_g": result["endpoints"]["previous"]["minimum_remaining_erg_g"],
        "remaining_min_final_erg_g": result["endpoints"]["final"]["minimum_remaining_erg_g"],
        "delta_minimum_remaining_erg_g": (
            result["endpoints"]["final"]["minimum_remaining_erg_g"]
            - result["endpoints"]["previous"]["minimum_remaining_erg_g"]
        ),
        "failing_cells_previous": result["endpoints"]["previous"]["failing_cells"],
        "failing_cells_final": result["endpoints"]["final"]["failing_cells"],
        "maximum_abs_delta_ionization_erg_g": float(
            np.max(np.abs(leds["final"]["delta_ionization"] - leds["previous"]["delta_ionization"]))
        ),
        "maximum_abs_delta_radiative_energy_erg_g": float(
            np.max(np.abs(leds["final"]["radiative_energy"] - leds["previous"]["radiative_energy"]))
        ),
        "maximum_abs_delta_q_erg_s_cm3": float(
            np.max(np.abs(leds["final"]["q"] - leds["previous"]["q"]))
        ),
        "interpretation": "observed adjacent-endpoint sensitivity, not a strict error bound",
    }

    # Task 3: what the formal heating-stability metric is actually made of.
    result["heating_stability"] = heating_decomposition(feedbacks["previous"], feedbacks["final"])
    result["array_mapping_note"] = (
        "half_* arrays are parent_*[:128] (256-element parent grid), not a reduction of "
        "the 4096-depth radiation grid; the ledger uses the same half_* arrays the solver "
        "consumes and the metric uses the same 4096 arrays weighted_volume_l1 consumes."
    )
    result["unevaluated"] = (
        "encoded-residual noise-to-signal ratio stays unevaluated: the material response "
        "raised before the residual was formed; no substitute value is reported here."
    )

    print(json.dumps(result, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n")
        print(f"\nwritten: {args.json}")


if __name__ == "__main__":
    main()
