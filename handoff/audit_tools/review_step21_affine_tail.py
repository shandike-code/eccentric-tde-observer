"""Independent exact rational replay of archived radiation-tail witnesses."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import tarfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fraction(record):
    q = Fraction(int(record['numerator']), int(record['denominator']))
    assert record['sign'] == (q > 0)-(q < 0)
    return q


def review(archive, receipt, scan_archive, output):
    claim = json.loads(receipt.read_text())
    assert archive.stat().st_size == claim['size_bytes'] and digest(archive) == claim['sha256']
    with tarfile.open(archive) as t:
        assert all(m.isfile() and '/' not in m.name for m in t.getmembers())
        contents = {m.name: t.extractfile(m).read() for m in t.getmembers()}
    manifest = json.loads(contents['ARCHIVE_MANIFEST.json'])
    assert set(contents) == {'ARCHIVE_MANIFEST.json', *[c['path'] for c in manifest['files']]}
    for c in manifest['files']:
        assert len(contents[c['path']]) == c['size_bytes'] and hashlib.sha256(contents[c['path']]).hexdigest() == c['sha256']
    declaration = json.loads(contents['declaration.json']); result = json.loads(contents['diagnosis.json']); status = json.loads(contents['status.json'])
    assert status['status'] == 'complete_requires_review' and status['accepted_outer_steps'] == 20
    assert status['new_maps'] == status['new_material_steps'] == 0 and not status['candidate_written']
    assert declaration['frequency_range'] == [9424, 9504] and declaration['longdouble_mantissa_bits'] > 52
    for c in declaration['code']:
        p = Path(c['path']); assert p.stat().st_size == c['size_bytes'] and digest(p) == c['sha256']
    scan_claim = json.loads(Path('handoff/evidence/20260925-step21-anderson2-review.json').read_text())['archive']
    assert scan_archive.stat().st_size == scan_claim['size_bytes'] and digest(scan_archive) == scan_claim['sha256']
    with tarfile.open(scan_archive) as t:
        prediction_bytes = t.extractfile('prediction.json').read(); prediction = json.loads(prediction_bytes)
        source_declaration = json.load(t.extractfile('declaration.json'))
    old_claim = next(c for c in declaration['claims'] if c['path'] == declaration['source']+'/prediction.json')
    assert hashlib.sha256(prediction_bytes).hexdigest() == old_claim['sha256']
    claim_set = {(c['path'], c['size_bytes'], c['sha256']) for c in declaration['claims']}
    assert all((c['path'], c['size_bytes'], c['sha256']) in claim_set for c in source_declaration['claims']+source_declaration['code'])
    rows = {}; witnesses = 0
    assert set(result) == {'control', 'thermal', 'population'}
    for case, current in result.items():
        source = prediction[case]; assert current['uv'] == source['solve']['uv'] and current['peak_rss_bytes'] < 6*1024**3
        expected = [c for c in source['candidates'] if c['slabs']]
        assert [c['eta'] for c in current['candidates']] == [c['eta'] for c in expected]
        rows[case] = []
        for candidate, old in zip(current['candidates'], expected):
            original = {s['start']: s for s in old['slabs']}
            assert [(s['start'], s['stop']) for s in candidate['slabs']] == [(i, i+16) for i in range(9424, 9504, 16)]
            exact_negative = zero_obstructions = native_neg = extended_neg = 0
            for slab in candidate['slabs']:
                assert set(slab['fields']) == {'q', 'p'}
                for label, field in slab['fields'].items():
                    assert label in ('q', 'p')
                    assert field['native_negative_count'] == original[slab['start']]['negative_'+label]
                    assert field['native_minimum'] == original[slab['start']]['minimum_'+label]
                    native_neg += field['native_negative_count']; extended_neg += field['extended_negative_count']
                    assert 0 <= field['extended_negative_count'] <= 16*32*4096
                    assert field['exact_witnesses']
                    for w in field['exact_witnesses']:
                        assert w['label'] == label and float.fromhex(w['eta_hex']) == candidate['eta']
                        assert list(map(float.fromhex, w['uv_hex'])) == current['uv']
                        index = w['index']; assert slab['start'] <= index[0] < slab['stop'] and 0 <= index[1] < 32 and 0 <= index[2] < 4096
                        x = [Fraction.from_float(float.fromhex(s)) for s in w['inputs_hex']]
                        u, v = [Fraction.from_float(float.fromhex(s)) for s in w['uv_hex']]
                        eta = Fraction.from_float(float.fromhex(w['eta_hex'])); j = 2 if label == 'q' else 3
                        xf = list(map(float, x)); uf, vf = float(u)*float(eta), float(v)*float(eta)
                        native = xf[j]+uf*(xf[j-1]-xf[j])+vf*(xf[j-2]-xf[j])
                        assert native.hex() == w['native_value_hex']
                        value = x[j]+eta*u*(x[j-1]-x[j])+eta*v*(x[j-2]-x[j])
                        slope = u*(x[j-1]-x[j])+v*(x[j-2]-x[j])
                        assert value == fraction(w['value']) and slope == fraction(w['slope']) and x[j] == fraction(w['base'])
                        bound = x[j]/(-slope) if slope < 0 else None
                        assert (fraction(w['positive_eta_upper_bound']) if w['positive_eta_upper_bound'] is not None else None) == bound
                        obstructs = x[j] == 0 and slope < 0
                        assert w['no_positive_eta_on_this_ray'] == obstructs
                        exact_negative += int(value < 0); zero_obstructions += int(obstructs); witnesses += 1
            rows[case].append(dict(eta=candidate['eta'], native_negative_count=native_neg, extended_negative_count=extended_neg,
                                   exact_negative_witnesses=exact_negative, exact_zero_base_obstructions=zero_obstructions))
    audited = dict(archive=claim, verified_files=len(manifest['files']), verified_code_claims=len(declaration['code']),
                   exact_witnesses_replayed=witnesses, cases=rows, large_field_cells_recomputed_on_mac=False,
                   witnesses_not_exhaustive=True, accepted_outer_steps=20, new_maps=0)
    output.with_suffix('.json').write_text(json.dumps(audited, indent=2)+'\n')
    import matplotlib.pyplot as plt
    labels = []; n64 = []; nw = []; zeros = []
    for case, values in rows.items():
        for r in values:
            labels.append(f"{case} eta={r['eta']}"); n64.append(r['native_negative_count'])
            nw.append(r['extended_negative_count']); zeros.append(r['exact_zero_base_obstructions'])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
    axes[0].plot(labels, n64, 'o-', label='float64'); axes[0].plot(labels, nw, 'x--', label='longdouble'); axes[0].legend()
    axes[0].set(ylabel='Negative cells in inspected tail'); axes[1].bar(labels, zeros)
    axes[1].set(ylabel='Exact zero-base obstruction witnesses')
    for ax in axes: ax.tick_params(axis='x', labelrotation=35)
    fig.suptitle('Same stored basis and direction; no clipped or newly mapped field')
    fig.savefig(output.with_suffix('.png'), dpi=150); plt.close(fig)
    return audited


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('archive', 'receipt', 'scan-archive', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    print(json.dumps(review(**vars(p.parse_args())), indent=2))
