"""Phase 7B9dq：从 provisional_pause 小证据原子预注册反馈抽取。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9_provisional_feedback as provisional
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_provisional_feedback as provisional  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_RUNNER = provisional.PAUSED_ADAPTER_RELATIVE_PATH


def _safe_path(
    value: str,
    *,
    suffix: str | None = None,
    below_checkpoints: bool = False,
    output_protocol: bool = False,
) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("7B9dq path must be repository-relative")
    if suffix is not None and path.suffix.lower() != suffix:
        raise ValueError(f"7B9dq path must end in {suffix}")
    if below_checkpoints:
        if path.parts[:2] != ("outputs", "checkpoints") or "provisional" not in path.name:
            raise ValueError("7B9dq work directory must be provisional and below checkpoints")
    elif path.parts[0] not in {"outputs", "scripts"}:
        raise ValueError("7B9dq path must be below outputs or scripts")
    if output_protocol and (
        path.parts[0] != "outputs"
        or (len(path.parts) > 1 and path.parts[1] == "checkpoints")
    ):
        raise ValueError("7B9dq protocol output must be a small JSON below outputs")
    if path.suffix.lower() == ".dat":
        raise ValueError("7B9dq refuses .dat source arguments")
    return str(path)


def preregister(
    root: Path,
    *,
    spec: provisional.PausedProvisionalFeedbackProtocolSpec,
    output_path: str,
) -> tuple[dict[str, object], str]:
    output = root / _safe_path(
        output_path, suffix=".json", output_protocol=True
    )
    return provisional.write_paused_provisional_feedback_protocol(
        root, spec, output
    )


def main(
    argv: list[str] | None = None,
    *,
    root: Path = ROOT,
) -> tuple[dict[str, object], str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--continuation-protocol", required=True)
    parser.add_argument("--continuation-manifest", required=True)
    parser.add_argument("--continuation-summary", required=True)
    parser.add_argument("--material-protocol", required=True)
    parser.add_argument("--material-summary", required=True)
    parser.add_argument("--material", required=True)
    parser.add_argument("--physical-old-time-level", required=True)
    parser.add_argument("--phase7b7j-protocol", required=True)
    parser.add_argument("--feedback-work-directory", required=True)
    parser.add_argument("--feedback-output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    spec = provisional.PausedProvisionalFeedbackProtocolSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        continuation_protocol_path=_safe_path(
            args.continuation_protocol, suffix=".json"
        ),
        continuation_manifest_path=_safe_path(
            args.continuation_manifest, suffix=".json"
        ),
        continuation_summary_path=_safe_path(
            args.continuation_summary, suffix=".json"
        ),
        material_protocol_path=_safe_path(args.material_protocol, suffix=".json"),
        material_summary_path=_safe_path(args.material_summary, suffix=".json"),
        material_path=_safe_path(args.material),
        physical_old_time_level_path=_safe_path(args.physical_old_time_level),
        phase7b7j_protocol_path=_safe_path(args.phase7b7j_protocol, suffix=".json"),
        adapter_runner_path=ADAPTER_RUNNER,
        provisional_runner_path=provisional.RUNNER_RELATIVE_PATH,
        preregister_runner_path=provisional.PAUSED_PREREGISTER_RELATIVE_PATH,
        feedback_work_directory=_safe_path(
            args.feedback_work_directory, below_checkpoints=True
        ),
        feedback_output=_safe_path(args.feedback_output),
        summary_path=_safe_path(args.summary, suffix=".json"),
    )
    payload, digest = preregister(root, spec=spec, output_path=args.output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return payload, digest


if __name__ == "__main__":
    main()
