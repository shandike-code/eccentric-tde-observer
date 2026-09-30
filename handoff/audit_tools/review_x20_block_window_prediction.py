"""Audit 82472, including scientifically rejected but operationally complete runs.

No production field kernel or candidate optimizer is used. Gram comparisons test
arithmetic consistency; they are not bounds on the true radiation solution.
"""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import tarfile

import numpy as np
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT, digest, read
from handoff.audit_tools.review_x20_window_prediction import reduce_prediction


def local_path(path):
    for run, folder in (
        ('x20-accelerated-feedback-windows-20260930', 'x20-feedback-81769-complete-received'),
        ('x20-window-feedback-20260930', 'x20-feedback-82273-complete-received'),
        ('x20-window-difference-20260930', 'x20-window-difference-82396-received'),
        ('x20-latest-window-basis-20261001', 'x20-latest-basis-82441-received'),
    ):
        prefix = 'outputs/hpc/' + run + '/'
        if path.startswith(prefix):
            rel = path[len(prefix):]
            return ROOT / Path(rel).name if rel.startswith('archives/') else ROOT / folder / rel
    return Path(path)


def expected_from_basis(rows, coefficients):
    """80-digit quadratic and surface reductions with actual binary64 coefficients."""
    with localcontext() as ctx:
        ctx.prec = 80
        dec = lambda x: Decimal.from_float(float(x))
        squares = [Decimal(0)] * 3
        flux = [Decimal(0)] * 6
        absolute = [Decimal(0)] * 3
        signed = [Decimal(0)] * 3
        for n, row in enumerate(rows):
            assert row['first_group'] == 32*n and row['group_count'] == 32
            assert row['block'] == (32*n)//128
            cs = list(map(dec, coefficients[row['block']]))
            gram = [[dec(v) for v in r] for r in row['gram']]
            f = [[dec(v) for v in r] for r in row['boundary_spectra']]
            assert len(f) == 8 and all(len(r) == 32 for r in f)
            for endpoint, factor in enumerate((Decimal(0), Decimal(1), Decimal('.5'))):
                v = [Decimal(1)] + [factor*c for c in cs]
                squares[endpoint] += sum(v[i]*gram[i][j]*v[j] for i in range(4) for j in range(4))
                for k in range(32):
                    x = f[0][k] + factor*sum(cs[j]*(f[2*j+2][k]-f[0][k]) for j in range(3))
                    y = f[1][k] + factor*sum(cs[j]*(f[2*j+3][k]-f[1][k]) for j in range(3))
                    flux[2*endpoint] += x
                    flux[2*endpoint+1] += y
                    absolute[endpoint] += abs(y-x)
                    signed[endpoint] += y-x
        return dict(squared_l2=list(map(float, squares)), boundary_flux=list(map(float, flux)),
                    boundary_l1_numerator=list(map(float, absolute)), boundary_signed=list(map(float, signed)))


def main(job, commit):
    receipt = read(ROOT/f'{job}-block-prediction-review.json')
    arc = ROOT/f'{job}-block-prediction-review.tar.gz'
    assert arc.stat().st_size == receipt['size_bytes'] and digest(arc) == receipt['sha256']
    out = ROOT/f'x20-block-prediction-{job}-received'
    out.mkdir(exist_ok=False)
    with tarfile.open(arc) as tar:
        ix = {r['path']: r for r in receipt['files']}
        members = tar.getmembers()
        assert len(ix) == len(members) == 8
        for m in members:
            assert m.isfile() and m.name == Path(m.name).name and m.name in ix
            b = tar.extractfile(m).read()
            assert len(b) == ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest() == ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d, p, s, t = [read(out/(n+'.json')) for n in ('declaration', 'prediction', 'summary', 'scheduler-terminal')]
    assert d['job_id'] == str(job) and d['source_job'] == 82441 and d['git_commit'] == commit
    assert d['shape'] == [9632, 32, 4096]
    assert t['job_id'] == job and t['state'] == 'COMPLETED' and t['summary'] == s
    for token in ('ExitCode=0:0', 'NumCPUs=4', 'QOS=qos_stu_default', 'TimeLimit=01:00:00'):
        assert token in t['scontrol']
    assert not (out/f'tde-x20-bpred-{job}.err').read_bytes()
    for claim in d['code'] + d['source_code'] + d['source_claims']:
        f = local_path(claim['path'])
        assert f.stat().st_size == claim['size_bytes'] and digest(f) == claim['sha256'], claim['path']
    prior = read('handoff/evidence/20261001-x20-latest-basis-82441-review.json')
    candidate_path = Path('handoff/evidence/20261001-x20-82441-bounded-gram-analysis.json')
    candidate = read(candidate_path)
    proof = read('handoff/evidence/20261001-x20-82441-bounded-gram-verification.json')
    basis_path = ROOT/'x20-latest-basis-82441-received/basis.json'
    assert proof['analysis_sha256'] == digest(candidate_path)
    assert proof['basis_sha256'] == candidate['basis_sha256'] == digest(basis_path)
    assert d['fields'] == prior['fields'] and d['unresolved_blocks'] == proof['unresolved_blocks']
    assert d['selected_coefficients'] == [r['selected_coefficients_float'] for r in candidate['blocks']]
    assert d['coefficient_mode'] == 'per_natural_block' and d['full_fraction'] == .9 and d['half_fraction'] == .45
    assert d['maximum_candidates'] == 1 and d['maximum_full_field_reads'] == 3
    rows = p['slabs']
    assert len(rows) == 301 and all(r['group_count'] == 32 for r in rows)
    z = reduce_prediction(rows)
    assert z['checks'] == p['checks'] == s['checks'] and z['passed'] == p['passed'] == s['passed']
    expected = expected_from_basis(read(basis_path)['slabs'], d['selected_coefficients'])
    # Consistency tolerances are separate from (and do not alter) science gates.
    with localcontext() as ctx:
        ctx.prec = 80
        actual = {k: [float(sum(Decimal.from_float(float(r[k][i])) for r in rows))
                      for i in range(len(v))] for k, v in expected.items()}
    np.testing.assert_allclose(actual['squared_l2'], expected['squared_l2'], rtol=3e-10, atol=0)
    scale = max(abs(v) for v in expected['boundary_flux'])
    assert scale > 0
    for key in ('boundary_flux', 'boundary_l1_numerator', 'boundary_signed'):
        np.testing.assert_allclose(np.array(actual[key])/scale, np.array(expected[key])/scale, rtol=0, atol=3e-13)
    np.testing.assert_allclose(actual['squared_l2'][0], prior['gram'][0][0], rtol=3e-12, atol=0)
    if z['checks']['full_field_nonnegative']:
        np.testing.assert_allclose(z['l2_ratios'], p['fixed_scale_l2_ratios'], rtol=3e-12)
        np.testing.assert_allclose(z['linf_ratios'], p['fixed_scale_linf_ratios'], rtol=3e-12)
        for i in range(3):
            for k, v in z['boundary'][i].items():
                np.testing.assert_allclose(v, p['boundary'][i][k], rtol=3e-12, atol=0)
    else:
        assert p['status'] == 'negative_field_rejected' and p['other_gates_evaluated'] is False
        z['negative_slabs'] = [dict(first_group=r['first_group'], minima=r['minima']) for r in rows if min(r['minima']) < 0]
        z['other_gates_evaluated'] = False
    for obj in (d, s):
        assert all(obj[k] == 0 for k in ('new_maps', 'new_feedback_pairs', 'new_material_steps'))
        assert obj['baseline_replaced'] is False and obj['strict_error_bound'] is False
    status = 'prediction_passed_requires_review' if z['passed'] else 'prediction_rejected_requires_review'
    assert s['status'] == read(out/'status.json')['status'] == status and s['candidate_written'] is False
    assert 0 < s['peak_rss_bytes'] < 6*1024**3 and 0 < s['wall_s'] < 3600
    z.update(job_id=job, git_commit=commit, receipt=receipt, independent_complete_field_reduction=True,
             fields=d['fields'], selected_coefficients=d['selected_coefficients'], unresolved_blocks=d['unresolved_blocks'],
             expected_from_stored_basis=expected, measured_slab_totals=actual,
             peak_rss_bytes=s['peak_rss_bytes'], wall_s=s['wall_s'], large_fields_recomputed_on_mac=False,
             new_maps=0, new_feedback_pairs=0, new_material_steps=0, baseline_replaced=False, strict_error_bound=False)
    target = Path(f'handoff/evidence/20261001-x20-block-prediction-{job}-review.json')
    with target.open('x') as f:
        f.write(json.dumps(z, indent=2, allow_nan=False)+'\n')
    print(json.dumps({k: z[k] for k in ('job_id', 'passed', 'checks', 'wall_s', 'peak_rss_bytes')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=int, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    main(args.job, args.commit)
