"""Independent 70-digit halfspace-vertex/support audit of job 81453.

No production polygon, cutting-plane solver or coefficient minimizer is imported.
"""
import itertools,json,math
from decimal import Decimal,localcontext
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from handoff.audit_tools.review_x20_operator import old,cw,read,arrays
from handoff.audit_tools.review_x20_histories import source_archive

ROOT=Path('outputs/review-20260925')
BASE='complete-1790696920776063589'
OUT=ROOT/'x20-spectral-81453-received'
D=lambda x:Decimal.from_float(float(x))


def dot(x,y):return sum(a*b for a,b in zip(x,y))


def linear(matrix,rhs):
    a=[list(row)+[b] for row,b in zip(matrix,rhs)];n=len(a)
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(a[i][j]));a[j],a[k]=a[k],a[j]
        if abs(a[j][j])<Decimal('1e-55'):return None
        pivot=a[j][j];a[j]=[v/pivot for v in a[j]]
        for i in range(n):
            if i!=j:
                z=a[i][j];a[i]=[x-z*y for x,y in zip(a[i],a[j])]
    return [row[-1] for row in a]


def cap_halfspaces():
    # ||w||1<=17等价于全部16种符号的s.w<=17，独立于生产顶点/截取法。
    return [([D(s[0]-s[1]),D(s[2]-s[1]),D(s[3]-s[1])],D(17-s[1]))
            for s in itertools.product((-1,1),repeat=4)]


def vertices(flux,inequalities):
    result=[];eps=Decimal('1e-45')
    for (a,b),(c,d) in itertools.combinations(inequalities,2):
        point=linear([flux[1:],a,c],[-flux[0],b,d])
        if point is None or any(dot(x,point)>y+eps for x,y in inequalities):continue
        if not any(max(abs(x-y) for x,y in zip(point,p))<eps for p in result):result.append(point)
    assert len(result)>=3
    return result


def audit_numbers(gram,spectra,saved):
    fs=np.asarray(spectra);g=np.asarray(gram)
    assert fs.shape==(6,9632) and np.isfinite(fs).all() and np.all(fs>=0)
    assert g.shape==(4,4) and np.array_equal(g,g.T) and np.isfinite(g).all()
    assert np.linalg.eigvalsh(g[1:,1:]).min()>0
    a,b,c,h,j,k=fs;scale=max(math.fsum(b),math.fsum(c));r=(c-b)/scale
    directions=np.array([(b-a)-(c-b),(j-h)-(c-b),(k-j)-(c-b)])/scale
    inputs=np.array([a-b,h-b,j-b])/scale
    flux=np.r_[math.fsum(r),[math.fsum(v) for v in directions]]
    limit=math.fsum(abs(r))*(1+1e-10)
    np.testing.assert_allclose(flux,saved['boundary_flux_coefficients'],rtol=1e-12,atol=0)
    assert math.isclose(limit,saved['spectral_limit'],rel_tol=1e-12)
    anchor=np.array(saved['plane_anchor']);basis=np.array(saved['plane_basis']);trace=[]
    with localcontext() as ctx:
        ctx.prec=70;f=list(map(D,flux));inequalities=cap_halfspaces();gd=[[D(v)/D(g[0,0]) for v in row] for row in g]
        for row in saved['iterations']:
            vv=vertices(f,inequalities);point=np.array(row['raw_coefficients']);pd=list(map(D,point));t=D(.9)
            assert abs(dot(f[1:],pd)+f[0])<Decimal('1e-20')
            assert all(dot(x,pd)<=y+Decimal('1e-10') for x,y in inequalities)
            # 双向包含核对生产多边形；本证书下界使用独立枚举的全部顶点。
            polygon=np.asarray(row['polygon']);actual=anchor+polygon@basis.T
            for p in actual:assert all(float(dot(x,list(map(D,p)))-y)<1e-8 for x,y in inequalities)
            projected=np.linalg.lstsq(basis,(np.array(vv,float)-anchor).T,rcond=None)[0].T
            hull=ConvexHull(polygon)
            assert np.max(projected@hull.equations[:,:2].T+hull.equations[:,2])<1e-8
            u=[D(1)]+[t*z for z in pd]
            value=sum(u[i]*gd[i][j]*u[j] for i in range(4) for j in range(4))
            gradient=[2*t*dot(gd[i+1],u) for i in range(3)]
            support=value+min(dot(gradient,[z-x for z,x in zip(v,pd)]) for v in vv)
            np.testing.assert_allclose([float(value),float(support)],[row['bound']['squared_upper'],row['bound']['squared_support_lower']],rtol=2e-10,atol=0)
            # 支撑面达到当前值才称找到最小值；不把任意候选的二次值冒充下界。
            assert abs(value-support)<Decimal('1e-8')
            cuts=[]
            for tfloat,stored in zip((.9,.45),row['cuts']):
                difference=r+tfloat*(point@directions)
                signed=math.fsum(difference);input_total=math.fsum(b)/scale+tfloat*math.fsum(point*np.array([math.fsum(v) for v in inputs]))
                den=input_total+max(signed,0.);num=math.fsum(abs(difference));signs=np.sign(difference)
                aa=tfloat*np.array([math.fsum(signs*v)/limit-math.fsum(di) for v,di in zip(directions,inputs)])
                bb=math.fsum(b)/scale+max((1-tfloat)*flux[0],0.)-math.fsum(signs*r)/limit
                np.testing.assert_allclose(aa,stored['a'],rtol=2e-10,atol=1e-12)
                np.testing.assert_allclose([bb,num,den,num/(limit*den)],[stored['b'],stored['numerator'],stored['denominator'],stored['ratio_to_limit']],rtol=2e-10,atol=1e-16)
                assert int(np.count_nonzero(difference>0))==stored['positive_groups']
                assert int(np.count_nonzero(difference<0))==stored['negative_groups']
                cuts.append((aa,bb,num/(limit*den)))
            trace.append(dict(iteration=row['iteration'],independent_vertices=len(vv),squared_value_70digit=str(value),squared_support_lower_70digit=str(support),l2_lower_70digit=str(support.sqrt()),spectral_ratios=[z[2] for z in cuts]))
            for aa,bb,ratio in cuts:
                if ratio>1:inequalities.append((list(map(D,aa)),D(bb)))
        assert saved['status']=='no_20pct_candidate_in_registered_plane' and support>Decimal('.64')
    return dict(trace=trace,decimal_precision=70,scope='registered raw zero-net-flux plane, weight L1 <= 17, full fraction 0.9',no_20pct_candidate_in_registered_plane=True,all_three_dimensional_directions_excluded=False,physical_model_nonexistence=False)


def main():
    m=cw.receive(ROOT/(BASE+'.tar.gz'),ROOT/(BASE+'-receipt.json'),OUT)
    assert m==read(ROOT/(BASE+'.json')) and len(m['files'])==9
    d=read(OUT/'declaration.json');pre=read(OUT/'source-preflight/declaration.json');s=read(OUT/'summary.json');p=read(OUT/'feasibility.json')
    terminal=read(Path('handoff/evidence/20260929-x20-spectral-81453-terminal.json'))
    assert terminal['job_id']==81453 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    assert d['environment']['scheduler']['SLURM_JOB_ID']=='81453'
    assert d['maximum_maps']==d['maximum_feedback_pairs']==d['new_material_steps']==0
    assert d['maximum_field_scans']==1 and d['maximum_cut_iterations']==64 and d['accepted_outer_steps']==20
    assert d['source_jobs']==[80554,80862,80925] and d['coefficient_l1_cap']==17 and d['selected_fraction']==.9
    assert not d['baseline_replaced'] and not d['candidate_written'] and d['registered_plane_only']
    assert s['status']==p['status']==read(OUT/'status.json')['status'] and s['field_scans']==1 and s['cut_iterations']==len(p['iterations'])==2
    assert s['new_maps']==s['new_feedback_pairs']==s['new_material_steps']==0 and s['accepted_outer_steps']==20
    assert not any(s[k] for k in ('baseline_replaced','strict_error_bound','candidate_written')) and s['parent_peak_rss_bytes']<6*1024**3
    for claim in d['code']+pre['code']:old.verify_claim(claim,Path(claim['path']))
    index={c['path']:c for c in d['claims']}
    for tag,job,run in [('subspace',80862,'x20-boundary-subspace-20260929'),('capped',80925,'x20-capped-subspace-20260929')]:
        folder=ROOT/f'x20-{tag}-{job}-received';source_archive(folder,f'20260929-x20-{tag}-review.json',ROOT)
        for name in ('declaration.json','summary.json','prediction.json'):old.verify_claim(index['outputs/hpc/'+run+'/'+name],folder/name)
        for name in (f'20260929-x20-{tag}-review.json',f'20260929-x20-{tag}-{job}-terminal.json'):old.verify_claim(index['handoff/evidence/'+name],Path('handoff/evidence')/name)
    previous=ROOT/'x20-capped-80925-received'
    previous_declaration=read(previous/'declaration.json')
    assert d['basis']==previous_declaration['basis'] and set(d['cases'])=={'control'}
    assert set(d['cases']['control'])=={'trial','config'}
    for name,claim in d['cases']['control'].items():
        earlier=previous_declaration['cases']['control'][name]
        assert (claim['size_bytes'],claim['sha256'])==(earlier['size_bytes'],earlier['sha256'])
        assert claim['path']=='outputs/hpc/x20-spectral-feasibility-20260929/source-preflight/inputs/'+Path(earlier['path']).name
    assert pre['field_pairs']==[d['basis'][i] for i in (1,2,4,5)]
    for c in d['cases']['control'].values():old.verify_claim(c,OUT/'source-preflight/inputs'/Path(c['path']).name)
    for name in ('config.json','trial_material.npz'):assert old.digest(OUT/'source-preflight/inputs'/name)==old.digest(previous/'source-preflight/inputs'/name)
    trial=arrays(OUT/'source-preflight/inputs/trial_material.npz');assert int(trial['phase_index'])==1367 and float(trial['step_duration_s'])==889.419892762322
    data=arrays(OUT/'boundary-spectra.npz');prior=read(previous/'prediction.json')
    assert np.array_equal(data['gram'],prior['gram']) and np.array_equal(data['original_boundary_coefficients'],prior['boundary_coefficients'])
    result=audit_numbers(data['gram'],data['spectra'],p)
    result.update(job_id=81453,archive=read(ROOT/(BASE+'-receipt.json')),verified_files=9,verified_code_claims=len(d['code']),new_maps=0,new_feedback_pairs=0,new_material_steps=0,accepted_outer_steps=20,baseline_replaced=False,independent_small_statistic_reduction=True,large_fields_recomputed_on_mac=False,strict_physical_error_bound=False,parent_peak_rss_bytes=s['parent_peak_rss_bytes'],wall_s=s['wall_s'])
    Path('handoff/evidence/20260929-x20-spectral-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    import csv
    with Path('handoff/evidence/20260929-x20-spectral-review.csv').open('w',newline='') as handle:
        writer=csv.writer(handle,lineterminator='\n');writer.writerow(['constraint_round','l2_optimistic_lower','full_spectral_ratio','half_spectral_ratio'])
        for row in result['trace']:writer.writerow([row['iteration'],row['l2_lower_70digit'],*row['spectral_ratios']])
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained');x=[0,1]
    axes[0].plot(x,[float(r['l2_lower_70digit']) for r in result['trace']],'o-',label='Independent optimistic lower bound')
    axes[0].axhline(.8,color='r',ls='--',label='Required full L2 <= 0.8')
    axes[0].set(ylabel='Predicted defect L2 / original late',ylim=(.7,1.));axes[0].legend(fontsize=8)
    for i,label in enumerate(('Full','Half')):axes[1].plot(x,[r['spectral_ratios'][i] for r in result['trace']],'o-',label=label)
    axes[1].axhline(1,color='r',ls='--',label='Spectral nonincrease limit')
    axes[1].set(ylabel='Boundary spectral L1 / limit',yscale='log');axes[1].legend(fontsize=8)
    for ax in axes:ax.set(xticks=x,xticklabels=['Initial slice','After necessary cuts'],xlabel='Constraint refinement; zero new maps')
    fig.savefig('handoff/evidence/20260929-x20-spectral-review.png',dpi=150);plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
