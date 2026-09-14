"""Phase 7B9cs：冻结 7B9cr 末态的字节一致 APFS 锚点协议。"""

from __future__ import annotations

from pathlib import Path

try:
    from scripts.phase7b9_protocol_builders import (
        SequenceTailAnchorProtocolSpec,
        build_sequence_tail_anchor_protocol,
        freeze_protocol,
    )
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from phase7b9_protocol_builders import (  # type: ignore[no-redef]
        SequenceTailAnchorProtocolSpec,
        build_sequence_tail_anchor_protocol,
        freeze_protocol,
    )


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = "outputs/phase7b9cs_preregistered_resource_tail_anchor.json"


def main() -> None:
    spec = SequenceTailAnchorProtocolSpec(
        phase="7B9cs byte-identical anchor of the resource-adjusted Picard tail",
        phase_index=1420,
        classification="[A-preregistered]+[V]+[O]",
        sequence_summary_path="outputs/phase7b9cr_resource_adjusted_picard_summary.json",
        sequence_protocol_path=(
            "outputs/phase7b9cr_preregistered_resource_adjusted_picard.json"
        ),
        target_state_path=(
            "outputs/checkpoints/phase7b9cs_resource_adjusted_tail_anchor.dat"
        ),
        summary_path="outputs/phase7b9cs_resource_tail_anchor_summary.json",
        postcopy_authorization_key="phase7b9ct_two_map_tail_authorized",
    )
    payload = build_sequence_tail_anchor_protocol(ROOT, spec)
    protocol_sha256 = freeze_protocol(ROOT, PROTOCOL_PATH, payload)
    print(protocol_sha256)


if __name__ == "__main__":
    main()
