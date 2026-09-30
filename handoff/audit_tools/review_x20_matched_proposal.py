"""Independent small-artifact audit of 82083; no production reduction reused."""
from decimal import Decimal,localcontext
import hashlib,json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_cross_seed_chord import digest,read,ROOT


def close(x,y):np.testing.assert_allclose(x,y,rtol=3e-11,atol=1e-25)


def quadratic_minimum(g):
    with localcontext() as c:
        c.prec=70
        a,b,h=[Decimal.from_float(float(v)) for v in (g[0][0],g[0][1],g[1][1])]
        if a<=0 or h<=0:raise ValueError('nonpositive quadratic scale')
        f=a-b*b/h
        if f<0:raise ValueError('non-PSD objective')
        return dict(unconstrained_alpha=float(-b/h),unconstrained_minimum_l2_ratio=float((f/a).sqrt()),
                    all_real_alpha_cannot_reach_0_8=bool(f>Decimal('.64')*a),scope='affine prediction on this chord only')


def boundary(x,y):
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(x<0) or np.any(y<0):raise ValueError('invalid surface spectrum')
    den=max(math.fsum(x),math.fsum(y))
    if den<=0:raise ValueError('zero flux normalization')
    return dict(boundary_l1=math.fsum(abs(y-x))/den,boundary_bolometric=abs(math.fsum(y-x))/den)


def main():
    receipt=read(ROOT/'82083-review-20260930.json');tarpath=ROOT/'82083-review-20260930.tar.gz';out=ROOT/'x20-proposal-82083-received'
    assert tarpath.stat().st_size==receipt['size_bytes'] and digest(tarpath)==receipt['sha256'];out.mkdir(exist_ok=False)
    with tarfile.open(tarpath) as tar:
        index={r['path']:r for r in receipt['files']};members=tar.getmembers();assert len(members)==len(index)==8
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in index
            b=tar.extractfile(m).read();c=index[m.name]
            assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256'];(out/m.name).write_bytes(b)
    d=read(out/'declaration.json');p=read(out/'prediction.json');s=read(out/'summary.json');t=read(out/'scheduler-terminal.json')
    assert d['job_id']=='82083' and d['source_job']==s['source_job']==82039 and d['source_maps_job']==81769
    assert t['job_id']==82083 and t['state']=='COMPLETED' and 'ExitCode=0:0' in t['scontrol'] and t['summary']==s
    assert 'NumCPUs=4' in t['scontrol'] and 'QOS=qos_stu_default' in t['scontrol']
    assert d['git_commit']=='86dddc09818af69d370cc6aa712586e6e70b054a'
    assert not (out/'tde-x20-proposal-82083.err').read_bytes()
    prior=read(ROOT/'x20-chord-82039-received/declaration.json');assert d['fields']==prior['fields']['16']
    prefix='outputs/hpc/x20-accelerated-feedback-windows-20260930/'
    seen=0
    for c in d['code']+d['claims']:
        path=c['path']
        if path.endswith('.dat'):assert c in d['fields'];seen+=1;continue
        if path.startswith(prefix):
            rel=path[len(prefix):];f=ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/'x20-feedback-81769-complete-received'/rel
        elif path.startswith('outputs/hpc/x20-cross-seed-chord-20260930/') or 'x20-cross-seed-chord-watch-82039/' in path:f=ROOT/'x20-chord-82039-received'/Path(path).name
        else:f=Path(path)
        assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],path
    assert seen==4
    assert d['maximum_field_scans']==2 and d['maximum_candidates']==1 and d['alpha_bounds']==[-8.,8.] and d['step_safety']==.9 and d['coefficient_l1_cap']==17
    for x in (d,s):assert x['new_material_steps']==0 and x['baseline_replaced'] is False and x['strict_error_bound'] is False
    assert d['maximum_new_maps']==d['maximum_feedback_pairs']==s['new_maps']==s['new_feedback_pairs']==0
    rows=p['slabs'];pred=p['prediction_slabs'];assert len(rows)==len(pred)==301
    for j,(x,y) in enumerate(zip(rows,pred)):
        assert x['first_group']==y['first_group']==32*j and x['group_count']==y['group_count']==32
        a=np.asarray(x['gram']);assert a.shape==(4,4) and np.isfinite(a).all() and np.array_equal(a,a.T)
        assert -8<=x['alpha_interval'][0]<=0<=x['alpha_interval'][1]<=8
        assert y['minimum_candidate']>=0 and y['minimum_prediction']>=0
        assert np.isfinite(y['squared_l2']).all() and min(y['squared_l2'])>=0 and np.isfinite(y['linf']).all()
    with localcontext() as ctx:
        ctx.prec=70
        g=np.array([[float(sum((Decimal.from_float(float(r['gram'][i][j])) for r in rows),Decimal(0))) for j in range(4)] for i in range(4)])
    close(g,p['gram']);close(g[3],g[1]+g[2]);close(g[:,3],g[:,1]+g[:,2])
    q=quadratic_minimum(g);lo=max(r['alpha_interval'][0] for r in rows);hi=min(r['alpha_interval'][1] for r in rows)
    resolved=g[1,1]>1e-12*g[0,0];opt=q['unconstrained_alpha'];bounded=min(hi,max(lo,opt));alpha=.9*bounded if resolved else 0.
    choice=p['choice'];close(alpha,choice['alpha']);close([lo,hi],choice['alpha_interval']);close(opt,choice['unconstrained_alpha'])
    assert choice['direction_resolved']==resolved and not choice['strict_error_bound']
    close(choice['coefficient_l1'],abs(1-alpha)+abs(alpha));close(choice['difference_gain_l2'],math.sqrt(g[3,3]/g[2,2]));close(choice['difference_projection'],g[2,3]/g[2,2])
    sums=[math.fsum(r['squared_l2'][i] for r in pred) for i in range(3)];peaks=[max(r['linf'][i] for r in pred) for i in range(2)]
    close(sums[0],g[0,0]);quadratic=g[0,0]+2*alpha*g[0,1]+alpha*alpha*g[1,1];close(sums[1],quadratic)
    l2=math.sqrt(sums[1]/sums[0]);linf=peaks[1]/peaks[0];close(l2,p['l2_ratio']);close(linf,p['linf_ratio']);close(math.sqrt(sums[2]/g[3,3]),p['difference_nonparallel_fraction'])
    f=np.asarray(p['surface_spectra']);assert f.shape==(4,9632) and np.isfinite(f).all() and np.all(f>=0)
    base=boundary(*f[:2]);test=boundary(f[0]+alpha*(f[2]-f[0]),f[1]+alpha*(f[3]-f[1]))
    for k in base:close(base[k],p['original_boundary'][k]);close(test[k],p['predicted_boundary'][k])
    checks=dict(resolved_nonzero_direction=bool(resolved and alpha!=0),coefficient_l1_bounded=bool(abs(1-alpha)+abs(alpha)<=17),l2_benefit=l2<=.8,linf_nonincrease=peaks[1]<=peaks[0]*(1+1e-10))
    for k in base:checks[k]=test[k]<1e-3 and test[k]<=base[k]*(1+1e-10)
    assert checks==p['checks']==s['checks'] and all(checks.values())==p['feasible']==s['feasible']
    assert not p['candidate_written'] and not s['candidate_written'] and p['true_map_required']
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600 and s['status']==read(out/'status.json')['status']=='prediction_complete_requires_review'
    result=dict(job_id=82083,receipt=receipt,independent_reduction=True,large_fields_recomputed_on_mac=False,code_claims_verified=len(d['code']),source_claims_verified=len(d['claims']),fields=d['fields'],gram=g.tolist(),alpha=alpha,interval=[lo,hi],line_minimum=q,l2_ratio=l2,linf_ratio=linf,original_boundary=base,predicted_boundary=test,checks=checks,feasible=all(checks.values()),peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],new_maps=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    Path('handoff/evidence/20260930-x20-82083-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
