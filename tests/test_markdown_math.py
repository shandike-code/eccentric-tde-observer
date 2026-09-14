from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "normalize_markdown_math.py"


def _load_normalizer():
    spec = importlib.util.spec_from_file_location("normalize_markdown_math", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_math_is_normalized_for_obsidian() -> None:
    normalizer = _load_normalizer()
    changed = []
    for path in normalizer.markdown_files():
        text = path.read_text(encoding="utf-8")
        if normalizer.normalize_document(text) != text:
            changed.append(path.relative_to(ROOT).as_posix())
    assert changed == []


def test_normalizer_handles_greek_and_compound_subscripts() -> None:
    normalizer = _load_normalizer()
    source = "$Sigma, T_eff, F_nu_obs, tau_star$"
    expected = r"$\Sigma, T_{\rm eff}, F_{\nu,\rm obs}, \tau_{\rm star}$"
    assert normalizer.normalize_document(source) == expected


def test_markdown_contains_no_hidden_control_characters() -> None:
    normalizer = _load_normalizer()
    failures = []
    for path in normalizer.markdown_files():
        invalid = [
            value
            for value in path.read_bytes()
            if value < 32 and value != 10
        ]
        if invalid:
            failures.append(
                (path.relative_to(ROOT).as_posix(), sorted(set(invalid)))
            )
    assert failures == []
