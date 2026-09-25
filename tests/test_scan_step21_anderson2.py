import numpy as np
import pytest
from operations import scan_step21_anderson2 as scan


def files(tmp_path, values):
    paths = [tmp_path/str(i) for i in range(4)]
    for p, a in zip(paths, values):
        a.tofile(p)
    return paths


def test_two_mode_affine_problem_recovers_known_fixed_point_without_writing(tmp_path):
    shape = (8, 4, 2); star = np.full(shape, 10.)
    lam = np.broadcast_to(np.array([.5, .8]), shape)
    values = [star+lam**i for i in range(4)]
    paths = files(tmp_path, values); before = [p.read_bytes() for p in paths]
    result = scan.scan(paths, shape, np.arange(9.)+1, .01, chunk=2)
    assert result['selected']['eta'] == 1.
    q, p = scan.affine_pair(values, result['solve']['uv'], 1.)
    np.testing.assert_allclose(q, star, rtol=0, atol=3e-12)
    np.testing.assert_allclose(p, star+lam*(q-star), rtol=0, atol=1e-14)
    assert result['selected']['predicted_global_residual'] < 1e-12
    assert result['candidate_written'] is False and result['new_maps'] == 0
    assert [p.read_bytes() for p in paths] == before
    assert len(list(tmp_path.iterdir())) == 4
    for row in result['candidates']:
        assert [(s['start'], s['stop']) for s in row['slabs']] == [(0, 2), (2, 4), (4, 6), (6, 8)]


def test_singular_or_unresolved_differences_are_rejected_without_regularization():
    for g in (np.zeros((2, 2)), np.ones((2, 2)), np.diag([1., 1e-12])):
        assert not scan.solve_coefficients(g, np.ones(2))['resolved']
    result = scan.solve_coefficients(np.eye(2), np.zeros(2))
    assert result['resolved'] and result['normal_equation_relative_residual'] == 0


def test_negative_candidate_rejected_not_clipped(tmp_path, monkeypatch):
    shape = (2, 4, 2); values = [np.full(shape, v) for v in (1., 2., 100., 101.)]
    monkeypatch.setattr(scan, 'solve_coefficients', lambda *a: {'resolved': True, 'uv': [0., 10.]})
    result = scan.scan(files(tmp_path, values), shape, np.arange(3.)+1, .1, chunk=1)
    assert result['selected'] is None
    assert all(not r['gates']['positive'] for r in result['candidates'])
    assert all(any(s['minimum_q'] < 0 for s in r['slabs']) for r in result['candidates'])


def test_large_coefficients_not_silently_damped_beyond_declared_grid(tmp_path, monkeypatch):
    shape = (2, 4, 2); values = [np.full(shape, i+1.) for i in range(4)]
    monkeypatch.setattr(scan, 'solve_coefficients', lambda *a: {'resolved': True, 'uv': [10000., 0.]})
    result = scan.scan(files(tmp_path, values), shape, np.arange(3.)+1, .1, chunk=1)
    assert result['selected'] is None and len(result['candidates']) == 4
    assert all(r['reason'] == 'coefficient l1 limit' for r in result['candidates'])


@pytest.mark.parametrize('bad', ['nan', 'negative', 'edges'])
def test_invalid_inputs_fail(tmp_path, bad):
    shape = (2, 4, 2); values = [np.ones(shape)*(i+1) for i in range(4)]
    if bad != 'edges':
        values[0][0, 0, 0] = np.nan if bad == 'nan' else -1
    edges = np.ones(3) if bad == 'edges' else np.arange(3.)+1
    with pytest.raises(ValueError):
        scan.scan(files(tmp_path, values), shape, edges, .1)


def test_lineage_must_match_all_four_states():
    rows = [dict(input_sha256=a, output_sha256=b) for a, b in zip('abc', 'bcd')]
    state = dict(history=rows, active_map=None)
    retained = dict(history_rows=rows[1:], endpoints={k: {'sha256': v} for k, v in zip(('previous', 'final', 'mapped_final'), 'bcd')})
    validation = dict(actual_map=rows[0], candidate={'sha256': 'a'})
    assert [v['sha256'] for v in scan.four_basis(state, retained, validation)] == list('abcd')
    validation['candidate']['sha256'] = 'wrong'
    with pytest.raises(ValueError):
        scan.four_basis(state, retained, validation)


def test_nonfinite_normal_equation_rejected():
    with pytest.raises(ValueError):
        scan.solve_coefficients(np.eye(2), np.array([np.nan, 1.]))
