import numpy as np
import pytest
from operations.scan_positive_subspace import solve_constrained, collect_cuts
from operations.scan_multihistory_subspace import residual_system, bounded_step, fields
from operations.prepare_mixed_followup import latest_seed
from tests.test_multihistory_subspace import files


def test_qp_known_active_constraint_and_sum_one():
    anchor = np.array([0., 1., 0., 0.])
    target, info = solve_constrained(np.eye(3), [2., 0., 0.], anchor, [[-1., 0., 0.]], [-.5])
    np.testing.assert_allclose(target, [.5, .5, 0., 0.], atol=1e-10)
    assert target.sum() == pytest.approx(1.)
    assert info['maximum_linear_constraint_violation'] < 1e-10


def test_zero_anchor_constraint_is_not_discarded():
    target, _ = solve_constrained(np.eye(3), [-2., 0., 0.], [0., 1., 0., 0.], [[1., 0., 0.]], [0.])
    assert target[0] >= -1e-10


def test_l1_cap_is_an_explicit_coefficient_constraint():
    target, _ = solve_constrained(np.eye(3), [100., 0., 0.], [0., 1., 0., 0.], [], [])
    assert np.sum(abs(target)) <= 32.+1e-10
    assert target[0] == pytest.approx(16.5)


@pytest.mark.parametrize('scale', [1., 1e-260])
def test_negative_cells_located_and_constraints_scale_invariant(tmp_path, scale):
    shape = (1, 4, 2)
    arrays = [np.full(shape, v*scale) for v in (1., 1., 1., 10., 10., 10.)]
    paths = files(tmp_path, arrays); before = [p.read_bytes() for p in paths]
    cuts, stats = collect_cuts(paths, shape, np.array([0., 1., 0., 0.]), np.array([0., 2., 0., -1.]))
    assert stats['candidate']['negative_count'] == 8
    assert stats['predicted_map']['negative_count'] == 8
    assert stats['candidate']['positivity_step_upper'] == pytest.approx(1/9)
    np.testing.assert_allclose(cuts[0]['row'], [0., .9, .9])
    assert cuts[0]['lower'] == pytest.approx(-.1)
    assert [p.read_bytes() for p in paths] == before


def test_known_affine_root_survives_constrained_pipeline(tmp_path):
    root = np.full((1, 4, 2), 10.)
    q = np.array([.2, .5, .9, .2, .5, .9, .2, .5]).reshape(root.shape)
    f = lambda x: root+q*(x-root)
    # 每个特征模只用同一个幅度；此时已知根确实位于三个差残差方向张成的空间。
    b0 = root+np.array([1., 2., 3., 1., 2., 3., 1., 2.]).reshape(root.shape)
    o0 = root+np.array([3., -1., 1., 3., -1., 1., 3., -1.]).reshape(root.shape)
    arrays = [b0, f(b0), f(f(b0)), o0, f(o0), f(f(o0))]
    paths = files(tmp_path, arrays); anchor = np.array([0., .8, 0., .2])
    _, system = residual_system(paths, root.shape, anchor)
    target, _ = solve_constrained(system['gram'], system['rhs'], anchor, [], [])
    cuts, stats = collect_cuts(paths, root.shape, anchor, target)
    assert not cuts and stats['candidate']['negative_count'] == 0
    step, _ = bounded_step(paths, root.shape, anchor, target)
    assert step == 1.
    x, y = fields(arrays, target)
    assert np.max(abs(y-x)) < 1e-7


def test_rank_loss_and_infeasible_anchor_rejected():
    with pytest.raises(ValueError, match='three resolved'):
        solve_constrained(np.diag([1., 1., 0.]), np.zeros(3), [0., 1., 0., 0.], [], [])
    with pytest.raises(ValueError, match='satisfy every cut'):
        solve_constrained(np.eye(3), np.zeros(3), [0., 1., 0., 0.], [[1., 0., 0.]], [1.])


def test_followup_rejects_unsettled_source():
    with pytest.raises(ValueError, match='stopped and settled'):
        latest_seed({'status': 'radiation', 'history': [1]})
