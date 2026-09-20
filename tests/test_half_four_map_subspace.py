from copy import deepcopy
import numpy as np
import pytest
from operations import scan_half_four_map_subspace as scan


def history(prefix, n):
    h = [{'input_path': f'{prefix}{i}', 'input_sha256': f'h{prefix}{i}',
          'output_path': f'{prefix}{i+1}', 'output_sha256': f'h{prefix}{i+1}', 'residual': 1/(i+1)} for i in range(n)]
    return {'status': 'diagnostic_round_complete', 'history': h, 'slots': [f'{prefix}{n}'],
            'current_slot': 0, 'current_sha256': f'h{prefix}{n}', 'diagnostic': {'rounds': [
                {'endpoints': [n-1, n], 'endpoints_claim': {
                    e: {'path': h[i]['input_path'], 'sha256': h[i]['input_sha256']} for e,i in [('previous', -2), ('final', -1)]}}]}}


def files(tmp_path, arrays):
    result = []
    for i,a in enumerate(arrays):
        p = tmp_path/f'{i}.bin'; np.asarray(a, dtype=np.float64).tofile(p); result.append(p)
    return result


def test_explicit_pairs_preserve_each_measured_operator_application():
    pairs = scan.explicit_pairs([history('a', 8), history('b', 8), history('c', 2)])
    assert [[x['path'] for x in p] for p in pairs] == [['a7','a8'], ['b7','b8'], ['c0','c1'], ['c1','c2']]


@pytest.mark.parametrize('fault', ['link', 'current', 'pending', 'feedback'])
def test_no_cross_history_or_unsettled_substitution(fault):
    s = [history('a', 8), history('b', 8), history('c', 2)]
    if fault == 'link': s[2]['history'][0]['output_sha256'] = 'wrong'
    if fault == 'current': s[0]['current_sha256'] = 'wrong'
    if fault == 'pending': s[1]['pending_feedback'] = {'x': 1}
    if fault == 'feedback': s[2]['diagnostic']['rounds'][0]['endpoints'] = [3,4]
    with pytest.raises(ValueError): scan.explicit_pairs(s)


def test_pair_layout_does_not_assume_six_consecutive_states():
    a = [np.array([float(i)]) for i in range(8)]
    x,y = scan.fields(a, np.array([.1,.2,.3,.4]))
    assert x == pytest.approx(4.) and y == pytest.approx(5.)
    with pytest.raises(ValueError): scan.fields(a[:6], np.ones(4)/4)


def test_streamed_solution_matches_independent_affine_least_squares(tmp_path):
    rng = np.random.default_rng(531); shape = (3,2,2)
    r = rng.normal(size=(4,12))*.01
    a = [v.reshape(shape) for i in range(4) for v in (np.ones(12), np.ones(12)+r[i])]
    paths = files(tmp_path, a); w, system = scan.residual_system(paths, shape)
    d = (r[[0,2,3]]-r[1]).T
    coeff = np.linalg.lstsq(d, -r[3], rcond=1e-12)[0]
    expected = np.array([coeff[0], -coeff.sum(), coeff[1], 1+coeff[2]])
    np.testing.assert_allclose(w, expected, rtol=1e-10, atol=1e-12)
    assert system['retained_rank'] == 3


def test_degenerate_maps_do_not_invent_resolved_directions(tmp_path):
    paths = files(tmp_path, [np.ones((2,2,2))]*8)
    _, system = scan.residual_system(paths, (2,2,2))
    assert system['retained_rank'] == 0


def test_tiny_negative_cell_generates_scaled_constraint_without_clipping(tmp_path):
    shape = (1,2,2); a = [np.ones(shape)*1e-250 for _ in range(8)]
    a[0][0,0,0] = 3e-250; paths = files(tmp_path,a)
    additions, stats = scan.collect_cuts(paths, shape, np.array([-1.,0.,0.,2.]))
    assert stats['negative_counts'] == [1,0]
    assert len(additions) == 1 and additions[0]['index'] == [0,0,0]
    assert np.all(np.isfinite(additions[0]['row']))
    assert additions[0]['lower'] < 0


def test_negative_source_is_rejected_before_prediction(tmp_path):
    shape = (1,2,2); a = [np.ones(shape) for _ in range(8)]; a[0][0,0,0] = -1
    with pytest.raises(ArithmeticError): scan.residual_system(files(tmp_path,a), shape)


def test_global_coefficient_step_keeps_sum_and_cap():
    target = np.array([100., -99., 0., 0.]); step = scan.coefficient_step(target)
    w = scan.ANCHOR+step*(target-scan.ANCHOR)
    assert 0 < step < 1 and abs(w.sum()-1) < 1e-12 and abs(w).sum() <= 32


def test_zero_tail_is_retained_and_full_field_metrics_match_direct_result(tmp_path):
    shape = (2,2,3); x = np.ones(shape); x[1] = 0; y = 1.0001*x
    paths = files(tmp_path, [v for _ in range(4) for v in (x,y)])
    m = scan.prediction_metrics(paths, shape, scan.ANCHOR, np.array([1.,2.,3.]))
    assert m['negative_counts'] == [0,0] and m['minimum_fields'] == [0.,0.]
    assert m['predicted_residual'] == pytest.approx(.0001/1.0001)
    assert m['predicted_boundary_l1'] == pytest.approx(.0001/1.0001)


def test_small_residual_does_not_override_constraint_budget_or_rank():
    m = {'negative_counts':[0,0], 'predicted_residual':1e-8,
         'predicted_boundary_l1':1e-8,'predicted_boundary_bolometric':1e-8}
    assert not all(scan.checks(scan.ANCHOR,m,1e-4,2,True).values())
    assert not all(scan.checks(scan.ANCHOR,m,1e-4,3,False).values())
    m['negative_counts'] = [1,0]
    assert not all(scan.checks(scan.ANCHOR,m,1e-4,3,True).values())
