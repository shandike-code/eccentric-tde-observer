"""Reaggregate the small four-state scan archive without loading large fields."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np
import matplotlib.pyplot as plt


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def review(archive, receipt, prior, output):
    claim = json.loads(receipt.read_text())
    assert archive.stat().st_size == claim['size_bytes'] and digest(archive) == claim['sha256']
    with tarfile.open(archive) as t:
        assert all(m.isfile() and '/' not in m.name for m in t.getmembers())
        content = {m.name: t.extractfile(m).read() for m in t.getmembers()}
    manifest = json.loads(content['ARCHIVE_MANIFEST.json'])
    assert set(content) == {'ARCHIVE_MANIFEST.json', *[c['path'] for c in manifest['files']]}
    for c in manifest['files']:
        assert len(content[c['path']]) == c['size_bytes'] and hashlib.sha256(content[c['path']]).hexdigest() == c['sha256']
    d = json.loads(content['declaration.json']); p = json.loads(content['prediction.json']); status = json.loads(content['status.json'])
    assert status['status'] == 'complete_requires_review' and status['accepted_outer_steps'] == 20
    assert status['new_maps'] == status['new_material_steps'] == 0 and status['candidate_written'] is False
    assert d['etas'] == [1., .5, .25, .125] and d['chunk'] == 16
    assert d['condition_limit'] == 1e10 and d['coefficient_l1_limit'] == 192
    for c in d['code']:
        f = Path(c['path']); assert f.stat().st_size == c['size_bytes'] and digest(f) == c['sha256']
    prefix = 'outputs/hpc/step21-radiation-affine-validation-20260925/'
    claims = {c['path']: c for c in d['claims']}; rows = {}
    assert set(p) == {'control', 'thermal', 'population'}
    grid = [(i, min(i+16, 9632)) for i in range(0, 9632, 16)]
    for case, h in p.items():
        for name in ('state.json', 'config.json', 'trial_material.npz', 'validation.json', 'endpoints-map03/manifest.json'):
            c = claims[prefix+case+'/'+name]; f = prior/case/name
            assert f.stat().st_size == c['size_bytes'] and digest(f) == c['sha256']
        state = json.loads((prior/case/'state.json').read_text()); history = state['history']
        assert state['active_map'] is None and len(history) == 3
        ret = json.loads((prior/case/'endpoints-map03/manifest.json').read_text())
        val = json.loads((prior/case/'validation.json').read_text())
        expected = [val['candidate']] + [ret['endpoints'][k] for k in ('previous', 'final', 'mapped_final')]
        assert d['cases'][case]['basis'] == expected
        assert [c['sha256'] for c in expected] == [history[0]['input_sha256']] + [v['output_sha256'] for v in history]
        assert h['latest_actual_residual'] == history[-1]['residual']
        assert h['new_maps'] == 0 and h['candidate_written'] is False and h['fresh_map_required']
        assert not h['strict_error_bound'] and h['peak_rss_bytes'] < 6*1024**3
        gs = h['gram_slabs']; assert [(s['start'], s['stop']) for s in gs] == grid
        g = sum((np.array(s['gram']) for s in gs), np.zeros((2, 2)))
        b = sum((np.array(s['rhs']) for s in gs), np.zeros(2))
        np.testing.assert_array_equal(g, h['gram']); np.testing.assert_array_equal(b, h['rhs'])
        # 生产端逐片 +=；Python sum 的补偿算法与此不一定逐位一致。
        accumulated_r2 = 0.
        for s in gs:
            accumulated_r2 += s['r2_squared']
        assert accumulated_r2 == h['r2_squared']
        scale = np.max(abs(g)); eig = np.linalg.eigvalsh(g/scale) if scale else np.zeros(2)
        resolved = bool(eig[0] > 0 and eig[-1]/eig[0] < 1e10)
        assert h['solve']['resolved'] == resolved
        if not resolved:
            assert h['selected'] is None and h['candidates'] == []
            rows[case] = {'resolved': False, 'selected': None}; continue
        uv = np.linalg.solve(g/scale, -b/scale)
        np.testing.assert_allclose(uv, h['solve']['uv'], rtol=1e-12, atol=0)
        # 跨CPU线性求解不要求逐位一致；上行独立复算系数用1e-12核对。
        # 随后严格验证Linux声明系数到候选记录的算术血缘，不放宽任何科学门。
        solve_scale = float(np.max(np.abs(h['solve']['uv'])))
        solve_relative_difference = float(np.max(np.abs(uv-np.array(h['solve']['uv'])))/solve_scale) if solve_scale else 0.
        uv = np.array(h['solve']['uv'])
        assert [c['eta'] for c in h['candidates']] == d['etas']
        for candidate in h['candidates']:
            u, v = uv*candidate['eta']; coef = [v, u, 1-u-v]
            np.testing.assert_array_equal(coef, candidate['coefficients'])
            l1coef = float(np.sum(np.abs(coef))); assert l1coef == candidate['coefficient_l1']
            ss = candidate['slabs']
            if l1coef >= 192:
                assert ss == [] and not candidate['feasible']; continue
            assert [(s['start'], s['stop']) for s in ss] == grid
            assert all(np.isfinite(x) for s in ss for x in s.values())
            for s in ss:
                assert s['local_relative'] == (s['change']/s['scale'] if s['scale'] else 0.)
                assert (s['minimum_q'] >= 0) == (s['negative_q'] == 0)
                assert (s['minimum_p'] >= 0) == (s['negative_p'] == 0)
            total = lambda k: sum(s[k] for s in ss)
            global_res = max(s['change'] for s in ss)/max(s['scale'] for s in ss)
            l1 = total('boundary_num')/max(total('q_abs_flux'), total('p_abs_flux'))
            bol = abs(total('p_bol')-total('q_bol'))/max(abs(total('q_bol')), abs(total('p_bol')))
            for name, value in [('predicted_global_residual', global_res), ('predicted_boundary_l1', l1), ('predicted_boundary_bolometric', bol), ('predicted_ratio', global_res/history[-1]['residual'])]:
                assert value == candidate[name]
            gates = dict(positive=total('negative_q') == total('negative_p') == 0,
                maximum_improves=global_res/history[-1]['residual'] < .99, strict_inner=global_res < 1e-4,
                boundary_l1=l1 < 1e-3, boundary_bolometric=bol < 1e-3)
            assert gates == candidate['gates'] and candidate['feasible'] == all(gates.values())
        eligible = [c for c in h['candidates'] if c['feasible']]
        selected = min(eligible, key=lambda c: c['predicted_global_residual']) if eligible else None
        assert h['selected'] == ({k: selected[k] for k in ('eta', 'coefficients', 'predicted_ratio', 'predicted_global_residual')} if selected else None)
        rows[case] = dict(resolved=True, selected=h['selected'], condition=h['solve']['condition'],
                         cross_cpu_solve_relative_difference=solve_relative_difference)
    result = dict(archive=claim, verified_files=len(manifest['files']), verified_code_claims=len(d['code']), cases=rows,
                  large_fields_recomputed_on_mac=False, fresh_map_required=True, accepted_outer_steps=20, new_maps=0)
    output.with_suffix('.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for name, h in p.items():
        for c in h['candidates']:
            if c['slabs']:
                axes[0].plot([s['start'] for s in c['slabs']], [s['local_relative'] for s in c['slabs']], label=f"{name} eta={c['eta']}")
                axes[1].scatter(c['eta'], c['predicted_ratio'], marker='o' if c['feasible'] else 'x')
    axes[0].set(xlabel='First frequency index of slab', ylabel='Local relative predicted residual', yscale='log')
    if axes[0].lines: axes[0].legend(fontsize=6)
    axes[1].axhline(.99, color='black'); axes[1].set(xlabel='Damping eta', ylabel='Predicted / latest global residual')
    fig.suptitle('Read-only algebraic prediction; no new transfer map'); fig.savefig(output.with_suffix('.png'), dpi=150); plt.close(fig)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('archive', 'receipt', 'prior', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    print(json.dumps(review(**vars(parser.parse_args())), indent=2))
