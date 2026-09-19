import numpy as np
import pytest
from operations.profile_frozen_feedback_block import compare_arrays


def test_comparison_reports_difference_without_acceptance(tmp_path):
    a, b = tmp_path / 'a.npz', tmp_path / 'b.npz'
    np.savez(a, q=np.array([0., -2., 4.]))
    np.savez(b, q=np.array([0., -3., 4.]))
    result = compare_arrays(a, b)['q']
    assert not result['bitwise_equal']
    assert result['maximum_absolute_difference'] == 1
    assert result['relative_to_reference_maximum'] == .25


@pytest.mark.parametrize('values', [np.array([np.nan]), np.array([np.inf]), np.array([1., 2.])])
def test_rejects_nonfinite_or_malformed_replay(tmp_path, values):
    a, b = tmp_path / 'a.npz', tmp_path / 'b.npz'
    np.savez(a, q=np.array([1.]))
    np.savez(b, q=values)
    with pytest.raises(RuntimeError):
        compare_arrays(a, b)
