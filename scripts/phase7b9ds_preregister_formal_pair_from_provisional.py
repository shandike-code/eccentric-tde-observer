"""Phase 7B9ds：由 passed dr 与 cached dq 原子预注册正式 feedback pair。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9_formal_pair_from_provisional as pair
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_formal_pair_from_provisional as pair  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _safe_path(
    value: str,
    *,
    suffix: str | None = None,
    output: bool = False,
    work_directory: bool = False,
) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("7B9ds path must be repository-relative")
    if suffix is not None and path.suffix.lower() != suffix:
        raise ValueError(f"7B9ds path must end in {suffix}")
    if path.suffix.lower() == ".dat":
        raise ValueError("7B9ds refuses .dat source arguments")
    if work_directory:
        if path.parts[:2] != ("outputs", "checkpoints") or "formal" not in path.name:
            raise ValueError("7B9ds work directory must be formal and below checkpoints")
    elif path.parts[0] not in {"outputs", "scripts"}:
        raise ValueError("7B9ds path must be below outputs or scripts")
    if output and (
        path.parts[0] != "outputs"
        or (len(path.parts) > 1 and path.parts[1] == "checkpoints")
    ):
        raise ValueError("7B9ds small output must be below outputs")
    return str(path)


def preregister(
    root: Path,
    *,
    spec: pair.PausedFormalPairFromProvisionalSpec,
    output_path: str,
) -> tuple[dict[str, object], str]:
    output = root / _safe_path(output_path, suffix=".json", output=True)
    return pair.write_paused_formal_pair_from_provisional_protocol(
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
    parser.add_argument("--confirmation-protocol", required=True)
    parser.add_argument("--confirmation-summary", required=True)
    parser.add_argument("--provisional-protocol", required=True)
    parser.add_argument("--provisional-summary", required=True)
    parser.add_argument("--provisional-manifest", required=True)
    parser.add_argument("--provisional-artifact", required=True)
    parser.add_argument("--trial-acceptance", required=True)
    parser.add_argument("--base-feedback-summary", required=True)
    parser.add_argument("--base-residual", required=True)
    parser.add_argument("--feedback-work-directory", required=True)
    parser.add_argument("--final-feedback-output", required=True)
    parser.add_argument("--target-material-output", required=True)
    parser.add_argument("--encoded-residual-output", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    spec = pair.PausedFormalPairFromProvisionalSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        confirmation_protocol_path=_safe_path(
            args.confirmation_protocol, suffix=".json"
        ),
        confirmation_summary_path=_safe_path(
            args.confirmation_summary, suffix=".json"
        ),
        provisional_protocol_path=_safe_path(
            args.provisional_protocol, suffix=".json"
        ),
        provisional_summary_path=_safe_path(
            args.provisional_summary, suffix=".json"
        ),
        provisional_manifest_path=_safe_path(
            args.provisional_manifest, suffix=".json"
        ),
        provisional_artifact_path=_safe_path(args.provisional_artifact),
        trial_acceptance_path=_safe_path(args.trial_acceptance, suffix=".json"),
        base_feedback_summary_path=_safe_path(
            args.base_feedback_summary, suffix=".json"
        ),
        base_residual_path=_safe_path(args.base_residual),
        adapter_runner_path=pair.PAUSED_ADAPTER_RELATIVE_PATH,
        pair_runner_path=pair.RUNNER_RELATIVE_PATH,
        preregister_runner_path=pair.PAUSED_PREREGISTER_RELATIVE_PATH,
        feedback_work_directory=_safe_path(
            args.feedback_work_directory, work_directory=True
        ),
        final_feedback_output=_safe_path(args.final_feedback_output, output=True),
        target_material_output=_safe_path(args.target_material_output, output=True),
        encoded_residual_output=_safe_path(args.encoded_residual_output, output=True),
        summary_path=_safe_path(args.summary, suffix=".json", output=True),
        figure_path=_safe_path(args.figure, suffix=".png", output=True),
    )
    payload, digest = preregister(root, spec=spec, output_path=args.output)
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return payload, digest


if __name__ == "__main__":
    main()
