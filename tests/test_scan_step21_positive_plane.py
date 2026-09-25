import numpy as np
import pytest
from operations import scan_step21_positive_plane as plane


def cut(row, lower=0, label='q', index=(0, 0, 0)):
    return dict(row=row, lower=lower, label=label, index=list(index))


def test_quadratic_minimum_on_known_half_plane():
    # 无约束最小点(-2,3)被u>=0截断；受约束精确解(0,3)。
    result = plane.solve_plane(np.eye(2), [2., -3.], [cut([1., 0.])])
    np.testing.assert_allclose(result['raw_uv'], [0., 3.], atol=1e-12)
    np.testing.assert_allclose(result['effective_uv'], [0., 2.97], atol=1e-12)


def test_joint_constraints_rotate_direction_instead_of_damping_the_same_ray():
    result = plane.solve_plane(np.eye(2), [2., -3.], [cut([1., 0.]), cut([0., -1.], -1.)])
    np.testing.assert_allclose(result['raw_uv'], [0., 1.], atol=1e-12)
    assert result['raw_uv'] != [-2., 3.]


def test_zero_anchor_and_coefficient_cap_remain_feasible():
    result = plane.solve_plane(np.eye(2), [1e6, -1e6], [])
    u, v = result['effective_uv']
    assert abs(u)+abs(v)+abs(1-u-v) < 192
    collapsed = plane.solve_plane(np.eye(2), [2., 3.], [cut([1., 0.]), cut([-1., 0.]), cut([0., 1.]), cut([0., -1.])])
    np.testing.assert_allclose(collapsed['effective_uv'], [0., 0.], atol=0)


def test_tail_constraint_normalization_does_not_drop_underflow_scale():
    tiny = np.nextafter(0., 1.)
    c = plane.make_cut([tiny, 2*tiny, tiny, 1e100], 'q', (9488, 1, 2))
    assert c['row'] == [.5, 0.] and c['lower'] == -.5
    assert list(map(float.fromhex, c['inputs_hex'])) == [tiny, 2*tiny, tiny, 1e100]


def test_full_field_negative_point_becomes_a_constraint_and_is_not_clipped(tmp_path):
    shape = (16, 4, 3); values = [np.full(shape, x) for x in (0., 0., 2., 3.)]
    paths = [tmp_path/str(i) for i in range(4)]
    for p, a in zip(paths, values): a.tofile(p)
    original = [p.read_bytes() for p in paths]
    r = plane.inspect_fields(paths, shape, [2., 0.], np.arange(17.)+1, .5)
    assert not r['gates']['positive'] and r['slabs'][0]['negative_q'] == np.prod(shape)
    assert r['slabs'][0]['minimum_q'] == -2
    assert len(r['cuts']) == 2 and all(c['row'][0] == -1 for c in r['cuts'])
    assert [p.read_bytes() for p in paths] == original


def test_finite_pass_budget_does_not_loop_on_repeated_witness(monkeypatch):
    monkeypatch.setattr(plane, 'MAX_PASSES', 3)
    seen = []
    def evaluate(uv, i):
        seen.append(i); return {'gates': {'positive': False}, 'cuts': [cut([1., 0.])]}
    r = plane.search(np.eye(2), [1., 1.], [], evaluate)
    assert seen == [0, 1, 2] and r['reason'] == 'pass_budget' and not r['feasible']


def test_positive_but_nonimproving_candidate_is_not_accepted():
    r = plane.search(np.eye(2), [1., 1.], [], lambda *args: {'gates': {'positive': True, 'maximum_improves': False}, 'cuts': []})
    assert len(r['rounds']) == 1 and not r['feasible']


def test_completed_round_is_saved_before_next_scan_can_fail():
    saved = []
    def evaluate(uv, index):
        if index == 1: raise InterruptedError('simulated signal')
        return {'gates': {'positive': False}, 'cuts': [cut([1., 0.])]}
    with pytest.raises(InterruptedError):
        plane.search(np.eye(2), [1., 1.], [], evaluate, save_round=lambda r, c: saved.append((len(r), len(c))))
    assert saved == [(1, 1)]


def test_changed_witness_and_cut_budget_stop(monkeypatch):
    with pytest.raises(RuntimeError, match='changed'):
        plane.search(np.eye(2), [1., 1.], [cut([1., 0.])], lambda *args: {'gates': {'positive': False}, 'cuts': [cut([2., 0.])]})
    monkeypatch.setattr(plane, 'MAX_CUTS', 0)
    r = plane.search(np.eye(2), [1., 1.], [cut([1., 0.])], lambda *args: pytest.fail('unexpected scan'))
    assert r['reason'] == 'cut_budget' and not r['rounds']


def test_two_mode_feasible_prediction_preserves_known_solution(tmp_path):
    shape = (16, 4, 2); lam = np.broadcast_to(np.array([.5, .8]), shape)
    values = [10+.1*lam**i for i in range(4)]; paths = [tmp_path/str(i) for i in range(4)]
    for p, a in zip(paths, values): a.tofile(p)
    r0, r1, r2 = (values[i+1]-values[i] for i in range(3)); ds = [r1-r2, r0-r2]
    g = [[np.sum(x*y) for y in ds] for x in ds]; b = [np.sum(x*r2) for x in ds]
    r = plane.search(g, b, [], lambda uv, n: plane.inspect_fields(paths, shape, uv, np.arange(17.)+1, .1))
    assert r['feasible'] and all(r['rounds'][0]['result']['gates'].values())
    assert r['rounds'][0]['result']['predicted_ratio'] < .01
    q, p = plane.base.affine_pair(values, r['rounds'][0]['solve']['effective_uv'], 1.)
    np.testing.assert_allclose(q, 10+(1-plane.RETREAT)*.1*lam**2, rtol=0, atol=2e-12)
    np.testing.assert_allclose(p, 10+lam*(q-10), rtol=0, atol=1e-14)
