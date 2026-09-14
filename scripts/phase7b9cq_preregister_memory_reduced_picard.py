"""Phase 7B9cq：冻结两进程低内存 Picard 续算协议。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts.phase7b9_protocol_builders import (
        MEMORY_REDUCED_PICARD_RUNNER,
        MemoryReducedPicardContinuationProtocolSpec,
        build_memory_reduced_picard_continuation_protocol,
        freeze_protocol,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b9_protocol_builders import (  # type: ignore[no-redef]
        MEMORY_REDUCED_PICARD_RUNNER,
        MemoryReducedPicardContinuationProtocolSpec,
        build_memory_reduced_picard_continuation_protocol,
        freeze_protocol,
    )


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9cq_preregistered_memory_reduced_picard.json"


def main() -> None:
    spec = MemoryReducedPicardContinuationProtocolSpec(
        phase="7B9cq memory-reduced fixed-matter positive Picard continuation",
        phase_index=1418,
        classification="[A-preregistered]+[V]+[O]",
        interrupted_protocol_path=(
            "outputs/phase7b9cp_preregistered_long_positive_picard.json"
        ),
        interrupted_manifest_path=(
            "outputs/checkpoints/phase7b9cp_long_positive_picard/manifest.json"
        ),
        manifest_path=(
            "outputs/checkpoints/phase7b9cq_memory_reduced_picard/manifest.json"
        ),
        report_directory=(
            "outputs/checkpoints/phase7b9cq_memory_reduced_picard/reports"
        ),
        summary_path="outputs/phase7b9cq_memory_reduced_picard_summary.json",
        figure_path="outputs/phase7b9cq_memory_reduced_picard.png",
        # 中文：父进程与 worker 共用已测试的 SHA 固定低内存 runner。
        runner_path=MEMORY_REDUCED_PICARD_RUNNER,
    )
    payload = build_memory_reduced_picard_continuation_protocol(ROOT, spec)
    protocol_sha256 = freeze_protocol(ROOT, PROTOCOL_PATH, payload)
    print(protocol_sha256)


if __name__ == "__main__":
    main()
