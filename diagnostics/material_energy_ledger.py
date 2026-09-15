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
import math
from pathlib import Path

import numpy as np

from eccentric_tde_observer import radiation_matter_feedback as rmf

ROOT = Path(__file__).resolve().parents[1]
OLD_TIME_LEVEL = "outputs/phase7b4r_depth128_phase2048.npz"

# Depth-grid geometry, taken from the adapter rather than assumed:
# `phase7b9_formal_feedback_pair_adapter.py:593` reshapes the radiation array to
# (256, 16, ...) and averages over the trailing subcell axis, and
# `phase7b7a_feedback_coefficients.py:570` then takes `parent[:128]` as `half_*`.
SUBCELLS = 4096
PARENT_LAYERS = 256
PARENT_SUBCELLS = SUBCELLS // PARENT_LAYERS
MATERIAL_LAYERS = PARENT_LAYERS // 2


def finite_or_none(value: float):
    """Emit null instead of a non-finite number; the JSON stays strict."""
    return value if math.isfinite(value) else None


def parent_layer_contributions(per_depth):
    """4096 subcell contributions -> 256 whole-column parent layers.

    Sums across the 16 subcells of each parent layer. The input is a
    width-weighted numerator, so it is summed here and never reweighted.
    """
    array = np.asarray(per_depth, dtype=np.float64)
    if array.shape != (SUBCELLS,):
        raise ValueError("expected %d subcell contributions" % SUBCELLS)
    return array.reshape(PARENT_LAYERS, PARENT_SUBCELLS).sum(axis=1)


def fold_to_material_layers(parent_layer):
    """256 parent layers -> 128 material layers.

    The two half-columns are mirror images, so a material layer is
    `parent[i] + parent[255 - i]`, i.e. front + reversed(back). It is NOT a
    contiguous run of subcells: grouping 32 adjacent subcells returns layer 48
    for a perturbation that truly sits in layer 96.
    """
    parent = np.asarray(parent_layer, dtype=np.float64)
    if parent.shape != (PARENT_LAYERS,):
        raise ValueError("expected %d parent layers" % PARENT_LAYERS)
    half = MATERIAL_LAYERS
    return parent[:half] + parent[half:][::-1]


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
        "old_h": old_h, "old_he": old_he,
        "new_h": new_h, "new_he": new_he, "electron": electron,
        "charge_residual": charge_residual, "particle_residual": particle_residual,
        "split_self_check": split_error,
        "delta_ionization": ion_new - ion_old,
        "remaining_relative_to_old_gas_heat": np.where(
            gas_old > 0.0, remaining / gas_old, np.nan
        ),
    }


def mass_weights(cell_mass_g_cm2):
    cell_mass = np.asarray(cell_mass_g_cm2, dtype=np.float64)
    return cell_mass / np.sum(cell_mass)


def endpoint_report(led, weights, index):
    """Absolute and relative worst layer are different argmins -- report both."""
    remaining = led["remaining"]
    bad = remaining <= 0.0
    count = int(np.count_nonzero(bad))
    relative = led["remaining_relative_to_old_gas_heat"]
    absolute_worst = int(np.argmin(remaining))
    finite_relative = np.where(np.isfinite(relative), relative, np.inf)
    relative_worst = int(np.argmin(finite_relative))
    shortfall = -remaining[bad] if count else np.array([])
    relative_shortfall = -finite_relative[bad] if count else np.array([])
    return {
        "endpoint": index,
        "cells": int(remaining.size),
        "failing_cells": count,
        "failing_mass_fraction": float(np.sum(weights[bad])) if count else 0.0,
        "failing_indices": np.nonzero(bad)[0].tolist(),
        "absolute_worst": {
            "criterion": "minimum remaining gas heat (erg/g)",
            "cell": absolute_worst,
            "remaining_erg_g": finite_or_none(float(remaining[absolute_worst])),
            "shortfall_over_old_gas_heat": finite_or_none(
                float(-remaining[absolute_worst] / led["gas_old"][absolute_worst])
            ),
        },
        "relative_worst": {
            "criterion": "minimum remaining gas heat relative to that cell's old gas heat",
            "cell": relative_worst,
            "ratio": finite_or_none(float(finite_relative[relative_worst])),
            "remaining_erg_g": finite_or_none(float(remaining[relative_worst])),
        },
        "maximum_shortfall_erg_g": finite_or_none(float(np.max(shortfall))) if count else None,
        "maximum_relative_shortfall": (
            finite_or_none(float(np.max(relative_shortfall))) if count else None
        ),
        "maximum_charge_residual": finite_or_none(float(np.max(led["charge_residual"]))),
        "maximum_particle_residual": finite_or_none(float(np.max(led["particle_residual"]))),
        "split_self_check": finite_or_none(led["split_self_check"]),
    }


def cell_ledger(led, cell, weights):
    """Full ledger for one material cell, with real old and new populations."""
    old_h, new_h = led["old_h"][cell], led["new_h"][cell]
    old_he, new_he = led["old_he"][cell], led["new_he"][cell]
    return {
        "cell": int(cell),
        "mass_fraction": finite_or_none(float(weights[cell])),
        "old_gas_heat_erg_g": finite_or_none(float(led["gas_old"][cell])),
        "old_ionization_erg_g": finite_or_none(float(led["ion_old"][cell])),
        "old_total_erg_g": finite_or_none(float(led["total_old"][cell])),
        "new_ionization_erg_g": finite_or_none(float(led["ion_new"][cell])),
        "delta_ionization_erg_g": finite_or_none(float(led["delta_ionization"][cell])),
        "q_erg_s_cm3": finite_or_none(float(led["q"][cell])),
        "dt_times_q_over_rho_erg_g": finite_or_none(float(led["radiative_energy"][cell])),
        "target_total_erg_g": finite_or_none(float(led["target"][cell])),
        "remaining_gas_heat_erg_g": finite_or_none(float(led["remaining"][cell])),
        "remaining_over_old_gas_heat": finite_or_none(
            float(led["remaining_relative_to_old_gas_heat"][cell])
        ),
        "old_hydrogen": [finite_or_none(float(x)) for x in old_h],
        "new_hydrogen": [finite_or_none(float(x)) for x in new_h],
        "delta_hydrogen": [finite_or_none(float(b - a)) for a, b in zip(old_h, new_h)],
        "old_helium": [finite_or_none(float(x)) for x in old_he],
        "new_helium": [finite_or_none(float(x)) for x in new_he],
        "delta_helium": [finite_or_none(float(b - a)) for a, b in zip(old_he, new_he)],
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
        # then takes the worst component. The numerator and denominator reported
        # here belong to that SAME component -- taking each one's maximum
        # separately would pair numbers drawn from different components. Every
        # component is kept alongside so the pairing can be checked.
        # Scalar metrics (the heating arrays are 1-D) collapse to 0-d here; keep
        # them in a length-1 axis so component indexing is uniform.
        component_numerator = np.atleast_1d(np.sum(numerator, axis=0))
        component_denominator = np.atleast_1d(np.sum(denominator, axis=0))
        defined = component_denominator > 0.0
        component_ratio = np.full(component_denominator.shape, np.nan)
        component_ratio[defined] = (
            component_numerator[defined] / component_denominator[defined]
        )
        worst = int(np.nanargmax(component_ratio))
        metrics[key] = {
            "worst_component_index": worst,
            "numerator": finite_or_none(float(component_numerator[worst])),
            "denominator": finite_or_none(float(component_denominator[worst])),
            "ratio": finite_or_none(float(component_ratio[worst])),
            "component_numerators": [finite_or_none(float(x)) for x in component_numerator],
            "component_denominators": [finite_or_none(float(x)) for x in component_denominator],
            "component_ratios": [finite_or_none(float(x)) for x in component_ratio],
        }
        numerators[key] = np.sum(numerator.reshape(SUBCELLS, -1), axis=1)

    key = "atomic_rate_heating_erg_s_cm3"
    per_depth = numerators[key]
    total = float(np.sum(per_depth))
    order = np.argsort(per_depth)[::-1]
    cumulative = np.cumsum(per_depth[order]) / total
    depths_for = {
        f"{int(100 * frac)}%": int(np.searchsorted(cumulative, frac)) + 1
        for frac in (0.5, 0.9, 0.99)
    }
    # The adapter maps 4096 radiation subcells onto 256 whole-column parent
    # layers of 16 subcells each
    # (`phase7b9_formal_feedback_pair_adapter.py:593`), and `half_*` is
    # `parent[:128]`. A material layer is NOT a contiguous run of 32 subcells;
    # the two half-columns are mirror images, so folding back to 128 layers is
    # front + reversed(back). The numerator already carries the width weight, so
    # it is summed across the 16 subcells, never reweighted.
    parent_layer = parent_layer_contributions(per_depth)
    front, back = parent_layer[:MATERIAL_LAYERS], parent_layer[MATERIAL_LAYERS:]
    folded = fold_to_material_layers(parent_layer)
    full_total = float(np.sum(parent_layer))
    front_total = float(np.sum(front))
    top_folded = np.argsort(folded)[::-1][:5]

    def share(value, denominator):
        return finite_or_none(float(value) / denominator) if denominator else None

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

    top_front = np.argsort(front)[::-1][:5]
    return {
        "metrics": metrics,
        "numerator_by_depth": {
            "grid": {
                "subcells": SUBCELLS,
                "parent_layers": PARENT_LAYERS,
                "subcells_per_parent": PARENT_SUBCELLS,
                "material_layers": MATERIAL_LAYERS,
                "fold": "material = parent[:128] + parent[128:][::-1]",
            },
            "active_subcell_depths": int(np.count_nonzero(per_depth)),
            "subcell_depths_holding_half": depths_for["50%"],
            "subcell_depths_holding_90pct": depths_for["90%"],
            "subcell_depths_holding_99pct": depths_for["99%"],
            "top_single_subcell_share_of_full_column": share(per_depth[order[0]], full_total),
            "parent_layer_totals": {
                "full_column": finite_or_none(full_total),
                "front_half": finite_or_none(front_total),
                "back_half": finite_or_none(float(np.sum(back))),
            },
            "top_folded_material_layers": top_folded.tolist(),
            "top_folded_share_of_full_column": share(folded[top_folded].sum(), full_total),
            "top_front_half_layers": top_front.tolist(),
            "top_front_half_share_of_front_column": share(front[top_front].sum(), front_total),
            "material_layer_96": {
                "folded_value": finite_or_none(float(folded[96])),
                "share_of_full_column": share(folded[96], full_total),
                "front_value": finite_or_none(float(front[96])),
                "share_of_front_column": share(front[96], front_total),
            },
            "normalisation_note": (
                "full-column and front-half-column shares are different "
                "denominators; report and compare them separately, never mixed"
            ),
        },
        "absorption_emission_cancellation": {
            "closure_error_relative": finite_or_none(closure),
            "net_over_gross_median": finite_or_none(float(np.median(cancellation))),
            "net_over_gross_p90": finite_or_none(float(np.percentile(cancellation, 90))),
            "net_over_gross_max": finite_or_none(float(np.max(cancellation))),
            "median_amplification": finite_or_none(float(1.0 / np.median(cancellation))),
            "interpretation": (
                "net heating is locally a difference of two nearly equal large "
                "terms. This describes the local mechanism only: it is not an "
                "identity for the volume-weighted formal metric, and multiplying "
                "these local factors by a change aggregated at another scale is "
                "not a quantitative causal proof."
            ),
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
    parser.add_argument("--feedback-source", type=Path, default=None,
                        help="directory holding previous_feedback.npz and "
                             "final_feedback.npz (defaults to --run). Use this to "
                             "replay an archived round whose feedback arrays live "
                             "outside the run root, without moving any file.")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    run = ROOT / args.run
    feedback_dir = (ROOT / args.feedback_source) if args.feedback_source else run
    if not feedback_dir.is_dir():
        raise SystemExit(f"feedback source directory missing: {feedback_dir}")

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
        name: dict(np.load(feedback_dir / f"{name}_feedback.npz"))
        for name in ("previous", "final")
    }

    result = {
        "run": args.run,
        "feedback_source": feedback_dir.relative_to(ROOT).as_posix(),
        "phase_index": phase,
        "step_duration_s": duration,
        "material_cells": int(density.size),
        "inputs": {
            "trial_material": {
                "path": (run / "trial_material.npz").relative_to(ROOT).as_posix(),
                "sha256": sha256(run / "trial_material.npz")},
            "old_time_level": {"sha256": sha256(ROOT / OLD_TIME_LEVEL), "phase": phase},
            "previous_feedback": {
                "path": (feedback_dir / "previous_feedback.npz").relative_to(ROOT).as_posix(),
                "sha256": sha256(feedback_dir / "previous_feedback.npz")},
            "final_feedback": {
                "path": (feedback_dir / "final_feedback.npz").relative_to(ROOT).as_posix(),
                "sha256": sha256(feedback_dir / "final_feedback.npz")},
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
        rep["absolute_worst_cell_ledger"] = cell_ledger(
            led, rep["absolute_worst"]["cell"], weights)
        rep["relative_worst_cell_ledger"] = cell_ledger(
            led, rep["relative_worst"]["cell"], weights)
        rep["tracked_cell_96"] = cell_ledger(led, 96, weights)
        result["endpoints"][name] = rep

    # Endpoint-to-endpoint sensitivity. Observed difference only, not an error bound.
    previous_absolute = result["endpoints"]["previous"]["absolute_worst"]
    final_absolute = result["endpoints"]["final"]["absolute_worst"]
    result["endpoint_difference"] = {
        "absolute_worst_previous": previous_absolute,
        "absolute_worst_final": final_absolute,
        "delta_minimum_remaining_erg_g": finite_or_none(
            final_absolute["remaining_erg_g"] - previous_absolute["remaining_erg_g"]
        ),
        "failing_cells_previous": result["endpoints"]["previous"]["failing_cells"],
        "failing_cells_final": result["endpoints"]["final"]["failing_cells"],
        "maximum_abs_delta_ionization_erg_g": finite_or_none(float(
            np.max(np.abs(leds["final"]["delta_ionization"] - leds["previous"]["delta_ionization"]))
        )),
        "maximum_abs_delta_radiative_energy_erg_g": finite_or_none(float(
            np.max(np.abs(leds["final"]["radiative_energy"] - leds["previous"]["radiative_energy"]))
        )),
        "maximum_abs_delta_q_erg_s_cm3": finite_or_none(float(
            np.max(np.abs(leds["final"]["q"] - leds["previous"]["q"]))
        )),
        "interpretation": "observed adjacent-endpoint sensitivity, not a strict error bound",
    }

    # Task 3: what the formal heating-stability metric is actually made of.
    result["heating_stability"] = heating_decomposition(feedbacks["previous"], feedbacks["final"])
    result["array_mapping_note"] = (
        "There IS a defined mapping. The adapter "
        "(phase7b9_formal_feedback_pair_adapter.py:593) reduces the 4096 radiation "
        "subcells to 256 whole-column parent layers of 16 subcells each via "
        "reshape(256, 16, ...).mean(axis=1), and phase7b7a_feedback_coefficients.py:570 "
        "takes half_* = parent[:128]. The two half-columns are mirror images, so the "
        "fold back to 128 material layers is parent[:128] + parent[128:][::-1]. "
        "An earlier revision of this tool used reshape(128, 32) and was wrong."
    )
    result["unevaluated"] = (
        "encoded-residual noise-to-signal ratio stays unevaluated: the material response "
        "raised before the residual was formed; no substitute value is reported here."
    )

    text = json.dumps(result, indent=2, allow_nan=False)
    print(text)
    if args.json:
        args.json.write_text(text + "\n")
        print(f"\nwritten: {args.json}")


if __name__ == "__main__":
    main()
