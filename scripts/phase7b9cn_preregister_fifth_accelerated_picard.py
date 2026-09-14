"""Phase 7B9cn：冻结第四次 Anderson 映射后的两步 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as builder
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as builder  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "outputs/phase7b9cn_preregistered_fifth_accelerated_picard.json"


def main() -> None:
    payload = builder.build_seeded_two_map_picard_protocol(
        ROOT,
        builder.SeededTwoMapPicardProtocolSpec(
            phase="7B9cn fifth accelerated fixed-matter positive Picard continuation",
            phase_index=1415,
            classification=(
                "[A-preregistered] import the independently audited Phase 7B9cl "
                "map, then apply exactly two unrelaxed original source maps with "
                "three workers; [V] audit positivity, contraction, boundary, "
                "ownership and resources; [O] material feedback remains closed "
                "above the 1e-4 fixed-matter residual gate"
            ),
            mapped_summary_path="outputs/phase7b9cl_fourth_candidate_map_summary.json",
            mapped_protocol_path=(
                "outputs/phase7b9cl_preregistered_fourth_candidate_map.json"
            ),
            mapped_summary_source_key="phase7b9cl_summary",
            mapped_protocol_source_key="phase7b9cl_protocol",
            anchor_summary_path="outputs/phase7b9cm_fourth_map_anchor_summary.json",
            anchor_protocol_path=(
                "outputs/phase7b9cm_preregistered_fourth_map_anchor.json"
            ),
            anchor_summary_source_key="phase7b9cm_summary",
            anchor_protocol_source_key="phase7b9cm_protocol",
            anchor_continuation_decision_key=(
                "fifth_accelerated_picard_continuation_authorized"
            ),
            scratch_state_path=(
                "outputs/checkpoints/phase7b6j_line_search_iteration14.dat"
            ),
            manifest_path=(
                "outputs/checkpoints/phase7b9cn_fifth_accelerated_picard/manifest.json"
            ),
            report_directory=(
                "outputs/checkpoints/phase7b9cn_fifth_accelerated_picard/reports"
            ),
            summary_path="outputs/phase7b9cn_fifth_accelerated_picard_summary.json",
            figure_path="outputs/phase7b9cn_fifth_accelerated_picard.png",
            runner_path="scripts/phase7b9cn_fifth_accelerated_picard.py",
            slow_mode_after_pause_authorization_key="fifth_slow_mode_test_after_pause",
        ),
    )
    print(builder.freeze_protocol(ROOT, PROTOCOL, payload))


if __name__ == "__main__":
    main()
