"""Phase 7B9dp：仅用小型 streaming 证据预注册 pure-Picard 续算。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9dp_post_streaming_picard as continuation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9dp_post_streaming_picard as continuation  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _json_path(value: str, *, protocol_output: bool = False) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "outputs"
        or path.suffix.lower() != ".json"
        or (
            protocol_output
            and len(path.parts) > 1
            and path.parts[1] == "checkpoints"
        )
    ):
        raise ValueError("7B9dp JSON path must be safe and repository-relative")
    return str(path)


def _transient_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.parts[:2] != ("outputs", "checkpoints")
        or "transient" not in path.name
    ):
        raise ValueError("7B9dp transient path must be stage-owned below checkpoints")
    return str(path)


def preregister(
    root: Path,
    *,
    spec: continuation.PostStreamingPicardSpec,
    output_path: str,
) -> tuple[dict[str, object], str]:
    output = root / _json_path(output_path, protocol_output=True)
    return continuation.write_protocol(root, spec, output)


def main(
    argv: list[str] | None = None, *, root: Path = ROOT
) -> tuple[dict[str, object], str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--prior-protocol", required=True)
    parser.add_argument("--prior-pass1-manifest", required=True)
    parser.add_argument("--prior-pass2-manifest", required=True)
    parser.add_argument("--prior-candidate-commit-manifest", required=True)
    parser.add_argument("--prior-fresh-manifest", required=True)
    parser.add_argument("--prior-fresh-summary", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--transient-report-directory", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    figure = PurePosixPath(args.figure)
    if (
        figure.is_absolute()
        or ".." in figure.parts
        or not figure.parts
        or figure.parts[0] != "outputs"
        or figure.suffix.lower() != ".png"
    ):
        raise ValueError("7B9dp figure path must be a safe PNG below outputs")
    spec = continuation.PostStreamingPicardSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        prior_protocol_path=_json_path(args.prior_protocol),
        prior_pass1_manifest_path=_json_path(args.prior_pass1_manifest),
        prior_pass2_manifest_path=_json_path(args.prior_pass2_manifest),
        prior_candidate_commit_manifest_path=_json_path(
            args.prior_candidate_commit_manifest
        ),
        prior_fresh_manifest_path=_json_path(args.prior_fresh_manifest),
        prior_fresh_summary_path=_json_path(args.prior_fresh_summary),
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        manifest_path=_json_path(args.manifest),
        transient_report_directory=_transient_path(
            args.transient_report_directory
        ),
        summary_path=_json_path(args.summary),
        figure_path=str(figure),
    )
    payload, digest = preregister(root, spec=spec, output_path=args.output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return payload, digest


if __name__ == "__main__":
    main()
