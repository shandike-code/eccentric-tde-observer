"""Phase 7B9ck：冻结第四次 Anderson(1) 慢模外推。"""

from __future__ import annotations

try:
    from scripts import phase7b9_preregister_slow_mode_anderson as generic
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_preregister_slow_mode_anderson as generic  # type: ignore[no-redef]


def main() -> None:
    generic.preregister(
        phase="7B9ck fourth protected Anderson(1) slow-mode candidate",
        phase_index=1412,
        sequence_summary="outputs/phase7b9cj_fourth_accelerated_picard_summary.json",
        sequence_protocol="outputs/phase7b9cj_preregistered_fourth_accelerated_picard.json",
        anchor_summary="outputs/phase7b9ci_third_map_anchor_summary.json",
        anchor_protocol="outputs/phase7b9ci_preregistered_third_map_anchor.json",
        anchor_authorization_key="fourth_accelerated_picard_continuation_authorized",
        candidate_output="outputs/checkpoints/phase7b6h_full_frequency_residual8.dat",
        protocol_output="outputs/phase7b9ck_preregistered_fourth_slow_mode_anderson.json",
        summary_output="outputs/phase7b9ck_fourth_slow_mode_anderson_summary.json",
        figure_output="outputs/phase7b9ck_fourth_slow_mode_anderson.png",
    )


if __name__ == "__main__":
    main()
