"""Phase 7B9cp：冻结拒绝第五次 Anderson 后的长正 Picard 延拓。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as builder
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as builder  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "outputs/phase7b9cp_preregistered_long_positive_picard.json"


def main() -> None:
    payload = builder.build_sequence_picard_continuation_protocol(
        ROOT,
        builder.SequencePicardContinuationProtocolSpec(
            phase="7B9cp long fixed-matter positive Picard after rejected Anderson",
            phase_index=1417,
            classification=(
                "[A-preregistered] resume only the unrelaxed original positive "
                "Picard map after Phase 7B9co failed its unchanged 0.99 predicted-"
                "improvement gate; [V] audit every new map for positivity, contraction, "
                "boundary, ownership and resources; [O] material feedback opens only "
                "after the 1e-4 fixed-matter residual and a separate consecutive-state gate"
            ),
            sequence_summary_path=(
                "outputs/phase7b9cn_fifth_accelerated_picard_summary.json"
            ),
            sequence_protocol_path=(
                "outputs/phase7b9cn_preregistered_fifth_accelerated_picard.json"
            ),
            rejected_anderson_summary_path=(
                "outputs/phase7b9co_fifth_slow_mode_anderson_summary.json"
            ),
            rejected_anderson_protocol_path=(
                "outputs/phase7b9co_preregistered_fifth_slow_mode_anderson.json"
            ),
            scratch_state_path=(
                "outputs/checkpoints/phase7b6h_full_frequency_residual8.dat"
            ),
            maximum_total_picard_maps=24,
            manifest_path=(
                "outputs/checkpoints/phase7b9cp_long_positive_picard/manifest.json"
            ),
            report_directory=(
                "outputs/checkpoints/phase7b9cp_long_positive_picard/reports"
            ),
            summary_path="outputs/phase7b9cp_long_positive_picard_summary.json",
            figure_path="outputs/phase7b9cp_long_positive_picard.png",
            runner_path="scripts/phase7b9cp_long_positive_picard.py",
        ),
    )
    print(builder.freeze_protocol(ROOT, PROTOCOL, payload))


if __name__ == "__main__":
    main()
