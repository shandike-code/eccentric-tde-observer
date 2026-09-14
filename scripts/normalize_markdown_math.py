"""规范项目 Markdown 数学片段中的希腊字母和复合下标。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_ROOTS = (ROOT / "README.md", ROOT / "docs", ROOT / "lecture")

GREEK = {
    "Gamma": r"\Gamma",
    "Delta": r"\Delta",
    "Theta": r"\Theta",
    "Lambda": r"\Lambda",
    "Xi": r"\Xi",
    "Pi": r"\Pi",
    "Phi": r"\Phi",
    "Psi": r"\Psi",
    "Sigma": r"\Sigma",
    "Omega": r"\Omega",
    "alpha": r"\alpha",
    "beta": r"\beta",
    "gamma": r"\gamma",
    "delta": r"\delta",
    "epsilon": r"\epsilon",
    "eta": r"\eta",
    "theta": r"\theta",
    "iota": r"\iota",
    "kappa": r"\kappa",
    "lambda": r"\lambda",
    "mu": r"\mu",
    "nu": r"\nu",
    "xi": r"\xi",
    "omega": r"\omega",
    "phi": r"\phi",
    "pi": r"\pi",
    "rho": r"\rho",
    "sigma": r"\sigma",
    "tau": r"\tau",
    "upsilon": r"\upsilon",
    "varpi": r"\varpi",
    "chi": r"\chi",
    "psi": r"\psi",
    "zeta": r"\zeta",
}

COMPOSITE_SUFFIXES = ("isotropic", "shift", "min", "max", "0", "P", "G")


def _render_subscript(content: str) -> str:
    """渲染一个简单下标；逗号只在已经成组的 ``_{...}`` 内解释。"""
    parts = content.split(",")
    rendered = []
    for part in parts:
        part = part.strip()
        if part in GREEK:
            rendered.append(GREEK[part])
        elif part.startswith("\\") or not part.isalnum():
            rendered.append(part)
        elif len(part) == 1 and part.islower():
            rendered.append(part)
        elif part.isdigit():
            rendered.append(part)
        else:
            rendered.append(rf"\rm {part}")
    return "_{" + ",".join(rendered) + "}"


def _format_subscript(match: re.Match[str]) -> str:
    return _render_subscript(match.group(1))


def normalize_math(math: str) -> str:
    """只改写数学定界符内部，不触碰普通正文或代码片段。"""
    result = math
    result = re.sub(r"\bproportional\s+to\b", r"\\propto", result)
    result = re.sub(r"(?<![A-Za-z])m0(?![A-Za-z0-9])", r"m_{0}", result)
    greek_names = "|".join(sorted(GREEK, key=len, reverse=True))
    result = re.sub(
        rf"(?<![\\A-Za-z])d({greek_names})(?=$|[^A-Za-z])",
        lambda match: r"\mathrm d" + GREEK[match.group(1)],
        result,
    )
    for plain, latex in (
        ("integral", r"\int"),
        ("infinity", r"\infty"),
        ("sqrt", r"\sqrt"),
        ("cos", r"\cos"),
        ("sin", r"\sin"),
        ("exp", r"\exp"),
    ):
        result = re.sub(
            rf"(?<![\\A-Za-z]){plain}(?=$|[^A-Za-z])",
            lambda _: latex,
            result,
        )
    for plain, latex in GREEK.items():
        result = re.sub(
            rf"(?<![\\A-Za-z]){plain}(?=$|[^A-Za-z])",
            lambda _, value=latex: value,
            result,
        )
    # 先规范已有的简单成组下标，例如 T_{eff} 和 F_{nu,obs}。
    result = re.sub(r"_\{([^{}]+)\}", _format_subscript, result)
    suffixes = "|".join(COMPOSITE_SUFFIXES)
    result = re.sub(
        rf"_\{{([^{{}}]+)\}},({suffixes})(?=$|[^A-Za-z0-9])",
        lambda match: _render_subscript(f"{match.group(1)},{match.group(2)}"),
        result,
    )
    # 处理 F_\nu,shift 这一类整体下标，再处理单个命令下标。
    result = re.sub(
        rf"_(\\[A-Za-z]+),({suffixes})(?=$|[^A-Za-z0-9])",
        lambda match: _render_subscript(f"{match.group(1)},{match.group(2)}"),
        result,
    )
    result = re.sub(
        r"_(\\[A-Za-z]+)_([A-Za-z0-9]+)",
        lambda match: _render_subscript(f"{match.group(1)},{match.group(2)}"),
        result,
    )
    result = re.sub(
        r"_(\\mathrm\{[^{}]+\}|\\[A-Za-z]+)",
        lambda match: "_{" + match.group(1) + "}",
        result,
    )
    # 未成组下标只读取紧邻的一个 token，绝不吞掉变量间的逗号。
    result = re.sub(
        r"_(?!\{)([A-Za-z0-9]+)",
        _format_subscript,
        result,
    )
    result = result.replace(" dot ", r" \cdot ")
    result = result.replace(" cross ", r" \times ")
    result = result.replace("*", r"\,")
    result = result.replace(">=", r"\ge")
    result = result.replace("<=", r"\le")
    result = result.replace("->", r"\to")
    result = result.replace("<<", r"\ll")
    result = re.sub(r"(?<=\d)\s*deg\b", lambda _: r"^\circ", result)
    return result


INLINE_MATH = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$")
CODE_SPAN = re.compile(r"(`+)(.*?)(\1)")


def normalize_document(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    fenced = False
    display = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            output.append(line)
            continue
        if fenced:
            output.append(line)
            continue
        if stripped.startswith("$$"):
            display = not display
            output.append(line)
            continue
        if display:
            output.append(normalize_math(line))
            continue
        chunks: list[str] = []
        cursor = 0
        for code_match in CODE_SPAN.finditer(line):
            plain = line[cursor : code_match.start()]
            chunks.append(
                INLINE_MATH.sub(lambda match: "$" + normalize_math(match.group(1)) + "$", plain)
            )
            chunks.append(code_match.group(0))
            cursor = code_match.end()
        plain = line[cursor:]
        chunks.append(
            INLINE_MATH.sub(lambda match: "$" + normalize_math(match.group(1)) + "$", plain)
        )
        output.append("".join(chunks))
    return "".join(output)


def markdown_files() -> list[Path]:
    files = [MARKDOWN_ROOTS[0]]
    for directory in MARKDOWN_ROOTS[1:]:
        files.extend(sorted(directory.rglob("*.md")))
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changed = []
    for path in markdown_files():
        original = path.read_text(encoding="utf-8")
        normalized = normalize_document(original)
        if normalized == original:
            continue
        changed.append(path.relative_to(ROOT).as_posix())
        if args.write:
            path.write_text(normalized, encoding="utf-8")
    for path in changed:
        print(path)
    if changed and not args.write:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
