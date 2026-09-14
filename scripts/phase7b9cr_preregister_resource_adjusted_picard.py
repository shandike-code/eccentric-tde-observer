"""Phase 7B9cr：冻结两进程资源门适配后的 Picard 续算协议。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts.phase7b9_resource_adjusted_picard import (
        RUNNER_RELATIVE_PATH,
        ResourceAdjustedPicardProtocolSpec,
        build_resource_adjusted_picard_protocol,
        common,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b9_resource_adjusted_picard import (  # type: ignore[no-redef]
        RUNNER_RELATIVE_PATH,
        ResourceAdjustedPicardProtocolSpec,
        build_resource_adjusted_picard_protocol,
        common,
    )


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9cr_preregistered_resource_adjusted_picard.json"


def main() -> None:
    spec = ResourceAdjustedPicardProtocolSpec(
        phase="7B9cr two-worker resource-adjusted positive Picard continuation",
        phase_index=1419,
        classification="[A-preregistered]+[A-resource]+[V]+[O]",
        source_protocol_path=(
            "outputs/phase7b9cq_preregistered_memory_reduced_picard.json"
        ),
        source_manifest_path=(
            "outputs/checkpoints/phase7b9cq_memory_reduced_picard/manifest.json"
        ),
        runner_path=RUNNER_RELATIVE_PATH,
        manifest_path=(
            "outputs/checkpoints/phase7b9cr_resource_adjusted_picard/manifest.json"
        ),
        report_directory=(
            "outputs/checkpoints/phase7b9cr_resource_adjusted_picard/reports"
        ),
        summary_path="outputs/phase7b9cr_resource_adjusted_picard_summary.json",
        figure_path="outputs/phase7b9cr_resource_adjusted_picard.png",
    )
    payload = build_resource_adjusted_picard_protocol(ROOT, spec)
    protocol_sha256 = common.freeze_protocol(ROOT, PROTOCOL_PATH, payload)
    print(protocol_sha256)


if __name__ == "__main__":
    main()
