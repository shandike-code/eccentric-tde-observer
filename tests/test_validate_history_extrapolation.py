import numpy as np
import pytest
from operations.validate_history_extrapolation import affine_chunk, write_candidate, validation_checks


def test_streamed_affine_candidate_matches_declared_expression(tmp_path):
    a, b, out = (tmp_path / n for n in ('a', 'b', 'out'))
    x = np.arange(9, dtype=float); y = x + 1.
    x.tofile(a); y.tofile(b)
    before = [a.read_bytes(), b.read_bytes()]
    assert write_candidate([a, b], out, 3., 9, 4) == 3.
    assert np.array_equal(np.fromfile(out), y + 2 * (y - x))
    assert before == [a.read_bytes(), b.read_bytes()]
    with pytest.raises(FileExistsError): write_candidate([a, b], out, 3., 9, 4)


def test_negative_candidate_is_rejected_without_floor():
    with pytest.raises(ArithmeticError): affine_chunk(np.array([2.]), np.array([.5]), 2.)
    with pytest.raises(ValueError): affine_chunk(np.array([np.nan]), np.array([1.]), 2.)


def test_short_basis_cannot_publish_candidate(tmp_path):
    a, b, out = (tmp_path / n for n in ('a', 'b', 'out'))
    np.ones(2).tofile(a); np.ones(3).tofile(b)
    with pytest.raises(RuntimeError): write_candidate([a, b], out, 2., 3, 2)
    assert not out.exists()


def test_good_prediction_does_not_override_worse_actual_map():
    row = {'residual': .002, 'boundary_l1': 0., 'boundary_bolometric': 0., 'maximum_worker_rss_mib': 1000}
    assert not validation_checks(row, .001)['actual_maximum_norm_improves']
