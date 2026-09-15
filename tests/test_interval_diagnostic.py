"""The diagnostic driver must fire feedback on cadence and archive each round.

The driver's whole reason to exist is that `hpc/pipeline.py` stops mapping at
`pair_ready`; the properties worth pinning are therefore the cadence rule and the
guarantee that an earlier round's artifacts survive a later one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "diagnostics"))

import interval_diagnostic as driver  # noqa: E402


@pytest.mark.parametrize(
    "completed,rounds_done,expected",
    [
        (0, 0, False),   # nothing done yet
        (1, 0, False),   # not on the cadence
        (3, 0, False),
        (4, 0, True),    # first round
        (4, 1, False),   # already run for this boundary
        (5, 1, False),
        (8, 1, True),    # second round
        (8, 2, False),
        (12, 2, True),
    ],
)
def test_feedback_cadence(completed, rounds_done, expected):
    assert driver.should_run_feedback(completed, 4, rounds_done, False) is expected


def test_feedback_never_fires_after_a_stop_request():
    assert driver.should_run_feedback(4, 4, 0, True) is False


def test_archive_round_preserves_artifacts(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "feedback_summary.json").write_text('{"round": 1}')
    (run / "previous_feedback.npz").write_bytes(b"first")
    work = run / "feedback"
    work.mkdir()
    (work / "previous_manifest.json").write_text("{}")

    first = run / "feedback-round1"
    first.mkdir()
    driver.archive_round(run, first)
    assert (first / "feedback_summary.json").read_text() == '{"round": 1}'
    assert (first / "previous_feedback.npz").read_bytes() == b"first"
    assert (first / "feedback" / "previous_manifest.json").is_file()

    # Archiving must clear the run root: a leftover summary makes run_pair raise
    # "formal feedback-pair summary lineage changed" on the next round.
    assert not (run / "feedback_summary.json").exists()
    assert not (run / "previous_feedback.npz").exists()
    assert not (run / "feedback").exists()

    # A later round must not land in the earlier round's directory.
    (run / "previous_feedback.npz").write_bytes(b"second")
    second = run / "feedback-round2"
    second.mkdir()
    driver.archive_round(run, second)
    assert (first / "previous_feedback.npz").read_bytes() == b"first"
    assert (second / "previous_feedback.npz").read_bytes() == b"second"


def test_archive_round_skips_absent_artifacts(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "feedback_summary.json").write_text("{}")
    target = run / "feedback-round1"
    target.mkdir()
    driver.archive_round(run, target)
    assert sorted(p.name for p in target.iterdir()) == ["feedback_summary.json"]
