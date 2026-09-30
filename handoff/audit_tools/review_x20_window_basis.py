"""Independent 82166 artifact audit and untruncated Decimal quadratic solve."""
from decimal import Decimal, localcontext
import hashlib,json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_cross_seed_chord import ROOT,digest,read,verify_slabs
from handoff.audit_tools.review_x20_matched_proposal import boundary


def close(a,b):np.testing.assert_allclose(a,b,rtol=3e-11,atol=1e-25)


def minimum(gram):
    """Solve H alpha=-b by 80-digit LDL; no eigenvalue clipping or regularization."""
    g=np.asarray(gram,float);n=g.shape[0]-1
    if g.shape!=(n+1,n+1) or not np.isfinite(g).all() or not np.array_equal(g,g.T) or g[0,0]<=0:
        raise ValueError('invalid symmetric Gram')
    with localcontext() as ctx:
        ctx.prec=80;D=lambda x:Decimal.from_float(float(x));a=D(g[0,0])
        h=[[D(g[i+1,j+1]) for j in range(n)] for i in range(n)]
        b=[D(g[i+1,0]) for i in range(n)]
        l=[[Decimal(i==j) for j in range(n)] for i in range(n)];p=[]
        for i in range(n):
            p.append(h[i][i]-sum(l[i][k]**2*p[k] for k in range(i)))
            if p[i]<=0:raise ValueError('Hessian not positive definite; retain all directions')
            for j in range(i+1,n):
                l[j][i]=(h[j][i]-sum(l[j][k]*l[i][k]*p[k] for k in range(i)))/p[i]
        def solve(v):
            y=[]
            for i in range(n):y.append(v[i]-sum(l[i][k]*y[k] for k in range(i)))
            z=[y[i]/p[i] for i in range(n)];x=[Decimal(0)]*n
            for i in range(n-1,-1,-1):x[i]=z[i]-sum(l[k][i]*x[k] for k in range(i+1,n))
            return x
        alpha=solve([-v for v in b])
        residual=[sum(h[i][j]*alpha[j] for j in range(n))+b[i] for i in range(n)]
        value=a+sum(b[i]*alpha[i] for i in range(n))
        if value<0:raise ValueError('negative Schur complement')
        inv_cols=[solve([Decimal(i==j) for i in range(n)]) for j in range(n)]
        hn=max(sum(map(abs,row)) for row in h)
        invn=max(sum(abs(inv_cols[j][i]) for j in range(n)) for i in range(n))
        weights=[1-sum(alpha)]+alpha
        return dict(alpha=list(map(float,alpha)),alpha_80digit=list(map(str,alpha)),ldl_pivots_80digit=list(map(str,p)),
                    normal_equation_residual_80digit=list(map(str,residual)),hessian_condition_inf_80digit=str(hn*invn),
                    minimum_squared_ratio_80digit=str(value/a),minimum_l2_ratio=float((value/a).sqrt()),
                    all_real_coefficients_excluded_at_0_8=bool(value>Decimal('.64')*a),
                    weight_l1_at_unconstrained_minimum=float(sum(map(abs,weights))),
                    scope='stored Gram affine prediction only; not a true-map or physical-error bound')


def reduce_rows(rows):
    verify_slabs(rows)
    for r in rows:
        g=np.array(r['gram'])
        assert g.shape==(4,4) and np.isfinite(g).all() and np.array_equal(g,g.T)
        assert np.all(np.diag(g)>=0)
        for i in range(4):
            for j in range(4):assert g[i,j]**2<=g[i,i]*g[j,j]*(1+1e-12)+1e-300
        for key,size in (('basis_linf',4),('field_minima',8)):
            x=np.asarray(r[key]);assert x.shape==(size,) and np.isfinite(x).all() and np.all(x>=0)
        f=np.asarray(r['boundary_spectra']);assert f.shape==(8,32) and np.isfinite(f).all() and np.all(f>=0)
    with localcontext() as c:
        c.prec=80
        g=[[float(sum((Decimal.from_float(float(r['gram'][i][j])) for r in rows),Decimal(0))) for j in range(4)] for i in range(4)]
    f=np.concatenate([np.asarray(r['boundary_spectra']) for r in rows],axis=1)
    return g,f


def main():
    receipt=read(ROOT/'82166-review-20260930.json');arc=ROOT/'82166-review-20260930.tar.gz'
    assert arc.stat().st_size==receipt['size_bytes'] and digest(arc)==receipt['sha256']
    out=ROOT/'x20-basis-82166-received';out.mkdir(exist_ok=False)
    with tarfile.open(arc) as tar:
        index={r['path']:r for r in receipt['files']};members=tar.getmembers()
        assert len(index)==len(members)==8
        for m in members:
            assert m.isfile() and m.name==Path(m.name).name and m.name in index
            b=tar.extractfile(m).read();c=index[m.name]
            assert len(b)==c['size_bytes'] and hashlib.sha256(b).hexdigest()==c['sha256']
            (out/m.name).write_bytes(b)
    d=read(out/'declaration.json');s=read(out/'summary.json');p=read(out/'basis.json');t=read(out/'scheduler-terminal.json')
    assert d['job_id']=='82166' and d['source_jobs']==[81769,82039,82083] and d['shape']==[9632,32,4096]
    assert d['git_commit']=='6052db124ae271f44cec75fb2a7488f347344b14'
    assert d['field_order']==['A16','T_A16','H16','T_H16','A8','T_A8','H8','T_H8']
    assert d['basis_order']==['r_A16','r_H16-r_A16','r_A8-r_A16','r_H8-r_A16']
    assert t['job_id']==82166 and t['state']=='COMPLETED' and 'ExitCode=0:0' in t['scontrol'] and t['summary']==s
    assert 'NumCPUs=4' in t['scontrol'] and 'QOS=qos_stu_default' in t['scontrol'] and 'TimeLimit=01:00:00' in t['scontrol']
    assert not (out/'tde-x20-basis-82166.err').read_bytes()
    prefix='outputs/hpc/x20-accelerated-feedback-windows-20260930/'
    for c in d['code']+d['small_claims']:
        path=c['path']
        if path.startswith(prefix):
            rel=path[len(prefix):]
            f=ROOT/Path(rel).name if rel.startswith('archives/') else ROOT/'x20-feedback-81769-complete-received'/rel
        elif path.startswith('outputs/hpc/x20-matched-chord-proposal-20260930/'):f=ROOT/'x20-proposal-82083-received'/Path(path).name
        else:f=Path(path)
        assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256'],path
    source=ROOT/'x20-feedback-81769-complete-received';fields=[]
    for name,n in [('accelerated',16),('historical',16),('accelerated',8),('historical',8)]:
        m=read(source/name/f'endpoints-map{n:02d}/manifest.json');row=m['history_rows'][-1]
        assert row['iteration']==n
        assert row['input_sha256']==m['endpoints']['final']['sha256']
        assert row['output_sha256']==m['endpoints']['mapped_final']['sha256']
        fields.extend(m['endpoints'][e] for e in ('final','mapped_final'))
    assert fields==d['fields'] and all(c['size_bytes']==10099884032 for c in fields)
    prev=read('handoff/evidence/20260930-x20-82083-review.json')
    assert fields[:4]==prev['fields'] and p['all_eight_sha256_verified'] is True
    g,f=reduce_rows(p['slabs']);close(g,p['gram']);close(g,s['gram'])
    close(np.array(g)[:2,:2],np.array(prev['gram'])[:2,:2])
    close(f[:4],read(ROOT/'x20-proposal-82083-received/prediction.json')['surface_spectra'])
    peaks=[max(r['basis_linf'][i] for r in p['slabs']) for i in range(4)]
    minima=[min(r['field_minima'][i] for r in p['slabs']) for i in range(8)]
    close(peaks,p['basis_linf']);close(minima,p['field_minima'])
    assert f.shape==(8,9632) and s['slabs']==301
    for z in (s,d):
        assert z['new_maps']==z['new_feedback_pairs']==z['new_material_steps']==0
        assert z['baseline_replaced'] is False and z['strict_error_bound'] is False
    assert d['maximum_field_scans']==1 and d['longdouble_mantissa_bits']>=52
    assert p['candidate_written'] is False and s['candidate_written'] is False
    assert s['status']==read(out/'status.json')['status']=='basis_complete_requires_review'
    assert 0<s['peak_rss_bytes']<6*1024**3 and 0<s['wall_s']<3600
    result=dict(job_id=82166,receipt=receipt,independent_audit=True,code_claims_verified=len(d['code']),source_claims_verified=len(d['small_claims']),
                fields=fields,gram=g,minimum=minimum(g),basis_linf=peaks,field_minima=minima,
                boundary_metrics=[boundary(f[i],f[i+1]) for i in range(0,8,2)],slabs=301,blocks=76,groups=9632,
                peak_rss_bytes=s['peak_rss_bytes'],wall_s=s['wall_s'],large_fields_recomputed_on_mac=False,
                new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False)
    Path('handoff/evidence/20260930-x20-82166-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result['minimum'],indent=2))


if __name__=='__main__':main()
