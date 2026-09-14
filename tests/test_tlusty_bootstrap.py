from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_tlusty208_hhe.py"


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("bootstrap_tlusty208_hhe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dimension_patch_ignores_fixed_format_comment() -> None:
    bootstrap = _load_bootstrap()
    source = (
        "      PARAMETER (MFRTAB = 125000,\n"
        "C     *           MFRTAB = 3,\n"
        "     *           MTABT = 21)\n"
    )
    updated = bootstrap._replace_integer_parameter(source, "MFRTAB", 3)
    assert "PARAMETER (MFRTAB = 3," in updated
    assert "C     *           MFRTAB = 3," in updated


def test_official_archive_hash_is_fixed() -> None:
    bootstrap = _load_bootstrap()
    assert bootstrap.PACKAGE_SHA256 == (
        "ec9febdc1795f2c1bbe948ea1736bed663aac9238b290483b517201132f85e4a"
    )
