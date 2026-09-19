import numpy as np
import pytest
from operations.validate_cross_history_candidate import affine_chunk, write_candidate, full_field_error
from operations.diagnose_cross_history_positivity import obstruction_stats


def files(tmp_path, arrays):
    paths = [tmp_path/str(i) for i in range(len(arrays))]
    for p, a in zip(paths, arrays): np.asarray(a, dtype=np.float64).tofile(p)
    return paths


def test_cross_candidate_uses_correct_order_and_preserves_sources(tmp_path):
    xb, xo = np.arange(12.)+1, np.arange(12.)+5
    paths = files(tmp_path, [xb, xo]); before = [p.read_bytes() for p in paths]
    out = tmp_path/'candidate.dat'
    write_candidate(paths, out, -.2, 12, 5)
    assert np.array_equal(np.fromfile(out), xb-.2*(xb-xo))
    assert [p.read_bytes() for p in paths] == before
    with pytest.raises(FileExistsError): write_candidate(paths, out, -.2, 12, 5)


@pytest.mark.parametrize('xb,xo,g', [([0.], [1.], .1), ([np.nan], [1.], -.2), ([1.], [2.], 20.)])
def test_invalid_or_negative_mix_rejected(xb, xo, g):
    with pytest.raises((ValueError, ArithmeticError)): affine_chunk(np.array(xb), np.array(xo), g)


def test_short_read_does_not_publish_candidate(tmp_path):
    paths = files(tmp_path, [np.ones(7), np.ones(8)]); out = tmp_path/'candidate.dat'
    with pytest.raises(RuntimeError): write_candidate(paths, out, -.2, 8, 3)
    assert not out.exists()


def test_full_field_check_detects_error_hidden_by_equal_scalar_residual(tmp_path):
    x = np.ones((1, 4, 2)); predicted = x.copy(); predicted[0, 0, 0] += .1
    actual = x.copy(); actual[0, 1, 0] += .1
    # 两者相对同一候选的最大残差相同，逐单元输出却不同。
    assert np.max(abs(predicted-x)) == np.max(abs(actual-x))
    paths = files(tmp_path, [x, actual, predicted, predicted])
    result = full_field_error(paths, x.shape, -.2, np.array([1., 2.]))
    assert result['error_over_actual_defect_l2'] == pytest.approx(np.sqrt(2.))
    assert not result['prediction_error_resolved']


def test_exact_full_field_prediction_passes(tmp_path):
    x = np.ones((1, 4, 2)); yb = 2*x; yo = 3*x; y = affine_chunk(yb, yo, -.2)
    r = full_field_error(files(tmp_path, [x, y, yb, yo]), x.shape, -.2, np.array([1., 2.]))
    assert r['error_l2'] == r['boundary_prediction_l1_error'] == 0.
    assert r['prediction_error_resolved']


def test_positivity_audit_counts_and_locates_only_exact_obstructions(tmp_path):
    xb = np.ones((2, 4, 3)); xo = xb.copy()
    xb[1, 2, 0] = 0.; xo[1, 2, 0] = 2.
    xb[0, 0, 0] = xo[0, 0, 0] = 0.
    paths = files(tmp_path, [xb, np.ones_like(xb), xo, np.ones_like(xb)])
    before = [p.read_bytes() for p in paths]
    r = obstruction_stats(paths, xb.shape)
    assert r['candidate']['count'] == 1 and r['predicted_map']['count'] == 0
    top = r['candidate']['largest_cells'][0]
    assert (top['frequency_index'], top['angle_index'], top['radiation_depth_index']) == (1, 2, 0)
    assert r['candidate']['maximum_obstruction_over_field_scale'] == 1.
    assert [p.read_bytes() for p in paths] == before
