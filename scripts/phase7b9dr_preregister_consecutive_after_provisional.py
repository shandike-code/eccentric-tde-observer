"""Phase 7B9dr：由 dp pause 与 dq 缓存反馈原子预注册一张 fresh map。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9_consecutive_after_provisional as consecutive
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_consecutive_after_provisional as consecutive  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _safe_output_path(value: str, *, suffix: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] != "outputs"
        or path.suffix.lower() != suffix
        or (len(path.parts) > 1 and path.parts[1] == "checkpoints")
    ):
        raise ValueError(f"7B9dr output must be a safe {suffix} below outputs")
    return str(path)


def _safe_small_input(value: str, *, suffix: str | None = None) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] not in {"outputs", "scripts"}
        or (suffix is not None and path.suffix.lower() != suffix)
        or path.suffix.lower() == ".dat"
    ):
        raise ValueError("7B9dr accepts only safe repository-relative small inputs")
    return str(path)


def preregister(
    root: Path,
    *,
    spec: consecutive.PausedConsecutiveAfterProvisionalSpec,
    output_path: str,
) -> tuple[dict[str, object], str]:
    output = root / _safe_output_path(output_path, suffix=".json")
    return consecutive.write_paused_consecutive_after_provisional_protocol(
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
    parser.add_argument("--provisional-protocol", required=True)
    parser.add_argument("--provisional-manifest", required=True)
    parser.add_argument("--provisional-summary", required=True)
    parser.add_argument("--provisional-artifact", required=True)
    parser.add_argument("--transition-receipt", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    spec = consecutive.PausedConsecutiveAfterProvisionalSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        continuation_protocol_path=_safe_small_input(
            args.continuation_protocol, suffix=".json"
        ),
        continuation_manifest_path=_safe_small_input(
            args.continuation_manifest, suffix=".json"
        ),
        continuation_summary_path=_safe_small_input(
            args.continuation_summary, suffix=".json"
        ),
        provisional_protocol_path=_safe_small_input(
            args.provisional_protocol, suffix=".json"
        ),
        provisional_manifest_path=_safe_small_input(
            args.provisional_manifest, suffix=".json"
        ),
        provisional_summary_path=_safe_small_input(
            args.provisional_summary, suffix=".json"
        ),
        provisional_artifact_path=_safe_small_input(args.provisional_artifact),
        runner_path=consecutive.RUNNER_RELATIVE_PATH,
        preregister_runner_path=consecutive.PAUSED_PREREGISTER_RELATIVE_PATH,
        transition_receipt_path=_safe_output_path(
            args.transition_receipt, suffix=".json"
        ),
        summary_path=_safe_output_path(args.summary, suffix=".json"),
    )
    payload, digest = preregister(root, spec=spec, output_path=args.output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return payload, digest


if __name__ == "__main__":
    main()
