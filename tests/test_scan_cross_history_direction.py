import numpy as np
import pytest
from operations.scan_cross_history_direction import scan, metrics, chunks, positive_interval


def files(tmp_path, arrays):
    paths = [tmp_path/str(i) for i in range(len(arrays))]
    for p, a in zip(paths, arrays): np.asarray(a, dtype=np.float64).tofile(p)
    return paths


def test_known_affine_fixed_point_recovered_without_mutating_basis(tmp_path):
    root = np.arange(24, dtype=float).reshape(3, 4, 2)+10.
    xb, xo = root+2., root+4.
    yb, yo = root+.99*(xb-root), root+.99*(xo-root)
    paths = files(tmp_path, [xb, yb, xo, yo]); before = [p.read_bytes() for p in paths]
    d = scan(paths, root.shape)
    assert d['gamma'] == pytest.approx(1., abs=1e-10)
    assert d['history_difference_image_l2_ratio'] == pytest.approx(.99)
    assert d['relative_operator_change_along_history_difference'] == pytest.approx(.01)
    m = metrics(paths, root.shape, d['gamma'], np.array([1., 2., 4., 8.]))
    assert m['predicted_residual'] < 1e-12
    assert m['candidate_negative_count'] == m['predicted_map_negative_count'] == 0
    assert [p.read_bytes() for p in paths] == before


def test_positivity_limits_global_coefficient_without_floor():
    assert positive_interval(np.array([0., 2.]), np.array([-1., 1.])) == (-2., 0.)


def test_unresolved_history_difference_does_not_invent_step(tmp_path):
    x = np.ones((1, 4, 2)); y = 2*x
    d = scan(files(tmp_path, [x, y, x, y]), x.shape)
    assert d['gamma_unconstrained'] is None
    assert d['gamma'] == d['direction_resolution_ratio'] == 0.


def test_large_unconstrained_coefficient_is_bounded(tmp_path):
    root = np.full((1, 4, 2), 20.); xb, xo = root+2., root+2.01
    paths = files(tmp_path, [xb, root+.99*(xb-root), xo, root+.99*(xo-root)])
    d = scan(paths, root.shape)
    assert d['gamma_unconstrained'] > 100.
    assert d['gamma'] < 15.5 and d['coefficient_l1'] <= 32.


def test_zero_cell_blocks_positive_extrapolation_instead_of_clipping(tmp_path):
    shape = (1, 4, 2)
    paths = files(tmp_path, [np.full(shape, x) for x in (0., .01, 1., 1.02)])
    d = scan(paths, shape)
    assert d['gamma_unconstrained'] > 0.
    assert d['gamma'] == 0.


@pytest.mark.parametrize('value', [-1., np.nan, np.inf])
def test_invalid_basis_rejected(tmp_path, value):
    a = np.ones((1, 4, 2)); b = a.copy(); b[0, 0, 0] = value
    with pytest.raises(ArithmeticError): scan(files(tmp_path, [a, a, b, a]), a.shape)


@pytest.mark.parametrize('length', [7, 9])
def test_short_or_long_basis_rejected(tmp_path, length):
    paths = files(tmp_path, [np.ones(length)]*4)
    with pytest.raises(RuntimeError): list(chunks(paths, (1, 4, 2)))


def test_invalid_frequency_measure_rejected(tmp_path):
    a = np.ones((2, 4, 2)); paths = files(tmp_path, [a]*4)
    with pytest.raises(ValueError): metrics(paths, a.shape, 0., np.array([1., 1., 2.]))
