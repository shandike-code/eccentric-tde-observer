"""Independent active-set QP and full small-artifact reductions for job78031."""
import itertools,json,math,tarfile
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_step21_control_windows import receive,read,digest,verified_inventory


def independent_qp(g,b,cuts):
    g=np.array(g);b=np.array(b);scale=np.max(abs(g));g/=scale;b/=scale
    A=np.array([[1,0],[0,1],[-1,-1]]+[c['row'] for c in cuts],float)
    h=np.array([0,0,-1]+[c['lower'] for c in cuts],float);candidates=[]
    def add(x):
        if np.isfinite(x).all() and np.all(A@x>=h-1e-11):candidates.append(x)
    add(np.linalg.solve(g,-b))
    # 独立KKT活跃集枚举，不调用生产代码的多边形裁切与逐边求解。
    for i in range(len(A)):
        K=np.block([[g,-A[i,:,None]],[A[i,None,:],np.zeros((1,1))]])
        if abs(np.linalg.det(K))>1e-14:add(np.linalg.solve(K,np.r_[-b,h[i]])[:2])
    for i,j in itertools.combinations(range(len(A)),2):
        mat=A[[i,j]]
        if abs(np.linalg.det(mat))>1e-14:add(np.linalg.solve(mat,h[[i,j]]))
    assert candidates
    return min(candidates,key=lambda x:x@g@x+2*b@x)


def main():
    root=Path('outputs/review-20260925');out=root/'joint-taper-plane-78031-received';receipt=root/'complete-1790448078036541242-receipt.json'
    manifest=receive(root/'complete-1790448078036541242.tar.gz',receipt,out)
    d=read(out/'declaration.json');p=read(out/'prediction.json');g=read(out/'gram.json');state=read(out/'status.json')
    term=read(Path('handoff/evidence/20260927-joint-taper-plane-78031-terminal.json'))
    assert term['job_id']==78031 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
    assert state['status']=='complete_requires_review' and d['accepted_outer_steps']==state['accepted_outer_steps']==20 and state['new_material_steps']==0
    assert d['maximum_maps']==d['maximum_feedback_pairs']==d['maximum_candidate_writes']==0 and d['maximum_passes']==6
    assert d['controls']=={'maximum_passes':6,'maximum_cuts':4096,'retreat':.99,'minimum_l2_gain':.2,'linf_roundoff':1e-10}
    assert p['passes']==1+len(p['rounds'])<=6 and not any(p[k] for k in ['full_constrained_optimum_proven','actual_map_performed','candidate_written','accepted_material_step'])
    for c in d['code']:
        f=Path(c['path']);assert f.stat().st_size==c['size_bytes'] and digest(f)==c['sha256']
    for folder,ev in [('joint-block-global-77843-received','20260926-joint-global-review'),('tapered-joint-77927-received','20260926-tapered-joint-review'),('taper-commutator-77954-received','20260927-taper-commutator-review')]:
        prior=root/folder;a=read(Path('handoff/evidence')/(ev+'.json'));archive=root/Path(a['archive']['path']).name
        assert digest(archive)==a['archive']['sha256']
        with tarfile.open(archive) as t:assert json.load(t.extractfile('ARCHIVE_MANIFEST.json'))==read(prior/'ARCHIVE_MANIFEST.json')
        verified_inventory(prior)
    prior=read(root/'taper-commutator-77954-received/declaration.json');assert d['paths']==prior['paths']
    assert d['source_row']==read(root/'joint-block-global-77843-received/declaration.json')['source_row']
    slabs=g['slabs'];assert [(r['start'],r['stop']) for r in slabs]==[(i,i+32) for i in range(0,9632,32)]
    G=np.array([[math.fsum(r['gram'][i][j] for r in slabs) for j in range(2)] for i in range(2)]);b=np.array([math.fsum(r['rhs'][i] for r in slabs) for i in range(2)]);S0=math.fsum(r['s0'] for r in slabs);M=max(r['maximum'] for r in slabs)
    assert np.isfinite([*G.ravel(),*b,S0,M]).all() and np.linalg.eigvalsh(G)[0]>1e-12*np.linalg.eigvalsh(G)[-1]
    np.testing.assert_allclose(G,g['gram'],rtol=1e-14);np.testing.assert_allclose(b,g['rhs'],rtol=1e-14);assert S0==g['s0'] and M==g['maximum']
    np.testing.assert_allclose(S0,a['domains']['all']['squared_l2'][0],rtol=1e-14);assert M==a['domains']['all']['linf'][0]
    f=np.array(g['fluxes']);assert f.shape==(6,9632) and np.isfinite(f).all()
    cuts=[];keys=set();rounds=[]
    for item in p['rounds']:
        sol=item['solution'];r=item['result'];uv=np.array(r['uv']);raw=independent_qp(G,b,cuts)
        np.testing.assert_allclose(raw,sol['raw_uv'],rtol=1e-9,atol=1e-11);np.testing.assert_allclose(uv,.99*raw,rtol=1e-9,atol=1e-11)
        assert sol['retreat']==.99 and sol['resolved'] and sol['uv']==r['uv'];assert np.all(uv>=0) and uv.sum()<=1
        w=np.r_[1-uv.sum(),uv];np.testing.assert_array_equal(w,r['weights'])
        rows=r['slabs'];assert [(s['start'],s['stop']) for s in rows]==[(i,i+32) for i in range(0,9632,32)]
        assert all(np.isfinite(list(s.values())).all() and min(s[k] for k in ('squared_l2','maximum','minimum_input','minimum_output','field_scale','affine_roundoff'))>=0 for s in rows)
        ss=math.fsum(s['squared_l2'] for s in rows);mx=max(s['maximum'] for s in rows);scale=max(s['field_scale'] for s in rows)
        l2=math.sqrt(ss/S0);quad=math.sqrt((S0+2*b@uv+uv@G@uv)/S0);linf=mx/M
        np.testing.assert_allclose([l2,quad,linf],[r['l2_ratio'],r['quadratic_l2_ratio'],r['linf_ratio']],rtol=1e-12)
        checks=dict(nonzero=bool(np.any(uv)),convex=True,full_l2_cost=l2<=.8,quadratic_l2_cost=quad<=.8,linf_nonincrease=linf<=1.0000000001,strict_radiation=scale>0 and mx/scale<1e-4,affine_roundoff=max(s['affine_roundoff'] for s in rows)/M<1e-7)
        for label,t in [('full',1.),('half',.5)]:
            ww=np.r_[1-t*uv.sum(),t*uv];fi=ww@f[::2];fo=ww@f[1::2]
            bi,bo=math.fsum(fi),math.fsum(fo);vals=dict(boundary_l1=math.fsum(abs(x) for x in fo-fi)/max(math.fsum(abs(x) for x in fi),math.fsum(abs(x) for x in fo)),boundary_bolometric=abs(bo-bi)/max(abs(bi),abs(bo)))
            for k,value in vals.items():
                np.testing.assert_allclose(value,r['boundary'][label][k],rtol=1e-8,atol=1e-15)
                checks[label+'_'+k]=value<1e-3 and value<=d['source_row'][k]*1.0000000001
        assert checks==r['checks']
        for c in r['cuts']:
            ix=c['index'];assert len(ix)==3 and all(type(i) is int for i in ix) and all(0<=i<n for i,n in zip(ix,(9632,32,4096)))
            rr,d1,d2=map(float.fromhex,c['values_hex']);m=float.fromhex(c['maximum_hex']);sign=c['sign']
            assert sign in (-1,1) and m==M and abs(rr)<=M
            np.testing.assert_allclose(c['row'],[-sign*d1/M,-sign*d2/M],rtol=1e-14);np.testing.assert_allclose(c['lower'],sign*rr/M-1,rtol=1e-14,atol=1e-15)
            assert sign*(rr+uv@[d1,d2])>M*(1-1e-7)
            key=(tuple(ix),sign)
            if key not in keys:keys.add(key);cuts.append(c)
        rounds.append(dict(uv=r['uv'],l2_ratio=l2,linf_ratio=linf,checks=checks,new_witnesses=len(r['cuts'])))
    assert cuts==p['cuts'] and len(cuts)<=4096 and p['eligible_for_independent_review']==all(rounds[-1]['checks'].values())==True
    assert p['reason']=='all_registered_predictive_gates_passed' and p['peak_rss_bytes']<6*1024**3
    result=dict(archive=read(receipt),accepted_outer_steps=20,new_material_steps=0,verified_files=len(manifest['files']),verified_code_claims=len(d['code']),passes=p['passes'],cuts=len(cuts),rounds=rounds,selected_uv=rounds[-1]['uv'],eligible_for_independent_review=True,peak_rss_bytes=p['peak_rss_bytes'],independent_active_set_and_scalar_reduction=True,raw_fields_recomputed_on_mac=False,operator_recomputed_on_mac=False)
    target=Path('handoff/evidence/20260927-joint-taper-plane-review');target.with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(9,3.5),layout='constrained')
    for axis,key,limit in [(ax[0],'l2_ratio',.8),(ax[1],'linf_ratio',1.)]:
        axis.plot(range(1,len(rounds)+1),[r[key] for r in rounds],'o-');axis.axhline(limit,c='red',ls='--');axis.set(xlabel='Full-field candidate check',ylabel=key,title='Predicted mixtures, not new maps')
    fig.savefig(target.with_suffix('.png'),dpi=150);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
