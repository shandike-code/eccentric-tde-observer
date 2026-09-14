"""Phase 7B9cm：冻结第四次 Anderson 映射态的锚点副本。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts import phase7b9_protocol_builders as builder
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import phase7b9_protocol_builders as builder  # type: ignore[no-redef]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = "outputs/phase7b9cm_preregistered_fourth_map_anchor.json"


def main() -> None:
    payload = builder.build_anchor_copy_protocol(
        ROOT,
        builder.AnchorCopyProtocolSpec(
            phase="7B9cm preserved fourth accelerated-map anchor",
            phase_index=1414,
            classification=(
                "[A-preregistered] preserve the complete fourth Anderson mapped "
                "state before two mutable Picard maps; [V] require a byte-identical "
                "file clone and SHA-256 audit; [O] no residual is inferred for the copy"
            ),
            mapped_summary_path="outputs/phase7b9cl_fourth_candidate_map_summary.json",
            mapped_protocol_path=(
                "outputs/phase7b9cl_preregistered_fourth_candidate_map.json"
            ),
            mapped_summary_source_key="phase7b9cl_summary",
            mapped_protocol_source_key="phase7b9cl_protocol",
            mapped_source_state_key="mapped_source_state",
            target_state_path=(
                "outputs/checkpoints/phase7b6f_full_frequency_iteration4.dat"
            ),
            summary_path="outputs/phase7b9cm_fourth_map_anchor_summary.json",
            postcopy_authorization_key=(
                "fifth_accelerated_picard_continuation_authorized"
            ),
        ),
    )
    print(builder.freeze_protocol(ROOT, PROTOCOL, payload))


if __name__ == "__main__":
    main()
