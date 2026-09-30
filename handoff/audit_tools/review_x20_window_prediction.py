"""Independent complete-slab reduction of 82187 prediction, without field kernels."""
import hashlib,json,math,tarfile
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT,read,digest


def reduce_prediction(rows):
    if not rows:raise ValueError('empty slabs')
    for j,r in enumerate(rows):
        if r['first_group']!=32*j or not 1<=r['group_count']<=32:raise ValueError('coverage')
        for k,n in [('squared_l2',3),('linf',3),('scales',3),('minima',4),('boundary_flux',6),('boundary_l1_numerator',3),('boundary_signed',3)]:
            x=np.array(r[k]);assert x.shape==(n,) and np.isfinite(x).all()
            if k not in ('minima','boundary_signed','boundary_flux'):assert np.all(x>=0)
    if any(min(r['minima'])<0 for r in rows):
        return dict(passed=False,checks=dict(full_field_nonnegative=False))
    with localcontext() as c:
        c.prec=80
        def total(k,i):return float(sum((Decimal.from_float(float(r[k][i])) for r in rows),Decimal(0)))
        sq=[total('squared_l2',i) for i in range(3)]
        peak=[max(r['linf'][i] for r in rows) for i in range(3)]
        scale=[max(r['scales'][i] for r in rows) for i in range(3)]
        assert min(sq)>0 and min(peak)>0 and min(scale)>0
        flux=[total('boundary_flux',i) for i in range(6)];assert min(flux)>0
        boundary=[dict(boundary_l1=total('boundary_l1_numerator',i)/max(flux[2*i:2*i+2]),
            boundary_bolometric=abs(total('boundary_signed',i))/max(flux[2*i:2*i+2]),residual=peak[i]/scale[i]) for i in range(3)]
        l2=[math.sqrt(z/sq[0]) for z in sq];linf=[z/peak[0] for z in peak]
        checks=dict(full_field_nonnegative=True,full_l2_benefit=l2[1]<=.8,full_linf_nonincrease=linf[1]<=1+1e-10,
            half_l2_nonincrease=l2[2]<=1+1e-10,half_linf_nonincrease=linf[2]<=1+1e-10)
        for i,name in [(1,'full'),(2,'half')]:
            checks[name+'_radiation']=boundary[i]['residual']<1e-4
            for k in ('boundary_l1','boundary_bolometric'):checks[name+'_'+k]=boundary[i][k]<1e-3 and boundary[i][k]<=boundary[0][k]*(1+1e-10)
        return dict(squared_l2=sq,linf=peak,scales=scale,boundary=boundary,l2_ratios=l2,linf_ratios=linf,
                    minima=[min(r['minima'][i] for r in rows) for i in range(4)],checks=checks,passed=all(checks.values()))


def local_path(path):
    prefix='outputs/hpc/x20-accelerated-feedback-windows-20260930/'
    if path.startswith(prefix):
        rel=path[len(prefix):]
        return ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/'x20-feedback-81769-complete-received'/rel
    for run,folder in [('x20-matched-chord-proposal-20260930','x20-proposal-82083-received'),('x20-window-basis-20260930','x20-basis-82166-received')]:
        if path.startswith('outputs/hpc/'+run+'/'):return ROOT/folder/Path(path).name
    return Path(path)


def main():
    rec=read(ROOT/'82187-review-20260930.json');arc=ROOT/'82187-review-20260930.tar.gz'
    assert digest(arc)==rec['sha256'] and arc.stat().st_size==rec['size_bytes']
    out=ROOT/'x20-prediction-82187-received';out.mkdir(exist_ok=False)
    with tarfile.open(arc) as tar:
        ix={r['path']:r for r in rec['files']};members=tar.getmembers();assert len(members)==len(ix)==8
        for m in members:
            assert m.isfile() and Path(m.name).name==m.name and m.name in ix
            b=tar.extractfile(m).read();assert len(b)==ix[m.name]['size_bytes'] and hashlib.sha256(b).hexdigest()==ix[m.name]['sha256']
            (out/m.name).write_bytes(b)
    d=read(out/'declaration.json');p=read(out/'prediction.json');s=read(out/'summary.json');t=read(out/'scheduler-terminal.json')
    assert d['job_id']=='82187' and d['source_job']==82166 and d['shape']==[9632,32,4096]
    assert t['job_id']==82187 and t['state']=='COMPLETED' and 'ExitCode=0:0' in t['scontrol'] and t['summary']==s
    assert 'NumCPUs=4' in t['scontrol'] and 'QOS=qos_stu_default' in t['scontrol']
    assert not (out/'tde-x20-wpred-82187.err').read_bytes()
    for c in d['code']+d['source_code']+d['source_claims']:
        f=local_path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],c['path']
    prior=read('handoff/evidence/20260930-x20-82166-review.json');cand=read('handoff/evidence/20260930-x20-window-candidate-result.json');w=read('handoff/evidence/20260930-x20-window-candidate-review.json')
    assert d['fields']==prior['fields'] and d['raw_coefficients']==cand['raw_coefficients']==w['raw_coefficients']
    assert d['selected_coefficients']==cand['selected_coefficients']==w['selected_coefficients']
    assert d['full_fraction']==.9 and d['half_fraction']==.45 and d['maximum_candidates']==1 and d['maximum_full_field_reads']==3
    assert len(p['slabs'])==301 and all(r['group_count']==32 for r in p['slabs'])
    z=reduce_prediction(p['slabs']);assert z['checks']==p['checks']==s['checks'] and z['passed']==p['passed']==s['passed']
    np.testing.assert_allclose(z['l2_ratios'],p['fixed_scale_l2_ratios'],rtol=3e-12)
    np.testing.assert_allclose(z['linf_ratios'],p['fixed_scale_linf_ratios'],rtol=3e-12)
    np.testing.assert_allclose(z['squared_l2'][0],prior['gram'][0][0],rtol=3e-12)
    for i in range(3):
        for k in z['boundary'][i]:np.testing.assert_allclose(z['boundary'][i][k],p['boundary'][i][k],rtol=3e-12)
    for i in range(2):
        np.testing.assert_allclose(z['l2_ratios'][i+1],float(w['endpoints'][i]['l2_ratio']),rtol=3e-10)
        for k in ('boundary_l1','boundary_bolometric'):
            expected=float(w['endpoints'][i][k+'_ratio'])*z['boundary'][0][k]
            assert abs(z['boundary'][i+1][k]-expected)<3e-13
    for x in (d,s):
        assert x['new_maps']==x['new_feedback_pairs']==x['new_material_steps']==0 and not x['baseline_replaced'] and not x['strict_error_bound']
    assert not s['candidate_written'] and s['status']==read(out/'status.json')['status']=='prediction_passed_requires_review'
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    z.update(job_id=82187,receipt=rec,independent_complete_field_reduction=True,fields=d['fields'],raw_coefficients=d['raw_coefficients'],
        selected_coefficients=d['selected_coefficients'],code_claims_verified=len(d['code'])+len(d['source_code']),source_claims_verified=len(d['source_claims']),
        peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],large_fields_recomputed_on_mac=False,
        new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    Path('handoff/evidence/20260930-x20-82187-review.json').write_text(json.dumps(z,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in z.items() if k not in ('receipt','fields')},indent=2))


if __name__=='__main__':main()
