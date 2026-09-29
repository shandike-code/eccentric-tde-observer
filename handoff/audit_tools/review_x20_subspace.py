"""Independent reduction of 80862 and a convex lower bound on its fixed subspace."""
import itertools,json,math
from pathlib import Path
import numpy as np
from decimal import Decimal,localcontext
from handoff.audit_tools.review_x20_operator import old,cw,read,arrays,slab_coverage,gram_roundoff_check
from handoff.audit_tools.review_x20_histories import source_archive
ROOT=Path('outputs/review-20260925')
BASE='complete-1790669151709949231'
OUT=ROOT/'x20-subspace-80862-received'


def active_face_certificate(gram,flux):
    """Independent 70-digit KKT solve on the observed active L1 facet.

    The facet c0+c2>=-8 is valid for the entire weight-cap polytope.
    A nonpositive equality-form multiplier certifies the facet optimum.
    """
    with localcontext() as ctx:
        ctx.prec=70;g=[[Decimal.from_float(float(v)) for v in row] for row in gram]
        f=[Decimal.from_float(float(v)) for v in flux];zero=Decimal(0);one=Decimal(1)
        scale=max(map(abs,f));f=[v/scale for v in f]
        a=[[g[i+1][j+1]/g[0][0] for j in range(3)] for i in range(3)]
        b=[g[0][i+1]/g[0][0] for i in range(3)];h=[one,zero,one]
        matrix=[a[i]+[f[i+1],h[i],-b[i]] for i in range(3)]
        matrix += [f[1:]+[zero,zero,-f[0]],h+[zero,zero,Decimal(-8)]]
        for k in range(5):
            pivot=max(range(k,5),key=lambda i:abs(matrix[i][k]));matrix[k],matrix[pivot]=matrix[pivot],matrix[k]
            z=matrix[k][k];assert z!=0;matrix[k]=[v/z for v in matrix[k]]
            for i in range(5):
                if i!=k:
                    z=matrix[i][k];matrix[i]=[u-z*v for u,v in zip(matrix[i],matrix[k])]
        solution=[r[-1] for r in matrix];c=solution[:3];weights=[c[0],one-sum(c),c[1],c[2]]
        assert weights[0]<0<weights[1] and weights[2]>0>weights[3] and solution[4]<0
        assert abs(sum(map(abs,weights))-17)<Decimal('1e-50')
        def norm(t):
            u=[one]+[t*v for v in c]
            return (sum(u[i]*g[i][j]*u[j] for i in range(4) for j in range(4))/g[0][0]).sqrt()
        return dict(coefficients=list(map(float,c)),weights=list(map(float,weights)),l2_ratio=float(norm(one)),
            safety_09_l2_prediction=float(norm(Decimal('0.9'))),cap_facet_multiplier=float(solution[4]),
            decimal_precision=70,active_facet='c0+c2=-8',all_boundary_spectrum_and_positivity_checks_pending=True)


def quadratic_bound(g,cap=17.):
    """Minimize over the affine-weight L1 polytope; certify with a support plane.

    This relaxes positivity and every boundary constraint, so is only an
    optimistic lower bound for the stored Gram, not a physical error bound.
    """
    g=np.asarray(g,float);gram_roundoff_check(g)
    if cap<1 or not g[0,0]>0:raise ValueError('invalid coefficient cap or defect')
    g=g/g[0,0];a=g[1:,1:];b=g[0,1:]
    if np.linalg.eigvalsh(a).min()<=0:raise ValueError('strictly resolved Gram required')
    # sum(w)=1, ||w||1<=R的顶点为(R+1)/2 e_i -(R-1)/2 e_j。
    vertices=[]
    for i,j in itertools.permutations(range(4),2):
        w=np.zeros(4);w[i]=(cap+1)/2;w[j]=-(cap-1)/2
        vertices.append(w[[0,2,3]])
    vertices=np.asarray(vertices);best=None
    # Caratheodory: 三维凸包中每点至多由四个顶点表示；枚举所有小单纯形。
    for n in range(1,5):
        for ids in itertools.combinations(range(len(vertices)),n):
            v=vertices[list(ids)];c=v[0].copy()
            if n>1:
                t=(v[1:]-c).T
                if np.linalg.matrix_rank(t)<n-1:continue
                try:u=np.linalg.solve(t.T@a@t,-t.T@(a@c+b))
                except np.linalg.LinAlgError:continue
                bary=np.r_[1-math.fsum(u),u]
                if np.any(bary<0):continue
                c=c+t@u
            w=np.r_[c[0],1-math.fsum(c),c[1:]]
            if np.sum(abs(w))>cap*(1+1e-13):continue
            value=float(1+2*b@c+c@a@c)
            if best is None or value<best[0]:best=(value,c)
    upper,c=best;gradient=2*(a@c+b)
    # 凸二次型高于任一点的切平面；线性函数在完整多面体顶点取最小。
    lower=upper+min(float(gradient@(v-c)) for v in vertices)
    scale=1+2*np.abs(b)@np.abs(c)+np.abs(c)@np.abs(a)@np.abs(c)
    margin=4096*np.finfo(float).eps*float(scale+max(np.abs(gradient)@np.abs(v-c) for v in vertices))
    return dict(coefficients=c.tolist(),weights=[float(c[0]),1-math.fsum(c),float(c[1]),float(c[2])],
        squared_upper=upper,squared_support_lower=lower,roundoff_allowance=margin,
        l2_upper=math.sqrt(upper),l2_conservative_lower=math.sqrt(max(0,lower-margin)),
        coefficient_l1_cap=cap,relaxed_positivity_and_boundary=True,strict_physical_error_bound=False)


def reduce_prediction(p):
    rows=p['system_slabs'];slab_coverage(rows)
    for r in rows:gram_roundoff_check(r['gram'])
    g=np.array([[math.fsum(r['gram'][i][j] for r in rows) for j in range(4)] for i in range(4)])
    f=np.array([math.fsum(r['signed_boundary'][i] for r in rows) for i in range(4)])
    np.testing.assert_allclose(g,p['gram'],rtol=1e-12,atol=0)
    np.testing.assert_allclose(f,p['boundary_coefficients'],rtol=1e-12,atol=0)
    eigen=np.linalg.eigvalsh(g[1:,1:]);np.testing.assert_allclose(eigen,p['solve']['eigenvalues'],rtol=1e-7,atol=0)
    assert np.all(eigen>1e-12*eigen[-1]) and p['solve']['retained_rank']==3
    # 独立用归一化KKT增广系统，不复用运行时的特征白化求解函数。
    a=g[1:,1:]/g[0,0];b=g[0,1:]/g[0,0];f=f/max(abs(f))
    kkt=np.zeros((4,4));kkt[:3,:3]=a;kkt[:3,3]=kkt[3,:3]=f[1:]
    solution=np.linalg.solve(kkt,np.r_[-b,-f[0]]);c=solution[:3]
    np.testing.assert_allclose(c,p['solve']['raw_coefficients'],rtol=2e-8,atol=0)
    assert abs(f[0]+f[1:]@c)<1e-12*(1+np.linalg.norm(c))
    limits=p['positivity_slabs'];slab_coverage(limits)
    assert all(r['upper']==1 and r['negative_candidate']==r['negative_prediction']==0 for r in limits)
    assert p['bounds']['positivity_upper']==1
    # 此例每个非锚点权重的符号在beta>0保持，锚点权重始终正，L1界可解析求得。
    c=np.array(p['solve']['raw_coefficients']);slope=math.fsum(abs(c))-math.fsum(c)
    assert slope>16 and math.fsum(c)<0
    upper=16/slope;beta=.9*upper;selected=beta*c
    np.testing.assert_allclose([upper,beta],[p['bounds']['bounded_upper'],p['bounds']['selected_fraction']],rtol=1e-12)
    np.testing.assert_allclose(selected,p['selected_coefficients'],rtol=1e-12,atol=0)
    w=np.r_[selected[0],1-math.fsum(selected),selected[1:]]
    np.testing.assert_allclose(w,p['weights'],rtol=1e-12,atol=0)
    assert math.isclose(math.fsum(abs(w)),p['bounds']['coefficient_l1'],rel_tol=1e-12) and math.fsum(abs(w))<=17
    measured=p['prediction'];rows=measured['slabs'];slab_coverage(rows)
    for r in rows:
        for k in ('squared_l2','linf','scales','minima','boundary_flux','boundary_l1_numerator'):
            assert np.isfinite(r[k]).all() and np.all(np.asarray(r[k])>=0)
        assert np.isfinite(r['boundary_signed']).all()
    ss=np.array([math.fsum(r['squared_l2'][i] for r in rows) for i in range(3)])
    peaks=np.max([r['linf'] for r in rows],axis=0)
    for i,t in enumerate((0,1,.5)):
        u=np.r_[1,t*selected];expected=float(u@g@u)
        np.testing.assert_allclose(ss[i],expected,rtol=2e-9,atol=0)
    ratios=np.sqrt(ss/ss[0]);linf=peaks/peaks[0]
    np.testing.assert_allclose(ratios,measured['fixed_scale_l2_ratios'],rtol=1e-12,atol=0)
    np.testing.assert_allclose(linf,measured['fixed_scale_linf_ratios'],rtol=1e-12,atol=0)
    flux=[math.fsum(r['boundary_flux'][i] for r in rows) for i in range(6)];boundary=[]
    for i in range(3):
        den=max(flux[2*i:2*i+2]);assert den>0
        boundary.append(dict(boundary_l1=math.fsum(r['boundary_l1_numerator'][i] for r in rows)/den,
            boundary_bolometric=abs(math.fsum(r['boundary_signed'][i] for r in rows))/den,
            residual=peaks[i]/max(r['scales'][i] for r in rows)))
    old.same_record(boundary,measured['boundary'])
    gates=dict(full_l2_benefit=bool(ratios[1]<=.8),full_linf_nonincrease=bool(linf[1]<=1.0000000001),
        half_l2_nonincrease=bool(ratios[2]<=1.0000000001),half_linf_nonincrease=bool(linf[2]<=1.0000000001))
    for i,name in ((1,'full'),(2,'half')):
        gates[name+'_radiation']=bool(boundary[i]['residual']<1e-4)
        for k in ('boundary_l1','boundary_bolometric'):gates[name+'_'+k]=bool(boundary[i][k]<1e-3 and boundary[i][k]<=boundary[0][k]*1.0000000001)
    assert gates==measured['checks'] and not measured['passed'] and not p['all_predicted_checks_passed'] and not p['candidate_written']
    assert [k for k,v in gates.items() if not v]==['full_l2_benefit']
    raw=np.r_[1,c]
    return dict(gram=g.tolist(),gram_condition=float(eigen[-1]/eigen[0]),selected_coefficients=selected.tolist(),weights=w.tolist(),
        raw_l2_prediction=math.sqrt(float(raw@g@raw)/g[0,0]),raw_weight_l1=math.fsum(abs(np.r_[c[0],1-math.fsum(c),c[1:]])),
        bounds=p['bounds'],l2_ratios=ratios.tolist(),linf_ratios=linf.tolist(),boundary=boundary,checks=gates,
        coefficient_cap_relaxation=quadratic_bound(g),joint_cap_boundary_certificate=active_face_certificate(g,p['boundary_coefficients']))


def main():
    inventory=cw.receive(ROOT/(BASE+'.tar.gz'),ROOT/(BASE+'-receipt.json'),OUT)
    assert inventory==read(ROOT/(BASE+'.json')) and len(inventory['files'])==8
    d=read(OUT/'declaration.json');pre=read(OUT/'source-preflight/declaration.json');s=read(OUT/'summary.json')
    terminal=read(Path('handoff/evidence/20260929-x20-subspace-80862-terminal.json'))
    assert terminal['job_id']==80862 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='80862'
    assert d['maximum_maps']==2 and d['maximum_feedback_pairs']==0 and d['maximum_field_scans']==5 and d['maximum_proposals']==1
    assert d['coefficient_l1_cap']==17 and d['rcond']==1e-12 and d['source_jobs']==[80554,80826,80823]
    assert d['fixed_material_x20'] and d['historical_failures_retained'] and not any(d[k] for k in ('baseline_replaced','automatic_promotion','strict_error_bound'))
    assert s['status']==read(OUT/'status.json')['status']=='prediction_rejected'
    assert s['new_maps']==s['new_feedback_pairs']==s['new_material_steps']==0 and s['accepted_outer_steps']==20
    assert not any(s[k] for k in ('baseline_replaced','strict_error_bound','validated','all_predicted_checks_passed'))
    assert s['parent_peak_rss_bytes']<6*1024**3
    for c in d['code']+pre['code']:old.verify_claim(c,Path(c['path']))
    source=ROOT/'x20-history-80554-received';source_archive(source,'20260929-x20-history-review.json',ROOT)
    basis=[]
    for child,n in [('late',16),('historical',24)]:
        m=read(source/child/f'endpoints-map{n:02d}/manifest.json');st=read(source/child/'state.json')
        assert m['history_rows']==st['history'][-2:]
        z=[m['endpoints'][k] for k in ('previous','final','mapped_final')]
        assert [r['sha256'] for r in z]==[st['history'][-2]['input_sha256'],st['history'][-1]['input_sha256'],st['history'][-1]['output_sha256']]
        basis+=z
    assert d['basis']==basis and pre['field_pairs']==[basis[i] for i in (1,2,4,5)]
    assert d['source_row']==pre['source_rows'][0]==read(source/'late/state.json')['history'][-1]
    for c in d['cases']['control'].values():old.verify_claim(c,OUT/'source-preflight/inputs'/Path(c['path']).name)
    assert read(OUT/'source-preflight/inputs/config.json')==read(source/'late/config.json')
    trial=OUT/'source-preflight/inputs/trial_material.npz';assert old.digest(trial)==old.digest(source/'late/trial_material.npz')==old.digest(source/'historical/trial_material.npz')
    t=arrays(trial);assert int(t['phase_index'])==1367 and float(t['step_duration_s'])==889.419892762322
    claim_index={c['path']:c for c in d['claims']}
    for mode,job,run in [('scan',80826,'x20-history-scan-v2-20260929'),('midpoint',80823,'x20-history-midpoint-20260929')]:
        folder=ROOT/f'x20-{mode}-{job}-received';ap=f'20260929-x20-{mode}-review.json'
        source_archive(folder,ap,ROOT)
        for name in ('declaration.json','summary.json','prediction.json' if mode=='scan' else 'validation.json'):
            old.verify_claim(claim_index['outputs/hpc/'+run+'/'+name],folder/name)
        for name in (ap,f'20260929-x20-{mode}-{job}-terminal.json'):
            old.verify_claim(claim_index['handoff/evidence/'+name],Path('handoff/evidence')/name)
    result=reduce_prediction(read(OUT/'prediction.json'))
    result.update(job_id=80862,archive=read(ROOT/(BASE+'-receipt.json')),verified_files=8,verified_code_claims=len(d['code']),
        accepted_outer_steps=20,new_material_steps=0,new_maps=0,new_feedback_pairs=0,baseline_replaced=False,
        independent_small_statistic_reduction=True,large_fields_recomputed_on_mac=False,strict_error_bound=False,
        parent_peak_rss_bytes=s['parent_peak_rss_bytes'],wall_s=s['wall_s'])
    target=Path('handoff/evidence/20260929-x20-subspace-review.json');target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
    ax.bar(['Submitted full','Submitted half','Joint cap/equality\nwith 10% safety'],[result['l2_ratios'][1],result['l2_ratios'][2],result['joint_cap_boundary_certificate']['safety_09_l2_prediction']])
    ax.axhline(.8,color='r',ls='--',label='Required <= 0.8');ax.set(ylabel='Predicted L2 defect / original late',ylim=(0,1.08));ax.legend()
    fig.savefig('handoff/evidence/20260929-x20-subspace-review.png',dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
