"""Phase 7B9cy：审计并刷新正式反馈 worker 的单一源码依赖。"""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import types

import numpy as np

from eccentric_tde_observer import mixed_frame_frequency as current_frequency


ROOT = Path(__file__).resolve().parents[1]
LEGACY_TEMPLATE = "outputs/phase7b7j_preregistered_second_assembled_feedback.json"
CURRENT_FREQUENCY = "src/eccentric_tde_observer/mixed_frame_frequency.py"
AUDIT_PATH = "outputs/phase7b9cy_feedback_dependency_migration_audit.json"
TEMPLATE_PATH = "outputs/phase7b9cy_refreshed_feedback_worker_template.json"
BUILDER_PATH = "scripts/phase7b9cy_refresh_feedback_worker_template.py"
LEGACY_FREQUENCY_SIZE = 59_584
LEGACY_FREQUENCY_SHA256 = (
    "363c179e8aae73ea74f9ed15c17c24a6efc84be580ac37436ec7a6b85a4dc08c"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source_entry(relative_path: str) -> dict[str, object]:
    path = ROOT / relative_path
    return {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def reconstruct_legacy_frequency_source(current_source: str) -> str:
    """精确反向移除 signed-ALI 扩展，重建旧 7B7j 冻结源码。"""
    source = current_source.replace(
        """            upper,\n            allow_signed_density=allow_signed_density,\n        )""",
        """            upper,\n        )""",
        1,
    )
    source = source.replace(
        """    upper: NDArray[np.float64],\n    *,\n    allow_signed_density: bool = False,\n) -> NDArray[np.float64]:\n    \"\"\"按局域交叠顺序批量积分，不依赖源频率切片的累计起点。\"\"\"""",
        """    upper: NDArray[np.float64],\n) -> NDArray[np.float64]:\n    \"\"\"按局域交叠顺序批量积分，不依赖源频率切片的累计起点。\"\"\"""",
        1,
    )
    source = source.replace(
        """    if not np.all(np.isfinite(result)) or (\n        not allow_signed_density and np.any(result < 0.0)\n    ):\n        raise ArithmeticError(\"local-overlap frequency integral became invalid\")""",
        """    if not np.all(np.isfinite(result)) or np.any(result < 0.0):\n        raise ArithmeticError(\"local-overlap frequency integral became invalid\")""",
        1,
    )
    patterns = (
        r"\n\ndef lorentz_remap_signed_group_intensity_perturbation\(.*?"
        r"\n    \)\n(?=\n\ndef lorentz_remap_comoving_group_emissivity_to_lab)",
        r"\n\ndef lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab\(.*?"
        r"\n    \)\n(?=\n\ndef lorentz_remap_comoving_group_extinction_to_lab)",
    )
    for pattern in patterns:
        source, count = re.subn(pattern, "", source, count=1, flags=re.S)
        if count != 1:
            raise RuntimeError("signed-ALI extension no longer matches migration audit")
    return source


def _legacy_module(source: str) -> types.ModuleType:
    name = "eccentric_tde_observer._phase7b9cy_legacy_mixed_frame_frequency"
    module = types.ModuleType(name)
    module.__file__ = "<phase7b9cy reconstructed legacy source>"
    module.__package__ = "eccentric_tde_observer"
    sys.modules[name] = module
    try:
        exec(compile(source, module.__file__, "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def positive_feedback_path_parity(legacy_source: str) -> dict[str, object]:
    """比较反馈实际调用的正强度共动变换；不测试新增 signed API。"""
    legacy = _legacy_module(legacy_source)
    try:
        mu, weight = np.polynomial.legendre.leggauss(12)
        beta = np.asarray([0.08, -0.03], dtype=np.float64)
        source_edge = np.geomspace(0.5, 4.0, 97)
        target_edge = np.geomspace(0.8, 2.5, 49)
        rng = np.random.default_rng(20260902)
        intensity = 0.2 + rng.random((96, 12, 2))
        legacy_result = legacy.comoving_group_radiation(
            intensity, source_edge, target_edge, mu, weight, beta
        )
        current_result = current_frequency.comoving_group_radiation(
            intensity, source_edge, target_edge, mu, weight, beta
        )
        arrays = {
            "angle_intensity_density": (
                legacy_result.angle_intensity_density,
                current_result.angle_intensity_density,
            ),
            "mean_intensity_density": (
                legacy_result.mean_intensity_density,
                current_result.mean_intensity_density,
            ),
            "comoving_angular_measure": (
                legacy_result.comoving_angular_measure,
                current_result.comoving_angular_measure,
            ),
        }
        return {
            name: {
                "array_equal": bool(np.array_equal(old, new)),
                "maximum_absolute_difference": float(np.max(np.abs(old - new))),
            }
            for name, (old, new) in arrays.items()
        }
    finally:
        sys.modules.pop(legacy.__name__, None)


def signed_api_references() -> dict[str, list[str]]:
    """静态确认反馈 worker 栈没有引用新增的 signed-ALI API。"""
    paths = (
        "scripts/phase7b7j_second_assembled_feedback.py",
        "scripts/phase7b7f_assembled_diagnostics.py",
        "scripts/phase7b7g_assembled_atomic_rates.py",
        "scripts/phase7b7e_radiation_direction.py",
        "scripts/phase7b5x_full_depth_block_probe.py",
    )
    references: dict[str, list[str]] = {}
    for relative in paths:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        names = sorted(
            {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id.startswith("lorentz_remap_signed")
            }
            | {
                node.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
                and node.attr.startswith("lorentz_remap_signed")
            }
        )
        references[relative] = names
    return references


def build_outputs() -> tuple[dict[str, object], dict[str, object]]:
    legacy_template = json.loads((ROOT / LEGACY_TEMPLATE).read_text(encoding="utf-8"))
    frozen_frequency = legacy_template["sources"]["mixed_frame_frequency"]
    if (
        frozen_frequency.get("sha256") != LEGACY_FREQUENCY_SHA256
        or int(frozen_frequency.get("size_bytes", LEGACY_FREQUENCY_SIZE))
        != LEGACY_FREQUENCY_SIZE
    ):
        raise RuntimeError("legacy feedback template frequency source changed")
    current_path = ROOT / CURRENT_FREQUENCY
    current_source = current_path.read_text(encoding="utf-8")
    legacy_source = reconstruct_legacy_frequency_source(current_source)
    reconstructed = legacy_source.encode("utf-8")
    if (
        len(reconstructed) != LEGACY_FREQUENCY_SIZE
        or sha256_bytes(reconstructed) != LEGACY_FREQUENCY_SHA256
    ):
        raise RuntimeError("exact legacy mixed-frame source reconstruction failed")
    parity = positive_feedback_path_parity(legacy_source)
    references = signed_api_references()
    if (
        not all(row["array_equal"] for row in parity.values())
        or any(references.values())
    ):
        raise RuntimeError("positive feedback path changed across signed-ALI extension")
    replaced = {
        "mapped_radiation_state",
        "second_material_iterate",
        "physical_old_time_level",
        "mixed_frame_frequency",
    }
    for name, source in legacy_template["sources"].items():
        if name in replaced:
            continue
        if sha256(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError(f"unchanged legacy feedback dependency drifted: {name}")
    audit = {
        "phase": "7B9cy formal-feedback dependency migration audit",
        "classification": "[V-code-path]+[O]",
        "legacy_template_path": LEGACY_TEMPLATE,
        "legacy_frequency": {
            "path": CURRENT_FREQUENCY,
            "size_bytes": LEGACY_FREQUENCY_SIZE,
            "sha256": LEGACY_FREQUENCY_SHA256,
            "exactly_reconstructed_in_memory": True,
            "reconstructed_source_written_to_disk": False,
        },
        "current_frequency": source_entry(CURRENT_FREQUENCY),
        "delta_scope": {
            "added_signed_ali_interfaces": [
                "lorentz_remap_signed_group_intensity_perturbation",
                "lorentz_remap_signed_comoving_group_emissivity_perturbation_to_lab",
            ],
            "physical_positive_path_allow_signed_density": False,
            "feedback_worker_signed_api_references": references,
        },
        "positive_path_parity": parity,
        "decision": {
            "legacy_hash_exactly_reconstructed": True,
            "feedback_positive_path_array_equal": True,
            "refresh_worker_template_authorized": True,
            "material_update_authorized": False,
            "dynamic_nlte_solution_accepted": False,
        },
    }
    write_json_atomic(ROOT / AUDIT_PATH, audit)
    template = deepcopy(legacy_template)
    template["phase"] = "7B9cy refreshed formal-feedback worker template"
    template["protocol_version"] = 2
    template["classification"] = (
        "[V-code-path] legacy source is exactly reconstructed and the positive "
        "feedback path is array-identical; [O] dynamic NLTE remains unaccepted"
    )
    template["sources"]["mixed_frame_frequency"] = source_entry(CURRENT_FREQUENCY)
    template["sources"]["phase7b9cy_migration_audit"] = source_entry(AUDIT_PATH)
    template["sources"]["phase7b9cy_builder"] = source_entry(BUILDER_PATH)
    template["dependency_migration"] = {
        "legacy_frequency_sha256": LEGACY_FREQUENCY_SHA256,
        "current_frequency_sha256": template["sources"]["mixed_frame_frequency"][
            "sha256"
        ],
        "positive_feedback_path_array_equal": True,
        "signed_ali_interfaces_used_by_feedback": False,
        "scientific_gate_changed": False,
    }
    write_json_atomic(ROOT / TEMPLATE_PATH, template)
    return audit, template


def main() -> None:
    build_outputs()
    print(
        json.dumps(
            {
                "audit_sha256": sha256(ROOT / AUDIT_PATH),
                "template_sha256": sha256(ROOT / TEMPLATE_PATH),
            }
        )
    )


if __name__ == "__main__":
    main()
