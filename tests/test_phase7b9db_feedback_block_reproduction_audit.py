"""Phase 7B9db 单块复现审计回归。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/phase7b9db_feedback_block_reproduction_audit.py"
SPEC = importlib.util.spec_from_file_location("phase7b9db_audit", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not import Phase 7B9db audit")
audit_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_module
SPEC.loader.exec_module(audit_module)


def test_single_block_reproduction_is_exact_and_isolated() -> None:
    audit = audit_module.build_audit()
    assert audit["block_comparison"]["previous"]["differing_block_indices"] == [49]
    assert audit["block_comparison"]["previous"]["byte_identical_block_count"] == 75
    assert audit["block_comparison"]["final"]["byte_identical_block_count"] == 76
    assert set(audit["previous_block49_affected_arrays"]) == {
        "absorbed_power_erg_s_cm3",
        "atomic_rate_heating_erg_s_cm3",
    }
    assert audit["decision"][
        "independent_rerun_matches_passed_phase7b9cz_bytes"
    ]
