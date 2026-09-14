"""Exhaust 后一键冻结双缓冲 streaming Anderson(1) 后备协议。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
from typing import Sequence

try:
    from scripts import phase7b9di_streaming_anderson_tail as streaming
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9di_streaming_anderson_tail as streaming  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _relative_under_outputs(value: str, *, allow_checkpoints: bool) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("preregistration paths must be safe repository-relative paths")
    if path.parts[0] != "outputs":
        raise ValueError("preregistration output must stay below outputs/")
    if not allow_checkpoints and len(path.parts) > 1 and path.parts[1] == "checkpoints":
        raise ValueError("small frozen protocol must not be written in checkpoints/")
    return str(path)


def preregister(
    root: Path,
    *,
    di_protocol_path: str,
    di_manifest_path: str,
    di_summary_path: str,
    protocol_output_path: str,
    phase_index: int,
    phase: str,
    classification: str,
) -> tuple[dict[str, object], str]:
    """Build and atomically write one small protocol; never open full-state claims."""
    di_protocol_path = _relative_under_outputs(
        di_protocol_path, allow_checkpoints=True
    )
    di_manifest_path = _relative_under_outputs(
        di_manifest_path, allow_checkpoints=True
    )
    di_summary_path = _relative_under_outputs(
        di_summary_path, allow_checkpoints=True
    )
    if any(
        PurePosixPath(value).suffix != ".json"
        for value in (di_protocol_path, di_manifest_path, di_summary_path)
    ):
        raise ValueError("di protocol/manifest/summary inputs must be JSON small files")
    output_relative = _relative_under_outputs(
        protocol_output_path, allow_checkpoints=False
    )
    output = root / output_relative
    stem = output.stem
    work_root = PurePosixPath("outputs/checkpoints") / f"{stem}_work"
    summary = PurePosixPath("outputs") / f"{stem}_candidate_summary.json"
    figure = PurePosixPath("outputs") / f"{stem}_candidate.png"
    spec = streaming.StreamingAndersonTailSpec(
        phase=phase,
        phase_index=phase_index,
        classification=classification,
        di_protocol_path=di_protocol_path,
        di_manifest_path=di_manifest_path,
        di_summary_path=di_summary_path,
        worker_path=streaming.RUNNER_RELATIVE_PATH,
        coefficient_report_directory=str(work_root / "pass1_coefficient_reports"),
        evaluation_report_directory=str(work_root / "pass2_evaluation_reports"),
        coefficient_manifest_path=str(work_root / "pass1_coefficient_manifest.json"),
        evaluation_manifest_path=str(work_root / "pass2_evaluation_manifest.json"),
        candidate_summary_path=str(summary),
        candidate_figure_path=str(figure),
    )
    payload = streaming.build_streaming_anderson_tail_protocol(root, spec)
    parent = payload["sources"].get("streaming_anderson_dry_pass_parent")
    if (
        not isinstance(parent, dict)
        or parent.get("path") != streaming.DRY_PASS_PARENT_RELATIVE_PATH
    ):
        raise RuntimeError("dry-pass parent was not frozen by the streaming builder")
    # 中文：协议正文只含小源哈希；两个 10 GiB 缓冲始终位于 runtime claims。
    if any(
        str(source["path"]).endswith(".dat")
        for source in payload["sources"].values()
    ):
        raise RuntimeError("builder attempted to pin a full-state file as a source")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, output)
    return payload, streaming._sha256(output)


def main(
    argv: Sequence[str] | None = None,
    *,
    root: Path = ROOT,
) -> str:
    parser = argparse.ArgumentParser()
    parser.add_argument("--di-protocol", required=True)
    parser.add_argument("--di-manifest", required=True)
    parser.add_argument("--di-summary", required=True)
    parser.add_argument("--protocol-output", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument(
        "--phase",
        default="7B9di exhausted-tail two-pass streaming Anderson(1)",
    )
    parser.add_argument(
        "--classification",
        default=(
            "[A-preregistered]+[V-lineage]+[O]：仅在 7B9di 24-map progression "
            "耗尽且未收敛后，执行两遍只读 dry map、受保护候选提交及一次 fresh map。"
        ),
    )
    args = parser.parse_args(argv)
    _, digest = preregister(
        root,
        di_protocol_path=args.di_protocol,
        di_manifest_path=args.di_manifest,
        di_summary_path=args.di_summary,
        protocol_output_path=args.protocol_output,
        phase_index=args.phase_index,
        phase=args.phase,
        classification=args.classification,
    )
    print(digest)
    return digest


if __name__ == "__main__":
    main()
