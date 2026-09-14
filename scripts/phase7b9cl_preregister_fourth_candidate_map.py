"""Phase 7B9cl：冻结第四次慢模候选的完整原算子映射。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as builder
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as builder  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "outputs/phase7b9cl_preregistered_fourth_candidate_map.json"


def main() -> None:
    payload = builder.build_candidate_map_protocol(
        ROOT,
        builder.CandidateMapProtocolSpec(
            phase="7B9cl fourth slow-mode candidate original-operator map",
            phase_index=1413,
            classification=(
                "[A-preregistered] apply exactly one complete, unrelaxed fixed-matter "
                "source map to the fourth protected Anderson(1) state; [V] audit all "
                "9632 groups, positivity, prediction reproduction, boundary and "
                "resources; [O] material feedback remains closed above 1e-4"
            ),
            candidate_summary_path=(
                "outputs/phase7b9ck_fourth_slow_mode_anderson_summary.json"
            ),
            candidate_protocol_path=(
                "outputs/phase7b9ck_preregistered_fourth_slow_mode_anderson.json"
            ),
            candidate_summary_source_key="phase7b9ck_summary",
            candidate_protocol_source_key="phase7b9ck_protocol",
            output_state_path=(
                "outputs/checkpoints/phase7b6h_full_frequency_iteration8.dat"
            ),
            manifest_path=(
                "outputs/checkpoints/phase7b9cl_fourth_candidate_map/manifest.json"
            ),
            report_directory=(
                "outputs/checkpoints/phase7b9cl_fourth_candidate_map/reports"
            ),
            summary_path="outputs/phase7b9cl_fourth_candidate_map_summary.json",
            figure_path="outputs/phase7b9cl_fourth_candidate_map.png",
            block_report_prefix="phase7b9cl",
            runner_path="scripts/phase7b9cl_fourth_candidate_map.py",
        ),
    )
    print(builder.freeze_protocol(ROOT, PROTOCOL, payload))


if __name__ == "__main__":
    main()
