"""Replay small constrained-scan evidence, including every positivity cut."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import numpy as np
from operations.scan_step21_positive_plane import solve_plane


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_archive(path):
    with tarfile.open(path) as t:
        assert all(m.isfile() and '/' not in m.name for m in t.getmembers())
        raw = {m.name: t.extractfile(m).read() for m in t.getmembers()}
    manifest = json.loads(raw['ARCHIVE_MANIFEST.json'])
    assert set(raw) == {'ARCHIVE_MANIFEST.json', *[c['path'] for c in manifest['files']]}
    for c in manifest['files']:
        assert len(raw[c['path']]) == c['size_bytes'] and hashlib.sha256(raw[c['path']]).hexdigest() == c['sha256']
    return {k: json.loads(v) for k, v in raw.items()}


def cut_key(c):
    return (c['label'], *c['index'])


def check_cut(c):
    x = np.array([float.fromhex(v) for v in c['inputs_hex']]); j = 2 if c['label'] == 'q' else 3
    assert c['label'] in ('q', 'p') and np.isfinite(x).all() and np.all(x >= 0)
    values = x[j-2:j+1]; assert values.max() > 0
    values = values/values.max()
    np.testing.assert_array_equal(c['row'], [values[1]-values[2], values[0]-values[2]])
    assert c['lower'] == -values[2]
    f, m, z = c['index']; assert 0 <= f < 9632 and 0 <= m < 32 and 0 <= z < 4096


def review(archive, receipt, scan_archive, tail_archive, output):
    claim = json.loads(receipt.read_text())
    assert archive.stat().st_size == claim['size_bytes'] and digest(archive) == claim['sha256']
    contents = read_archive(archive); d = contents['declaration.json']; pred = contents['prediction.json']; status = contents['status.json']
    assert status['status'] == 'complete_requires_review' and status['accepted_outer_steps'] == 20
    assert status['new_maps'] == status['new_material_steps'] == 0 and not status['candidate_written']
    assert (d['maximum_passes'], d['maximum_cuts'], d['coefficient_cap'], d['common_retreat']) == (6, 4096, 191., .99)
    for c in d['code']:
        p = Path(c['path']); assert p.stat().st_size == c['size_bytes'] and digest(p) == c['sha256']
    histories = {}
    for name, path, report in [('scan', scan_archive, '20260925-step21-anderson2-review.json'), ('tail', tail_archive, '20260925-step21-tail-review.json')]:
        a = json.loads((Path('handoff/evidence')/report).read_text())['archive']
        assert path.stat().st_size == a['size_bytes'] and digest(path) == a['sha256']
        histories[name] = read_archive(path)
    claims = {(c['path'], c['size_bytes'], c['sha256']) for c in d['claims']}
    for name in ('scan', 'tail'):
        original = histories[name]['declaration.json']
        assert all((c['path'], c['size_bytes'], c['sha256']) in claims for c in original['claims']+original['code'])
    source = histories['scan']['prediction.json']; tail = histories['tail']['diagnosis.json']; reviewed = {}
    assert set(pred) == {'control', 'thermal', 'population'}
    for case, result in pred.items():
        assert contents[case+'-progress.json'] == {'rounds': result['rounds'], 'cuts': result['cuts']}
        assert not any(result[k] for k in ('candidate_written', 'actual_map_performed', 'accepted_material_step', 'full_constrained_optimum_proven'))
        assert result['peak_rss_bytes'] < 6*1024**3 and 1 <= len(result['rounds']) <= 6
        witnessed = {}
        for c in tail[case]['candidates']:
            for s in c['slabs']:
                for f in s['fields'].values():
                    for w in f['exact_witnesses']:
                        witnessed[(w['label'], *w['index'])] = w['inputs_hex']
        cuts = {}
        for c in result['initial_cuts']:
            check_cut(c); assert c['inputs_hex'] == witnessed[cut_key(c)]; cuts[cut_key(c)] = c
        assert set(cuts) == set(witnessed)
        for round_index, row in enumerate(result['rounds']):
            assert row['input_cut_count'] == len(cuts) <= 4096
            replay = solve_plane(source[case]['gram'], source[case]['rhs'], list(cuts.values()))
            # 同一小矩阵算法重放不是另一优化器；跨CPU系数给有限舍入余量，科学门仍精确核对。
            np.testing.assert_allclose(replay['effective_uv'], row['solve']['effective_uv'], rtol=1e-10, atol=1e-12)
            assert row['solve']['retreat'] == .99
            np.testing.assert_array_equal(np.array(row['solve']['raw_uv'])*.99, row['solve']['effective_uv'])
            r = row['result']; assert r['uv'] == row['solve']['effective_uv']; u, v = r['uv']
            assert r['coefficients'] == [v, u, 1-u-v]
            slabs = r['slabs']; assert [(s['start'], s['stop']) for s in slabs] == [(i, min(i+16, 9632)) for i in range(0, 9632, 16)]
            assert all(np.isfinite(a) for s in slabs for a in s.values())
            total = lambda k: sum(s[k] for s in slabs)
            scale = max(s['scale'] for s in slabs); glob = max(s['change'] for s in slabs)/scale
            l1 = total('boundary_num')/max(total('q_abs_flux'), total('p_abs_flux'))
            bol = abs(total('p_bol')-total('q_bol'))/max(abs(total('q_bol')), abs(total('p_bol')))
            assert glob == r['predicted_global_residual'] and glob/source[case]['latest_actual_residual'] == r['predicted_ratio']
            assert l1 == r['predicted_boundary_l1'] and bol == r['predicted_boundary_bolometric']
            gates = dict(positive=total('negative_q') == total('negative_p') == 0, coefficient_l1=sum(abs(x) for x in r['coefficients']) < 192,
                         coefficient_sum=abs(sum(r['coefficients'])-1.) < 1e-12,
                         strict_inner=glob < 1e-4, maximum_improves=r['predicted_ratio'] < .99, boundary_l1=l1 < 1e-3, boundary_bolometric=bol < 1e-3)
            assert gates == r['gates']
            if gates['positive']: assert round_index == len(result['rounds'])-1
            for c in r['cuts']:
                check_cut(c)
                if cut_key(c) in cuts: assert cuts[cut_key(c)] == c
                cuts[cut_key(c)] = c
        assert list(cuts.values()) == result['cuts']
        last = result['rounds'][-1]['result']
        assert result['feasible'] == (result['reason'] == 'positive_candidate_review_required' and all(last['gates'].values()))
        reviewed[case] = dict(passes=len(result['rounds']), cuts=len(cuts), feasible=result['feasible'], reason=result['reason'],
                             effective_uv=last['uv'], predicted_ratio=last['predicted_ratio'], gates=last['gates'])
    report = dict(archive=claim, verified_files=len(contents)-1, verified_code_claims=len(d['code']), cases=reviewed,
                  full_fields_recomputed_on_mac=False, optimizer_independently_reimplemented=False,
                  full_constrained_optimum_proven=False, accepted_outer_steps=20, new_maps=0)
    output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for case, result in pred.items():
        axes[0].plot(range(1, len(result['rounds'])+1), [r['result']['predicted_ratio'] for r in result['rounds']], 'o-', label=case)
        axes[1].plot(range(1, len(result['rounds'])+1), [sum(s['negative_q']+s['negative_p'] for s in r['result']['slabs']) for r in result['rounds']], 'o-', label=case)
    axes[0].axhline(.99, color='black'); axes[0].set(xlabel='Full-field pass', ylabel='Predicted / last actual residual'); axes[0].legend()
    axes[1].set(xlabel='Full-field pass', ylabel='Negative predicted cells'); fig.suptitle('Constrained coefficients: prediction only, no new transfer map')
    fig.savefig(output.with_suffix('.png'), dpi=150); plt.close(fig)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('archive', 'receipt', 'scan-archive', 'tail-archive', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    print(json.dumps(review(**vars(p.parse_args())), indent=2))
