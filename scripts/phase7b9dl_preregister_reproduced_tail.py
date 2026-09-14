"""Phase 7B9dl：用小文件预注册 dk reproduction 后的 maps 21..23。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9dl_reproduced_tail_continuation as continuation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9dl_reproduced_tail_continuation as continuation  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _json_path(value: str, *, output: bool = False) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "outputs"
        or path.suffix != ".json"
        or (output and len(path.parts) > 1 and path.parts[1] == "checkpoints")
    ):
        raise ValueError("7B9dl JSON paths must be safe repository-relative outputs paths")
    return str(path)


def preregister(
    root: Path,
    *,
    spec: continuation.ReproducedTailContinuationSpec,
    output_path: str,
) -> tuple[dict[str, object], str]:
    output = root / _json_path(output_path, output=True)
    return continuation.write_protocol(root, spec, output)


def main(
    argv: list[str] | None = None, *, root: Path = ROOT
) -> tuple[dict[str, object], str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument("--classification", required=True)
    for name in (
        "di-protocol",
        "di-manifest",
        "di-summary",
        "dk-protocol",
        "dk-manifest",
        "dk-summary",
    ):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--transient-report-directory", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--fresh-current-sha256", required=True)
    parser.add_argument("--immutable-scratch-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    spec = continuation.ReproducedTailContinuationSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        di_protocol_path=_json_path(args.di_protocol),
        di_manifest_path=_json_path(args.di_manifest),
        di_summary_path=_json_path(args.di_summary),
        dk_protocol_path=_json_path(args.dk_protocol),
        dk_manifest_path=_json_path(args.dk_manifest),
        dk_summary_path=_json_path(args.dk_summary),
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        manifest_path=_json_path(args.manifest),
        transient_report_directory=args.transient_report_directory,
        summary_path=_json_path(args.summary),
        figure_path=args.figure,
        fresh_current_sha256=args.fresh_current_sha256,
        immutable_scratch_sha256=args.immutable_scratch_sha256,
    )
    payload, digest = preregister(root, spec=spec, output_path=args.output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return payload, digest


if __name__ == "__main__":
    main()
