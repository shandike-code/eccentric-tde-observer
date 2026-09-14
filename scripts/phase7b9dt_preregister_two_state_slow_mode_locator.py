"""Phase 7B9dt：从结束态小证据原子预注册两态慢模定位器。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

try:
    from scripts import phase7b9dt_two_state_slow_mode_locator as locator
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9dt_two_state_slow_mode_locator as locator  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def _safe_path(value: str, *, suffix: str, output: bool = False) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("7B9dt path must be repository-relative")
    if path.suffix.lower() != suffix:
        raise ValueError(f"7B9dt path must end in {suffix}")
    if path.suffix.lower() == ".dat":
        raise ValueError("7B9dt preregistration refuses .dat arguments")
    if output and (
        path.parts[0] != "outputs"
        or (len(path.parts) > 1 and path.parts[1] == "checkpoints")
    ):
        raise ValueError("7B9dt diagnostic output must be below outputs")
    return str(path)


def main(
    argv: list[str] | None = None, *, root: Path = ROOT
) -> tuple[dict[str, object], str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--phase-index", required=True, type=int)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--ending-protocol", required=True)
    parser.add_argument("--ending-manifest", required=True)
    parser.add_argument("--ending-summary", required=True)
    parser.add_argument("--block-json", required=True)
    parser.add_argument("--block-csv", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    spec = locator.TwoStateSlowModeLocatorSpec(
        phase=args.phase,
        phase_index=args.phase_index,
        classification=args.classification,
        ending_protocol_path=_safe_path(args.ending_protocol, suffix=".json"),
        ending_manifest_path=_safe_path(args.ending_manifest, suffix=".json"),
        ending_summary_path=_safe_path(args.ending_summary, suffix=".json"),
        analyzer_runner_path=locator.RUNNER_RELATIVE_PATH,
        preregister_runner_path=locator.PREREGISTER_RELATIVE_PATH,
        block_json_path=_safe_path(args.block_json, suffix=".json", output=True),
        block_csv_path=_safe_path(args.block_csv, suffix=".csv", output=True),
        summary_path=_safe_path(args.summary, suffix=".json", output=True),
        figure_path=_safe_path(args.figure, suffix=".png", output=True),
    )
    output = root / _safe_path(args.output, suffix=".json", output=True)
    protocol, digest = locator.write_two_state_slow_mode_locator_protocol(
        root, spec, output
    )
    print(json.dumps({"output": args.output, "sha256": digest}, indent=2))
    return protocol, digest


if __name__ == "__main__":
    main()
