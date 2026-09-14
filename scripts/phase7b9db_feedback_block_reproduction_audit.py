"""Phase 7B9db：审计正式反馈 previous/block49 的单块瞬态异常。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CZ_PROTOCOL = "outputs/phase7b9cz_preregistered_formal_feedback_pair.json"
DA_PROTOCOL = "outputs/phase7b9da_preregistered_formal_feedback_pair.json"
CZ_WORK = "outputs/checkpoints/phase7b9cz_formal_feedback_pair"
DA_WORK = "outputs/checkpoints/phase7b9da_formal_feedback_pair"
RERUN_PARTIAL = (
    "outputs/checkpoints/phase7b9db_block49_reproduction/previous_block49.npz"
)
RERUN_REPORT = (
    "outputs/checkpoints/phase7b9db_block49_reproduction/previous_block49.json"
)
OUTPUT = "outputs/phase7b9db_feedback_block_reproduction_audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _manifest(work: str, label: str) -> tuple[str, dict[str, object]]:
    relative = f"{work}/{label}_manifest.json"
    return relative, json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _partial_hashes(manifest: dict[str, object]) -> dict[int, str]:
    return {
        int(row["block_index"]): str(row["partial_sha256"])
        for row in manifest["completed_blocks"]
    }


def _array_differences(first: Path, second: Path) -> dict[str, dict[str, object]]:
    differences: dict[str, dict[str, object]] = {}
    with np.load(first) as left, np.load(second) as right:
        if left.files != right.files:
            raise RuntimeError("formal feedback partial array keys changed")
        for name in left.files:
            a = np.asarray(left[name])
            b = np.asarray(right[name])
            if np.array_equal(a, b):
                continue
            differences[name] = {
                "different_element_count": int(np.count_nonzero(a != b)),
                "maximum_absolute_difference": float(np.max(np.abs(a - b))),
            }
    return differences


def build_audit() -> dict[str, object]:
    cz_protocol = json.loads((ROOT / CZ_PROTOCOL).read_text(encoding="utf-8"))
    da_protocol = json.loads((ROOT / DA_PROTOCOL).read_text(encoding="utf-8"))
    for key in ("previous_radiation", "final_radiation"):
        if cz_protocol["sources"][key] != da_protocol["sources"][key]:
            raise RuntimeError("formal feedback protocols use different radiation states")
    manifests: dict[str, dict[str, dict[str, object]]] = {"cz": {}, "da": {}}
    manifest_paths: dict[str, dict[str, str]] = {"cz": {}, "da": {}}
    for run, work in (("cz", CZ_WORK), ("da", DA_WORK)):
        for label in ("previous", "final"):
            relative, payload = _manifest(work, label)
            manifests[run][label] = payload
            manifest_paths[run][label] = relative
    if (
        manifests["cz"]["previous"].get("status") != "complete"
        or manifests["cz"]["previous"].get("state_gate_passed") is not True
        or manifests["cz"]["final"].get("status") != "complete"
        or manifests["cz"]["final"].get("state_gate_passed") is not True
        or manifests["da"]["previous"].get("status") != "gate_failed"
        or manifests["da"]["previous"].get("state_gate_passed") is not False
        or manifests["da"]["final"].get("status") != "complete"
        or manifests["da"]["final"].get("state_gate_passed") is not True
    ):
        raise RuntimeError("formal feedback reproduction statuses changed")
    comparison: dict[str, object] = {}
    for label in ("previous", "final"):
        cz_hash = _partial_hashes(manifests["cz"][label])
        da_hash = _partial_hashes(manifests["da"][label])
        if sorted(cz_hash) != list(range(76)) or sorted(da_hash) != list(range(76)):
            raise RuntimeError("formal feedback block ownership changed")
        differing = [index for index in range(76) if cz_hash[index] != da_hash[index]]
        comparison[label] = {
            "byte_identical_block_count": 76 - len(differing),
            "differing_block_indices": differing,
            "feedback_artifact_byte_identical": (
                manifests["cz"][label].get("feedback_artifact_sha256")
                == manifests["da"][label].get("feedback_artifact_sha256")
            ),
        }
    if (
        comparison["previous"]["differing_block_indices"] != [49]
        or comparison["final"]["differing_block_indices"] != []
    ):
        raise RuntimeError("formal feedback anomaly is no longer isolated to previous/block49")
    cz_block = ROOT / f"{CZ_WORK}/previous/block49.npz"
    da_block = ROOT / f"{DA_WORK}/previous/block49.npz"
    rerun = ROOT / RERUN_PARTIAL
    rerun_report = json.loads((ROOT / RERUN_REPORT).read_text(encoding="utf-8"))
    if (
        int(rerun_report.get("block_index", -1)) != 49
        or sha256(rerun) != sha256(cz_block)
        or sha256(rerun) == sha256(da_block)
    ):
        raise RuntimeError("independent previous/block49 reproduction changed")
    affected = _array_differences(cz_block, da_block)
    if set(affected) != {
        "absorbed_power_erg_s_cm3",
        "atomic_rate_heating_erg_s_cm3",
    }:
        raise RuntimeError("unexpected arrays differ in previous/block49")
    audit = {
        "phase": "7B9db formal-feedback previous/block49 reproduction audit",
        "classification": "[V-reproduction]+[O]",
        "sources": {
            "phase7b9cz_protocol": source(CZ_PROTOCOL),
            "phase7b9da_protocol": source(DA_PROTOCOL),
            "phase7b9cz_previous_manifest": source(
                manifest_paths["cz"]["previous"]
            ),
            "phase7b9cz_final_manifest": source(manifest_paths["cz"]["final"]),
            "phase7b9da_previous_manifest": source(
                manifest_paths["da"]["previous"]
            ),
            "phase7b9da_final_manifest": source(manifest_paths["da"]["final"]),
            "phase7b9cz_previous_block49": source(
                f"{CZ_WORK}/previous/block49.npz"
            ),
            "phase7b9da_previous_block49": source(
                f"{DA_WORK}/previous/block49.npz"
            ),
            "independent_previous_block49": source(RERUN_PARTIAL),
            "independent_previous_block49_report": source(RERUN_REPORT),
        },
        "block_comparison": comparison,
        "previous_block49_affected_arrays": affected,
        "decision": {
            "single_block_transient_reproduced": True,
            "independent_rerun_matches_passed_phase7b9cz_bytes": True,
            "phase7b9cz_formal_feedback_artifacts_reusable": True,
            "material_update_authorized": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }
    write_json_atomic(ROOT / OUTPUT, audit)
    return audit


def main() -> None:
    build_audit()
    print(sha256(ROOT / OUTPUT))


if __name__ == "__main__":
    main()
