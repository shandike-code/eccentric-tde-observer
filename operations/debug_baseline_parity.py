"""Locate where a replayed 7B9f baseline response stops matching its archive.

Read-only. Writes the full difference evidence *before* applying the original
parity check, so a failure can never again leave the numbers unrecorded.

This is a light single-process diagnostic (128 cells, a few MB), not a
radiation solve; it is deliberately runnable on a login node or a laptop.
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "hpc"), str(ROOT / "src"), str(ROOT / "scripts")]
import pipeline
from diagnostics.material_energy_ledger import ledger
from operations.conservative_residual_diagnostic import equation_residual, norms
from operations.prepare_encoded_backtrack import load_arrays
from operations.recover_equation_baseline import recover_equation_residual
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec,
)
from eccentric_tde_observer.radiation_matter_feedback import frozen_radiation_material_response
import phase7b9cy_refresh_feedback_worker_template as migration

PROTOCOL = "outputs/phase7b9f_preregistered_converged_feedback_residual.json"
SUMMARY = "outputs/phase7b9f_converged_feedback_residual_summary.json"
RECEIPT = "handoff/evidence/ustc-baseline-input-package-20260917.json"
DEFAULT_PACKAGE = "outputs/baseline-audit-inputs-20260917"
RTOL, ATOL = 1.0e-11, 3.0e-13
COMPONENT_NAMES = ("energy", "hydrogen_logratio", "helium_logratio", "electron_logratio")


def runtime_fingerprint() -> dict[str, object]:
    """Record the arithmetic environment; a libm/BLAS change is a hypothesis, not a default."""
    fingerprint: dict[str, object] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "numpy_config": np.__config__.show(mode="dicts"),
        "slurm": {k: v for k, v in sorted(__import__("os").environ.items())
                  if k.startswith("SLURM_")},
    }
    for module in ("scipy", "numba"):
        try:
            fingerprint[module] = __import__(module).__version__
        except Exception:  # 未安装或导入失败都要显式记录，不能当作版本一致。
            fingerprint[module] = None
    try:
        fingerprint["git_head"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
            timeout=20, check=True,
        ).stdout.strip()
        fingerprint["git_status"] = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True,
            timeout=20, check=True,
        ).stdout
    except Exception as exc:
        fingerprint["git_error"] = str(exc)
    return fingerprint


def array_difference(replay: np.ndarray, stored: np.ndarray) -> dict[str, object]:
    """Per-component and per-cell difference summary; no tolerance is applied here."""
    a, b = np.asarray(replay, dtype=float), np.asarray(stored, dtype=float)
    if a.shape != b.shape:
        raise ValueError("replayed and stored residuals have different shapes")
    if a.size % len(COMPONENT_NAMES):
        raise ValueError("residual length is not a multiple of four components")
    # 残差在磁盘上是扁平向量；这里只重排形状做逐分量定位，不做任何数值变换。
    a, b = a.reshape(-1, len(COMPONENT_NAMES)), b.reshape(-1, len(COMPONENT_NAMES))
    difference = a - b
    scale = np.maximum(np.abs(a), np.abs(b))
    relative = np.zeros_like(difference)
    np.divide(np.abs(difference), scale, out=relative, where=scale > 0.0)
    worst_flat = int(np.argmax(np.abs(difference)))
    worst_cell, worst_component = divmod(worst_flat, difference.shape[1])
    components = {
        name: {
            "maximum_absolute_difference": float(np.max(np.abs(difference[:, index]))),
            "rms_difference": float(np.sqrt(np.mean(difference[:, index] ** 2))),
            "maximum_stored_magnitude": float(np.max(np.abs(b[:, index]))),
            "maximum_replayed_magnitude": float(np.max(np.abs(a[:, index]))),
            "worst_cell": int(np.argmax(np.abs(difference[:, index]))),
        }
        for index, name in enumerate(COMPONENT_NAMES)
    }
    return {
        "finite": bool(np.all(np.isfinite(a)) and np.all(np.isfinite(b))),
        "l2_replayed": float(np.linalg.norm(a)),
        "l2_stored": float(np.linalg.norm(b)),
        "l2_difference": float(np.linalg.norm(difference)),
        "maximum_absolute_difference": float(np.max(np.abs(difference))),
        "maximum_relative_difference": float(np.max(relative)),
        "worst": {
            "cell": worst_cell,
            "component": COMPONENT_NAMES[worst_component],
            "component_index": worst_component,
            "replayed": float(a[worst_cell, worst_component]),
            "stored": float(b[worst_cell, worst_component]),
            "difference": float(difference[worst_cell, worst_component]),
        },
        "components": components,
        "exceedance_counts": {
            f"absolute_difference_above_{threshold:.0e}": int(np.count_nonzero(np.abs(difference) > threshold))
            for threshold in (0.0, 1e-16, 1e-15, 1e-13, 1e-12, 1e-11, 1e-9, 1e-6)
        },
        "difference_by_cell": difference.tolist(),
    }


def parity_verdict(replay: np.ndarray, stored: np.ndarray) -> dict[str, object]:
    """The original replay gate, kept as the last thing that runs."""
    passed = bool(np.allclose(replay, stored, rtol=RTOL, atol=ATOL))
    with np.errstate(invalid="ignore", divide="ignore"):
        allowed = ATOL + RTOL * np.abs(stored)
        worst = float(np.max(np.abs(replay - stored) / allowed))
    return {"rtol": RTOL, "atol": ATOL, "passed": passed,
            "worst_absolute_difference_over_allowed": worst,
            "definition": "allclose(replay, stored, rtol, atol)"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="new diagnostics directory under outputs/hpc")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    args = parser.parse_args()
    out = pipeline.safe_path(ROOT, args.run)
    if not out.is_relative_to(ROOT / "outputs/hpc"):
        raise ValueError("output must be a new directory under outputs/hpc")
    out.mkdir(parents=True, exist_ok=False)
    pipeline.write_json(out / "status.json", {"status": "running"})
    pipeline.write_json(out / "environment.json", runtime_fingerprint())
    claims: dict[str, dict] = {}

    def pin(path, expected: str | None = None) -> Path:
        path = Path(path)
        relative = path.relative_to(ROOT) if path.is_absolute() else path
        guarded = pipeline.safe_path(ROOT, str(relative))
        item = pipeline.claim(guarded)
        if expected is not None and item["sha256"] != expected:
            raise RuntimeError(f"artifact identity changed: {relative}")
        if claims.get(item["path"], item) != item:
            raise RuntimeError("input changed during diagnostics")
        claims[item["path"]] = item
        return guarded

    try:
        receipt = pipeline.read(pin(RECEIPT))
        package = pipeline.safe_path(ROOT, args.package)
        if str(package.relative_to(ROOT)) != receipt["package_prefix"]:
            raise RuntimeError("package directory is not the pinned one")
        pipeline.read(pin(package / "MANIFEST.json", receipt["manifest_sha256"]))
        for item in receipt["files"]:
            path = pin(package / item["path"], item["sha256"])
            if path.stat().st_size != item["size_bytes"]:
                raise RuntimeError("package member size mismatch")
        proto = pipeline.read(package / PROTOCOL)
        summary = pipeline.read(package / SUMMARY)
        if pipeline.sha256(package / PROTOCOL) != summary["protocol_sha256"]:
            raise RuntimeError("baseline protocol lineage mismatch")
        for name, item in proto["sources"].items():
            if item["path"].endswith(".dat"):
                continue
            if item["path"].startswith("outputs/"):
                pin(package / item["path"], item["sha256"])
            elif name == "mixed_frame_frequency":
                current = pin(item["path"])
                audit = pipeline.read(package / migration.AUDIT_PATH)
                pin(current, audit["current_frequency"]["sha256"])
                legacy = migration.reconstruct_legacy_frequency_source(current.read_text())
                if migration.sha256_bytes(legacy.encode()) != item["sha256"]:
                    raise RuntimeError("legacy frequency source cannot be reconstructed")
                parity = migration.positive_feedback_path_parity(legacy)
                if not all(row["array_equal"] for row in parity.values()):
                    raise RuntimeError("positive transfer path migration parity failed")
            else:
                pin(item["path"], item["sha256"])
        for path in (Path(__file__), Path(__file__).with_suffix(".sbatch"),
                     ROOT / "operations/replay_equation_baseline.py",
                     ROOT / "operations/conservative_residual_diagnostic.py",
                     ROOT / "operations/recover_equation_baseline.py",
                     ROOT / "diagnostics/material_energy_ledger.py",
                     ROOT / "scripts/phase7b9cy_refresh_feedback_worker_template.py"):
            pin(path)

        old = load_arrays(package / proto["sources"]["physical_old_time_level"]["path"])
        base = load_arrays(package / proto["sources"]["current_material_state"]["path"])
        encoded = np.load(package / proto["sources"]["encoded_material_state"]["path"],
                          allow_pickle=False)
        stored = np.load(package / summary["encoded_residual_path"], allow_pickle=False)
        target = load_arrays(package / summary["target_material_path"])
        phase, dt = int(base["phase_index"]), float(base["step_duration_s"])
        density = base["density_g_cm3"]
        codec = GroundStateLogSimplexCodec(len(density))
        old_temperature = old["temperature_k"][phase]
        old_hydrogen = old["hydrogen_fraction"][phase]
        old_helium = old["helium_fraction"][phase]

        feedback = load_arrays(
            pin(package / summary["final_feedback"]["feedback_artifact_path"],
                summary["final_feedback"]["feedback_artifact_sha256"]))
        response = frozen_radiation_material_response(
            density, old_temperature, old_hydrogen, old_helium, dt,
            feedback["half_photoionization_s1"],
            feedback["half_total_recombination_cm3_s"],
            feedback["half_atomic_rate_heating_erg_s_cm3"],
        )
        replayed = np.asarray(codec.encode(
            response.temperature_k, response.hydrogen_fraction, response.helium_fraction
        )) - encoded

        led = ledger(feedback, density, dt, old_temperature, old_hydrogen, old_helium)
        equation = equation_residual(codec, encoded, led["total_old"], led["gas_old"],
                                     led["radiative_energy"], led["new_h"], led["new_he"])
        recovered = recover_equation_residual(codec, encoded, stored, led["gas_old"])
        populations = {
            "hydrogen_maximum_absolute_difference": float(np.max(np.abs(
                led["new_h"] - response.hydrogen_fraction))),
            "helium_maximum_absolute_difference": float(np.max(np.abs(
                led["new_he"] - response.helium_fraction))),
            "temperature_replayed_maximum": float(np.max(np.abs(response.temperature_k))),
        }
        identities = {
            "target_equals_base_plus_stored_maximum_difference": float(np.max(np.abs(
                target["encoded_state"] - (encoded + stored)))),
            "stored_residual_l2": float(np.linalg.norm(stored)),
            "decode_roundtrip_maximum_difference": float(np.max(np.abs(
                codec.encode(base["temperature_k"], base["hydrogen_fraction"],
                             base["helium_fraction"]) - encoded))),
            "equation_versus_recovered_replay_maximum_difference": float(np.max(np.abs(
                equation - recovered))),
            "ledger_split_self_check": float(led["split_self_check"]),
            "nonphysical_response_cells": int(np.count_nonzero(led["remaining"] <= 0)),
        }
        difference = array_difference(replayed, stored)
        verdict = parity_verdict(replayed, stored)
        norms_stored = norms(stored.reshape(-1, len(COMPONENT_NAMES)), old["cell_mass_g_cm2"])
        result = {
            "classification": "read-only parity localization; no new radiation or acceptance",
            "package": str(package.relative_to(ROOT)),
            "physical_phase": phase,
            "physical_dt_s": dt,
            "environment": pipeline.read(out / "environment.json"),
            "identities": identities,
            "populations": populations,
            "stored_norms": norms_stored,
            "difference": difference,
            "verdict": verdict,
            "sources": list(claims.values()),
        }
        np.savez(out / "parity_arrays.npz", replayed=replayed, stored=stored,
                 difference=replayed - stored, encoded_base=encoded,
                 response_temperature_k=response.temperature_k,
                 response_hydrogen_fraction=response.hydrogen_fraction,
                 response_helium_fraction=response.helium_fraction)
        pipeline.write_json(out / "parity_debug.json", result)
        # 证据已经落盘，最后才执行原判定。
        if not verdict["passed"]:
            pipeline.write_json(out / "status.json", {
                "status": "parity_failed",
                "maximum_absolute_difference": difference["maximum_absolute_difference"],
                "l2_difference": difference["l2_difference"],
                "worst": difference["worst"],
            })
            raise SystemExit(2)
        pipeline.write_json(out / "status.json", {"status": "parity_passed"})
    except SystemExit:
        raise
    except Exception as exc:
        pipeline.write_json(out / "status.json", {"status": "failed", "error": str(exc)})
        raise


if __name__ == "__main__":
    main()
