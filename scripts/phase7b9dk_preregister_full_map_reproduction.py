"""Phase 7B9dk：只用小文件预注册完整 76 块 reproduction 协议。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts import phase7b9dk_full_map_reproduction as reproduction
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9dk_full_map_reproduction as reproduction  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]


def preregister(
    root: Path,
    *,
    phase: str,
    classification: str,
    di_protocol_path: str,
    di_manifest_path: str,
    di_summary_path: str,
    failure_audit_path: str,
    runner_path: str,
    manifest_path: str,
    report_directory: str,
    summary_path: str,
    immutable_input_sha256: str,
    authorized_output_previous_sha256: str,
    natural_frequency_block_width: int,
    output_path: str,
) -> tuple[dict[str, object], str]:
    destination = (root / output_path).resolve()
    allowed = (root / "outputs").resolve()
    if destination.suffix != ".json" or not destination.is_relative_to(allowed):
        raise RuntimeError("7B9dk preregistration output must be an outputs/*.json file")
    spec = reproduction.FullMapReproductionSpec(
        phase=phase,
        classification=classification,
        di_protocol_path=di_protocol_path,
        di_manifest_path=di_manifest_path,
        di_summary_path=di_summary_path,
        failure_audit_path=failure_audit_path,
        runner_path=runner_path,
        manifest_path=manifest_path,
        report_directory=report_directory,
        summary_path=summary_path,
        immutable_input_sha256=immutable_input_sha256,
        authorized_output_previous_sha256=authorized_output_previous_sha256,
        natural_frequency_block_width=natural_frequency_block_width,
    )
    return reproduction.write_protocol(root, spec, destination)


def main(
    argv: list[str] | None = None, *, root: Path | None = None
) -> tuple[dict[str, object], str]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--classification", required=True)
    parser.add_argument("--di-protocol", required=True)
    parser.add_argument("--di-manifest", required=True)
    parser.add_argument("--di-summary", required=True)
    parser.add_argument("--failure-audit", required=True)
    parser.add_argument("--runner", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report-directory", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--immutable-input-sha256", required=True)
    parser.add_argument("--authorized-output-previous-sha256", required=True)
    parser.add_argument("--natural-frequency-block-width", type=int, default=128)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    base = ROOT if root is None else root
    protocol, digest = preregister(
        base,
        phase=args.phase,
        classification=args.classification,
        di_protocol_path=args.di_protocol,
        di_manifest_path=args.di_manifest,
        di_summary_path=args.di_summary,
        failure_audit_path=args.failure_audit,
        runner_path=args.runner,
        manifest_path=args.manifest,
        report_directory=args.report_directory,
        summary_path=args.summary,
        immutable_input_sha256=args.immutable_input_sha256,
        authorized_output_previous_sha256=args.authorized_output_previous_sha256,
        natural_frequency_block_width=args.natural_frequency_block_width,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "output": args.output,
                "sha256": digest,
                "full_state_bytes_read_or_hashed": False,
            },
            indent=2,
        )
    )
    return protocol, digest


if __name__ == "__main__":
    main()
