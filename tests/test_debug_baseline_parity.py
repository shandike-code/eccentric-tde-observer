import numpy as np
import pytest

from operations.debug_baseline_parity import array_difference, parity_verdict


def test_flat_vector_reshapes_to_cell_and_component_locally():
    stored = np.arange(8, dtype=float)
    replayed = stored.copy()
    replayed[5] += 0.25          # 单元 1、分量 1
    result = array_difference(replayed, stored)
    assert result["maximum_absolute_difference"] == pytest.approx(0.25)
    assert result["worst"]["cell"] == 1
    assert result["worst"]["component"] == "hydrogen_logratio"
    assert result["exceedance_counts"]["absolute_difference_above_1e-13"] == 1
    assert result["components"]["energy"]["maximum_absolute_difference"] == 0.0


def test_shape_mismatch_and_wrong_length_are_rejected():
    with pytest.raises(ValueError):
        array_difference(np.zeros(8), np.zeros(9))
    with pytest.raises(ValueError):
        array_difference(np.zeros(7), np.zeros(7))


def test_difference_is_signed_and_cell_resolved():
    stored = np.array([1.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0])
    replayed = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    result = array_difference(replayed, stored)
    assert result["worst"]["cell"] == 1
    assert result["worst"]["difference"] == -1.0
    assert result["difference_by_cell"][1][0] == -1.0


def test_verdict_reports_how_far_past_the_allowed_envelope():
    stored = np.ones(4)
    assert parity_verdict(stored.copy(), stored)["passed"] is True
    assert parity_verdict(stored, stored)["worst_absolute_difference_over_allowed"] == 0.0
    offset = stored + 1.0e-9
    verdict = parity_verdict(offset, stored)
    assert verdict["passed"] is False
    assert verdict["worst_absolute_difference_over_allowed"] > 1.0


def test_verdict_uses_stored_magnitude_as_relative_scale():
    stored = np.array([0.0, 1000.0])
    # 相对项按 stored 缩放：大分量允许更大绝对差，小分量只由 atol 兜底。
    assert parity_verdict(np.array([0.0, 1000.0 + 1e-9]), stored)["passed"] is True
    assert parity_verdict(np.array([1e-9, 1000.0]), stored)["passed"] is False
