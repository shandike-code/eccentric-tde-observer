"""Replay sign certificates using integer arithmetic, independently of Fraction kernel."""
import argparse
import hashlib
import json
import math
import subprocess
import tarfile
from pathlib import Path

ROOT = Path('outputs/review-20260925')


def read(path):
    return json.loads(Path(path).read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def integer_certificate(source_hex, coefficients):
    # 所有binary64分母都是2的幂；先通分成整数再求线性组合，独立于生产Fraction路径。
    values = [float.fromhex(v) for v in source_hex]
    assert len(values) == 4 and len(coefficients) == 3
    assert all(math.isfinite(v) for v in values + coefficients)
    vr = [v.as_integer_ratio() for v in values]
    cr = [v.as_integer_ratio() for v in coefficients]
    vd = max(d for _, d in vr)
    cd = max(d for _, d in cr)
    vi = [n * (vd // d) for n, d in vr]
    ci = [n * (cd // d) for n, d in cr]
    full = vi[0] * cd + sum(c * (v - vi[0]) for c, v in zip(ci, vi[1:]))
    half = vi[0] * cd + full
    result = {}
    for name, n, d in [('full', full, vd * cd), ('half', half, 2 * vd * cd)]:
        common = math.gcd(n, d)
        n, d = n // common, d // common
        result[name] = dict(sign=(n > 0) - (n < 0), numerator=str(n),
                            denominator_power_of_two=d.bit_length()-1)
    return result


def integer_bound(source_hex,coefficients):
    vr=[float.fromhex(v).as_integer_ratio() for v in source_hex]
    cr=[v.as_integer_ratio() for v in coefficients]
    vd=max(d for _,d in vr);cd=max(d for _,d in cr)
    vi=[n*(vd//d) for n,d in vr];ci=[n*(cd//d) for n,d in cr]
    dn=sum(c*(v-vi[0]) for c,v in zip(ci,vi[1:]))
    if dn>=0:return None
    n=vi[0]*cd;d=-dn;g=math.gcd(n,d);n//=g;d//=g
    return dict(numerator=str(n),denominator=str(d),float=n/d)


def review(job, commit):
    base = ROOT / f'{job}-subnormal-review'
    receipt = read(str(base)+'.json')
    archive = Path(str(base)+'.tar.gz')
    assert archive.stat().st_size == receipt['size_bytes'] and sha(archive.read_bytes()) == receipt['sha256']
    out = ROOT / f'x20-subnormal-audit-{job}-received'
    out.mkdir(exist_ok=False)
    ix = {r['path']: r for r in receipt['files']}
    assert set(ix) == {'declaration.json', 'exact-signs.json', 'summary.json', 'status.json',
                       'scheduler-terminal.json', 'stderr.log'}
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        assert len(members) == len(ix)
        for m in members:
            assert m.isfile() and m.name in ix and m.name == Path(m.name).name
            data = tar.extractfile(m).read()
            assert len(data) == ix[m.name]['size_bytes'] and sha(data) == ix[m.name]['sha256']
            (out/m.name).write_bytes(data)
    d, signs, s, terminal = [read(out/(n+'.json')) for n in
                              ('declaration', 'exact-signs', 'summary', 'scheduler-terminal')]
    assert job == 83075 and commit == 'd2582719dbf222f3de5a6916d779e2b953791741'
    assert d['job_id'] == str(job) and d['git_commit'] == commit and d['source_job'] == 83063
    assert terminal['job_id'] == job and terminal['state'] == 'COMPLETED'
    for token in ('ExitCode=0:0', 'NumCPUs=4', 'QOS=qos_stu_default', 'TimeLimit=01:00:00'):
        assert token in terminal['scontrol']
    assert not (out/'stderr.log').read_bytes()
    assert read(out/'status.json')['status'] == s['status'] == 'exact_sign_audit_complete_requires_review'
    original = read(ROOT/'x20-historical-heating-prediction-83063-received/declaration.json')
    assert d['fields'] == original['fields'] and d['shape'] == [9632, 32, 4096]
    assert d['coefficients'] == original['global_coefficients'] == [0., -7.2, 3.7942299325052176]
    assert d['targets'] == [9440, 9472] and d['maximum_unique_tuples_per_slab_kind'] == 4096
    for c in d['code']:
        data = subprocess.check_output(['git', 'show', commit+':'+c['path']])
        assert len(data) == c['size_bytes'] and sha(data) == c['sha256'], c['path']
    for c in d['source_claims']:
        path = Path(c['path'])
        prefix = 'outputs/hpc/x20-82989-heating-prediction-20261001/'
        if c['path'].startswith(prefix):
            path = ROOT/'x20-historical-heating-prediction-83063-received'/c['path'][len(prefix):]
        data = path.read_bytes()
        assert len(data) == c['size_bytes'] and sha(data) == c['sha256']
    totals = []
    prediction = read(ROOT/'x20-historical-heating-prediction-83063-received/prediction.json')
    original_slabs = {r['first_group']: r for r in prediction['slabs']}
    assert [r['first_group'] for r in signs['slabs']] == [9440, 9472]
    for slab in signs['slabs']:
        assert slab['group_count'] == 32
        assert slab['minima_hex'] == [v.hex() for v in original_slabs[slab['first_group']]['minima']]
        assert [r['kind'] for r in slab['checks']] == ['input', 'predicted_output', 'half_input', 'half_predicted_output']
        for row in slab['checks']:
            assert row['kind'] in ('input', 'predicted_output', 'half_input', 'half_predicted_output')
            cases = row['cases']
            assert 0 < len(cases) == row['unique_count'] <= 4096
            assert len({tuple(c['source_hex']) for c in cases}) == len(cases)
            assert sum(c['count'] for c in cases) == row['negative_count']
            for c in cases:
                assert isinstance(c['count'], int) and c['count'] > 0
                index = c['first_index']
                assert slab['first_group'] <= index[0] < slab['first_group']+32
                assert 0 <= index[1] < 32 and 0 <= index[2] < 4096
                assert float.fromhex(c['observed_binary64_hex']) < 0
                v = [float.fromhex(x) for x in c['source_hex']]
                cf = d['coefficients']
                observed = v[0] + cf[0]*(v[1]-v[0]) + cf[1]*(v[2]-v[0]) + cf[2]*(v[3]-v[0])
                if row['kind'].startswith('half_'):observed=.5*v[0]+.5*observed
                assert observed.hex() == c['observed_binary64_hex']
                result = integer_certificate(c['source_hex'], d['coefficients'])
                for kind in ('full', 'half'):
                    assert result[kind] == {k: c[kind][k] for k in result[kind]}
                    n=int(result[kind]['numerator']);den=1 << result[kind]['denominator_power_of_two']
                    assert (n/den).hex()==c[kind]['rounded_binary64_hex']
                bound=integer_bound(c['source_hex'],d['coefficients'])
                assert bound==c['full_direction_upper_fraction']
            for kind in ('full', 'half'):
                counts = {str(sign): sum(c['count'] for c in cases if c[kind]['sign'] == sign)
                          for sign in (-1, 0, 1)}
                assert counts == row[f'exact_{kind}_sign_counts']
            totals.append(dict(first_group=slab['first_group'], kind=row['kind'],
                               negative_count=row['negative_count'], unique_count=row['unique_count'],
                               full=row['exact_full_sign_counts'], half=row['exact_half_sign_counts']))
    for obj in (d, s):
        assert all(obj[k] == 0 for k in ('new_maps', 'new_feedback_pairs', 'new_material_steps'))
        assert obj['field_written'] is False and obj['baseline_replaced'] is False
    assert s['peak_rss_bytes'] < 6*1024**3
    result = dict(job_id=job, commit=commit, receipt=receipt, integer_certificates_verified=True,
                  code_and_source_claims_verified=True, full_fields_recomputed_on_mac=False,
                  scope=signs['scope'], counts=totals, summary=s, local_upper_fraction=min(c['full_direction_upper_fraction']['float'] for slab in signs['slabs'] for row in slab['checks'] for c in row['cases'] if c['full_direction_upper_fraction'] is not None), original_83063_rejection_preserved=True)
    target = Path(f'handoff/evidence/20261001-x20-subnormal-{job}-review.json')
    with target.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(dict(counts=totals, summary=s), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--job', type=int, required=True); p.add_argument('--commit', required=True)
    a = p.parse_args(); review(a.job, a.commit)
