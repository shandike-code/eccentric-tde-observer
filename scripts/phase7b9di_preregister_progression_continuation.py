"""Freeze the Phase 7B9di boundary-tolerant progression protocol."""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9di_progression_continuation as continuation
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9di_progression_continuation as continuation  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "outputs/phase7b9di_preregistered_progression_continuation.json"


def main() -> None:
    spec = continuation.ProgressionContinuationSpec(
        phase="7B9di 0.0625 fixed-material radiation progression continuation",
        phase_index=1433,
        classification=(
            "[A-preregistered]+[V-lineage]+[O]：7B9dh bootstrap 未收敛但仅 boundary "
            "门未通过；稳定、正定且资源合规的 map 允许继续，残差和 boundary 三门仅决定 "
            "converged/provisional pause。"
        ),
        dh_protocol_path="outputs/phase7b9dh_preregistered_half_trial_radiation.json",
        dh_manifest_path=(
            "outputs/checkpoints/phase7b9dh_half_trial_radiation/manifest.json"
        ),
        dh_summary_path="outputs/phase7b9dh_half_trial_radiation_summary.json",
        dh_initialization_receipt_path=(
            "outputs/checkpoints/phase7b9dh_half_trial_radiation/"
            "initialization_receipt.json"
        ),
        runner_path=continuation.RUNNER_RELATIVE_PATH,
        manifest_path=(
            "outputs/checkpoints/phase7b9di_progression_continuation/manifest.json"
        ),
        transient_report_directory=(
            "outputs/checkpoints/phase7b9di_transient_reports"
        ),
        summary_path="outputs/phase7b9di_progression_continuation_summary.json",
        figure_path="outputs/phase7b9di_progression_continuation.png",
    )
    _, digest = continuation.write_protocol(ROOT, spec, PROTOCOL_PATH)
    print(digest)


if __name__ == "__main__":
    main()
