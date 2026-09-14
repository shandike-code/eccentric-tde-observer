"""Phase 7B9ct：冻结锚点保护下的两次低内存 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts.phase7b9_protocol_builders import (
        TailTwoMapPicardProtocolSpec,
        build_tail_two_map_picard_protocol,
        freeze_protocol,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b9_protocol_builders import (  # type: ignore[no-redef]
        TailTwoMapPicardProtocolSpec,
        build_tail_two_map_picard_protocol,
        freeze_protocol,
    )


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9ct_preregistered_two_map_tail.json"


def main() -> None:
    spec = TailTwoMapPicardProtocolSpec(
        phase="7B9ct two-map memory-safe Picard tail",
        phase_index=1421,
        classification="[A-preregistered]+[A-resource]+[V]+[O]",
        sequence_summary_path="outputs/phase7b9cr_resource_adjusted_picard_summary.json",
        sequence_protocol_path=(
            "outputs/phase7b9cr_preregistered_resource_adjusted_picard.json"
        ),
        anchor_summary_path="outputs/phase7b9cs_resource_tail_anchor_summary.json",
        anchor_protocol_path=(
            "outputs/phase7b9cs_preregistered_resource_tail_anchor.json"
        ),
        anchor_continuation_decision_key="phase7b9ct_two_map_tail_authorized",
        scratch_state_path=(
            "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
        ),
        manifest_path="outputs/checkpoints/phase7b9ct_two_map_tail/manifest.json",
        report_directory="outputs/checkpoints/phase7b9ct_two_map_tail/reports",
        summary_path="outputs/phase7b9ct_two_map_tail_summary.json",
        figure_path="outputs/phase7b9ct_two_map_tail.png",
        runner_path="scripts/phase7b9ct_two_map_tail.py",
        tail_anderson_authorization_key=(
            "phase7b9cu_protected_tail_anderson_authorized"
        ),
    )
    payload = build_tail_two_map_picard_protocol(ROOT, spec)
    protocol_sha256 = freeze_protocol(ROOT, PROTOCOL_PATH, payload)
    print(protocol_sha256)


if __name__ == "__main__":
    main()
