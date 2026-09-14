"""Phase 7B9du：从 exhausted dp 小证据原子预注册 pure-Picard 续算。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9du_exhausted_dp_picard_continuation as continuation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9du_exhausted_dp_picard_continuation as continuation  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _json_path(value: str, *, protocol_output: bool = False) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "outputs"
        or path.suffix.lower() != ".json"
    ):
        raise ValueError("7B9du JSON path must be safe and repository-relative")
    if protocol_output and len(path.parts) > 1 and path.parts[1] == "checkpoints":
        raise ValueError("7B9du frozen protocol cannot be written below checkpoints")
    return str(path)


def _transient_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.parts[:2] != ("outputs", "checkpoints")
        or "transient" not in path.name
    ):
        raise ValueError("7B9du transient path must be stage-owned below checkpoints")
    return str(path)


def _figure_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "outputs"
        or path.suffix.lower() != ".png"
        or (len(path.parts) > 1 and path.parts[1] == "checkpoints")
    ):
        raise ValueError("7B9du figure must be a safe PNG below outputs")
    return str(path)


def main(
    argv: list[str] | None = None, *, root: Path = ROOT
) -> tuple[dict[str, object], str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--dp-protocol", required=True)
    parser.add_argument("--dp-manifest", required=True)
    parser.add_argument("--dp-summary", required=True)
    parser.add_argument("--additional-map-horizon", required=True, type=int)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--transient-report-directory", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    spec = continuation.ExhaustedDpPicardContinuationSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        dp_protocol_path=_json_path(args.dp_protocol),
        dp_manifest_path=_json_path(args.dp_manifest),
        dp_summary_path=_json_path(args.dp_summary),
        additional_map_horizon=args.additional_map_horizon,
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        preregister_path=continuation.PREREGISTER_RELATIVE_PATH,
        manifest_path=_json_path(args.manifest),
        transient_report_directory=_transient_path(
            args.transient_report_directory
        ),
        summary_path=_json_path(args.summary, protocol_output=True),
        figure_path=_figure_path(args.figure),
    )
    output = root / _json_path(args.output, protocol_output=True)
    payload, digest = continuation.write_protocol(root, spec, output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return payload, digest


if __name__ == "__main__":
    main()
