"""Read-only replay of exported USTC feedback arrays; never run radiation maps.

The material response is called unchanged. Its temperature inverse is observed
to capture the target energy and populations even when positive gas heat fails.
Original run files/protocols remain immutable; results go to a new directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np

from eccentric_tde_observer import radiation_matter_feedback as rmf
from eccentric_tde_observer.formal_feedback_pair import weighted_volume_l1

METRICS = {
    "photoionization_s1": "photoionization_volume_l1",
    "total_recombination_cm3_s": "total_recombination_volume_l1",
    "atomic_rate_heating_erg_s_cm3": "atomic_heating_volume_l1",
    "source_direct_heating_erg_s_cm3": "direct_heating_volume_l1",
    "source_formal_heating_erg_s_cm3": "formal_heating_volume_l1",
}
PAIRS = (
    ("warm", "hhe-r025-warm", "hhe-r025-warm"),
    ("round1", "hhe-diag-r025/feedback-round1", "hhe-diag-r025"),
    ("round2", "hhe-diag-r025/feedback-round2", "hhe-diag-r025"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def arrays(path: Path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key].copy() for key in data.files}


def checked_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside declared root: {relative}")
    return path


def check_claim(path: Path, claim: dict):
    if path.stat().st_size != claim["size_bytes"] or sha256(path) != claim["sha256"]:
        raise ValueError(f"Artifact size/hash mismatch: {path}")


def verify_package(root: Path) -> dict:
    manifest = read(root / "MANIFEST.json")
    rows = manifest["files"]
    names = [row["path"] for row in rows]
    if len(set(names)) != len(names) or len(rows) != manifest["file_count"]:
        raise ValueError("Duplicate names or incorrect manifest count")
    if sum(row["size_bytes"] for row in rows) != manifest["total_bytes"]:
        raise ValueError("Incorrect manifest byte total")
    for row in rows:
        check_claim(checked_path(root, row["path"]), row)
    text_rows = {}
    for line in (root / "MANIFEST.txt").read_text().splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) == 3 and parts[0].isdigit():
            if parts[2] in text_rows:
                raise ValueError("Duplicate text-manifest path")
            text_rows[parts[2]] = (int(parts[0]), parts[1])
    if text_rows != {row["path"]: (row["size_bytes"], row["sha256"]) for row in rows}:
        raise ValueError("Text and JSON manifests disagree")
    expected = set(names) | {"MANIFEST.json", "MANIFEST.txt"}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("Unexpected or missing package files")
    return {"payload_files": len(rows), "payload_bytes": manifest["total_bytes"],
            "regular_files_including_manifests": len(actual),
            "manifest_sha256": sha256(root / "MANIFEST.json")}


def depth_contributions(previous, final, width):
    """Width-weighted numerator on 256 parents and mirrored 128 material cells."""
    a, b, w = map(np.asarray, (previous, final, width))
    if a.shape != (4096,) or b.shape != a.shape or w.shape != a.shape:
        raise ValueError("Expected 4096 scalar radiation-depth cells")
    if not all(np.all(np.isfinite(x)) for x in (a, b, w)) or np.any(w <= 0):
        raise ValueError("Invalid depth arrays or widths")
    terms = w * np.abs(b - a)
    parent = terms.reshape(256, 16).sum(axis=1)
    folded = parent[:128] + parent[128:][::-1]
    return terms, parent, folded


def component_metric(previous, final, width):
    a, b = np.asarray(previous), np.asarray(final)
    ratio = np.asarray(weighted_volume_l1(a, b, width))
    weight = np.asarray(width).reshape((len(width),) + (1,) * (a.ndim - 1))
    num = (weight * np.abs(b - a)).sum(axis=0)
    den = (weight * np.maximum(np.abs(a), np.abs(b))).sum(axis=0)
    return {"numerator": np.asarray(num).tolist(), "denominator": np.asarray(den).tolist(),
            "ratio": ratio.tolist(), "maximum_ratio": float(ratio.max())}


def ion_energy(h, he):
    hp, hep, _ = rmf._composition_per_gram(rmf.SOLAR_FULLY_IONIZED_H_HE)
    return hp * h[:, 1] * rmf.HYDROGEN_IONIZATION_ERG + hep * (
        he[:, 1] * rmf.HELIUM_I_IONIZATION_ERG
        + he[:, 2] * (rmf.HELIUM_I_IONIZATION_ERG + rmf.HELIUM_II_IONIZATION_ERG))


def material_replay(feedback, old, phase, duration, density):
    if duration != float(old["step_duration_s"][phase]) or not np.array_equal(
        density, old["density_g_cm3"][phase]
    ):
        raise ValueError("Physical old time level mismatch")
    h, he, temp = (old[name][phase] for name in
                   ("hydrogen_fraction", "helium_fraction", "temperature_k"))
    inverse = rmf.ground_state_material_temperature_from_specific_energy_k
    captured = {}

    def observe(energy, new_h, new_he, **kwargs):
        captured.update(target=energy.copy(), hydrogen=new_h.copy(), helium=new_he.copy())
        return inverse(energy, new_h, new_he, **kwargs)

    error = None
    try:
        with patch.object(rmf, "ground_state_material_temperature_from_specific_energy_k", observe):
            rmf.frozen_radiation_material_response(
                density, temp, h, he, duration, feedback["half_photoionization_s1"],
                feedback["half_total_recombination_cm3_s"],
                feedback["half_atomic_rate_heating_erg_s_cm3"])
    except rmf.PhysicalDomainError as exc:
        if str(exc) != "specific material energy leaves no positive gas heat":
            raise
        error = str(exc)
    if not captured:
        raise RuntimeError("Material response did not reach the energy inverse")
    hp, hep, nuclei = rmf._composition_per_gram(rmf.SOLAR_FULLY_IONIZED_H_HE)
    electron_per_gram = hp * h[:, 1] + hep * (he[:, 1] + 2 * he[:, 2])
    gas = 1.5 * rmf.BOLTZMANN_ERG_K * temp * (nuclei + electron_per_gram)
    old_ion, new_ion = ion_energy(h, he), ion_energy(captured["hydrogen"], captured["helium"])
    radiative = duration * feedback["half_atomic_rate_heating_erg_s_cm3"] / density
    np.testing.assert_array_equal(captured["target"], gas + old_ion + radiative)
    remaining = captured["target"] - new_ion
    bad = remaining <= 0
    weights = old["cell_mass_g_cm2"] / np.sum(old["cell_mass_g_cm2"])
    relative = remaining / gas
    return {
        "solver_error": error, "failing_indices": np.flatnonzero(bad).tolist(),
        "failing_count": int(bad.sum()), "failing_mass_fraction": float(weights[bad].sum()),
        "worst_absolute_cell": int(remaining.argmin()),
        "worst_relative_cell": int(relative.argmin()),
        "minimum_remaining_erg_g": float(remaining.min()),
        "maximum_shortfall_over_old_gas_heat": float(np.maximum(-relative, 0).max()),
        "per_cell": {"density_g_cm3": density.tolist(), "mass_weight": weights.tolist(),
                     "temperature_old_k": temp.tolist(), "hydrogen_old": h.tolist(),
                     "helium_old": he.tolist(), "hydrogen_new": captured["hydrogen"].tolist(),
                     "helium_new": captured["helium"].tolist(), "gas_old_erg_g": gas.tolist(),
                     "ion_old_erg_g": old_ion.tolist(), "ion_new_erg_g": new_ion.tolist(),
                     "delta_ionization_erg_g": (new_ion - old_ion).tolist(),
                     "radiative_energy_erg_g": radiative.tolist(),
                     "remaining_erg_g": remaining.tolist(), "remaining_over_old_gas": relative.tolist()},
    }


def audit(bundle: Path, reference_root: Path, code_root: Path) -> dict:
    result = {"package": verify_package(bundle), "pairs": {}, "run_config_hashes": {}}
    for name in ("hhe-r025-cold", "hhe-r025-warm", "hhe-diag-r025"):
        config_path = bundle / name / "config.json"
        config, state = read(config_path), read(bundle / name / "state.json")
        if sha256(config_path) != state["config_sha256"]:
            raise ValueError("Run config/state hash mismatch")
        checked = 0
        for claim in config["sources"]:
            if Path(claim["path"]).parts[0] in {"src", "scripts", "hpc"}:
                check_claim(checked_path(code_root, claim["path"]), claim)
                checked += 1
        result["run_config_hashes"][name] = {"sha256": sha256(config_path), "code_claims_verified": checked}

    for name, relative, run_relative in PAIRS:
        path, run = bundle / relative, bundle / run_relative
        protocol, summary = read(path / "feedback_protocol.json"), read(path / "feedback_summary.json")
        phash = sha256(path / "feedback_protocol.json")
        if phash != summary["protocol_sha256"]:
            raise ValueError("Summary/protocol mismatch")
        for key, source_path in (("trial_material", run / "trial_material.npz"),
                                 ("phase7b7j_protocol", path / "feedback_template.json"),
                                 ("adapter_runner", code_root / protocol["sources"]["adapter_runner"]["path"])):
            check_claim(source_path, protocol["sources"][key])
        old_claim = protocol["sources"]["physical_old_time_level"]
        old_path = checked_path(reference_root, old_claim["path"])
        check_claim(old_path, old_claim)
        old, trial = arrays(old_path), arrays(run / "trial_material.npz")
        phase, dt = int(trial["phase_index"]), float(trial["step_duration_s"])
        pair_result = {"protocol_sha256": phash, "old_input_sha256": old_claim["sha256"],
                       "phase": phase, "duration_s": dt, "endpoints": {}}
        feedback = {}
        old_ledger = read(path / "material_energy_ledger.json")
        history = read(run / "state.json")["history"]
        indices = read(path / "round_summary.json")["endpoints"] if name != "warm" else [1, 2]
        for label, index in zip(("previous", "final"), indices):
            data_path = path / f"{label}_feedback.npz"
            manifest = read(path / "feedback" / f"{label}_manifest.json")
            source = protocol["sources"][f"{label}_radiation"]
            row = next(row for row in history if row["iteration"] == index)
            if (manifest["protocol_sha256"] != phash or manifest["state_sha256"] != source["sha256"]
                    or row["input_sha256"] != source["sha256"]
                    or sha256(data_path) != manifest["feedback_artifact_sha256"]
                    or sha256(data_path) != summary[f"{label}_feedback"]["feedback_artifact_sha256"]):
                raise ValueError("Feedback artifact/endpoint lineage mismatch")
            feedback[label] = a = arrays(data_path)
            mapping_count = 0
            for key in a:
                if key.startswith("parent_"):
                    base = key[len("parent_"):]
                    expected = a[base].reshape(256, 16, *a[base].shape[1:]).mean(axis=1)
                    np.testing.assert_array_equal(expected, a[key])
                    np.testing.assert_array_equal(a[key][:128], a["half_" + base])
                    mapping_count += 1
            endpoint = material_replay(a, old, phase, dt, trial["density_g_cm3"])
            reported = old_ledger["endpoints"][label]
            endpoint["reported_minimum_difference_erg_g"] = (
                endpoint["minimum_remaining_erg_g"] - reported["minimum_remaining_erg_g"])
            if endpoint["failing_indices"] != reported["failing_indices"]:
                raise ValueError("Replayed failing cells differ from original ledger")
            if endpoint["solver_error"] != summary["material_response_failures"][label]["message"]:
                raise ValueError("Material replay disagrees with original rejection")
            endpoint.update(feedback_sha256=sha256(data_path), map_index=index,
                            parent_half_arrays_bitwise_verified=mapping_count)
            pair_result["endpoints"][label] = endpoint

        a, b = feedback["previous"], feedback["final"]
        np.testing.assert_array_equal(a["subcell_width_cm"], b["subcell_width_cm"])
        metrics = {}
        for key, report_key in METRICS.items():
            metrics[key] = component_metric(a[key], b[key], a["subcell_width_cm"])
            np.testing.assert_array_equal(metrics[key]["ratio"], summary["comparison"][report_key])
        pair_result["metrics"] = metrics
        terms, parent, folded = depth_contributions(a["atomic_rate_heating_erg_s_cm3"],
                                                   b["atomic_rate_heating_erg_s_cm3"], a["subcell_width_cm"])
        total = float(terms.sum())
        pair_result["depth_contributions"] = {
            "normalization": "full-column width-weighted absolute heating difference",
            "total": total, "parent_256": parent.tolist(), "folded_128": folded.tolist(),
            "top_folded_layers": np.argsort(folded)[-5:][::-1].tolist(),
            "cell96_folded_share": float(folded[96] / total) if total else None,
            "cell96_front_share": float(parent[96] / total) if total else None,
            "failed_layer_folded_share": {
                label: float(folded[e["failing_indices"]].sum() / total) if total else None
                for label, e in pair_result["endpoints"].items()},
        }
        pair_result["original_failed_gates"] = [k for k, v in summary["gate_checks"].items() if not v]
        result["pairs"][name] = pair_result
    result["limits"] = ["No raw radiation-state or per-frequency-block recomputation",
                         "No accepted material response, encoded residual or noise-ratio estimate",
                         "Original gzip container not supplied; inner manifest verified",
                         "Exported ledger is not the implementation requested by the Mac review"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code_root = Path(__file__).resolve().parents[1]
    result = audit(args.bundle, args.reference_root, code_root)
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output / "feedback_artifact_audit.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(output)
    for name, pair in result["pairs"].items():
        print(name, pair["metrics"]["atomic_rate_heating_erg_s_cm3"]["maximum_ratio"],
              [(e["failing_count"], e["failing_mass_fraction"], e["maximum_shortfall_over_old_gas_heat"])
               for e in pair["endpoints"].values()])


if __name__ == "__main__":
    main()
