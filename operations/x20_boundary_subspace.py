"""A three-direction full-frequency proposal with an explicit boundary constraint.

At most one proposal and two true maps. No feedback or material promotion.
"""
import argparse,math,os,resource,signal,sys,time,shutil
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import seven_block_global_fields as actual
ROOT,pipeline,reused=core.ROOT,core.pipeline,core.reused
RCOND=1e-12
CAP=17.


def basis_fields(aa,c):
    a,b,d,h,i,j=aa;c=np.asarray(c,float)
    if c.shape!=(3,) or not np.isfinite(c).all():raise ValueError('invalid three-direction coefficients')
    # anchor是late的最后一次真实map输入b；候选和预测输出使用同一组全域系数。
    return b+c[0]*(a-b)+c[1]*(h-b)+c[2]*(i-b),d+c[0]*(b-d)+c[1]*(i-d)+c[2]*(j-d)


def weights(c):
    return np.array([c[0],1-math.fsum(c),c[1],c[2]])


def constrained_solution(g,flux):
    g=np.asarray(g,float);f=np.asarray(flux,float)
    if g.shape!=(4,4) or f.shape!=(4,) or not np.isfinite(g).all() or not np.isfinite(f).all() or not np.array_equal(g,g.T):
        raise ValueError('invalid small system')
    a=g[1:,1:];rhs=-g[0,1:];values,vectors=np.linalg.eigh(a);scale=float(np.max(abs(values)))
    if scale<=0 or g[0,0]<=0 or values.min()<-RCOND*scale:raise ValueError('unresolved or indefinite system')
    keep=values>RCOND*scale
    if not np.any(keep):raise ValueError('no resolved subspace')
    # 仅在已分辨特征方向白化；不改真实辐射场、残差定义或能量。
    transform=vectors[:,keep]*np.sqrt(scale/values[keep])[None,:]
    z=transform.T@rhs/scale
    fscale=float(np.max(abs(f)))
    if fscale==0:normalized=np.zeros(4)
    else:normalized=f/fscale
    h=transform.T@normalized[1:];h2=float(h@h)
    if h2==0:
        if normalized[0]!=0:raise ValueError('boundary constraint outside resolved subspace')
    else:z=z+(-normalized[0]-float(h@z))*h/h2
    c=transform@z
    if not np.isfinite(c).all():raise ValueError('nonfinite constrained solution')
    violation=float(normalized[0]+normalized[1:]@c)
    if abs(violation)>1e-10*(1+float(np.linalg.norm(normalized[1:]))*float(np.linalg.norm(c))):raise ArithmeticError('boundary constraint not solved')
    return c,dict(eigenvalues=values.tolist(),retained_rank=int(keep.sum()),relative_cutoff=RCOND,
        normalized_boundary_residual=violation,raw_coefficients=c.tolist(),raw_weights=weights(c).tolist(),
        constraint='signed boundary map change zero before global backtracking',strict_error_bound=False)


def positive_upper(anchor,target):
    core.physical(anchor)
    if anchor.shape!=target.shape or not np.isfinite(target).all():raise ValueError('invalid proposed field')
    bad=target<0
    if not np.any(bad):return 1.
    # 仅对负的试探终点算真实正性边界；缩放避免极弱尾端除法下溢。
    a=anchor[bad];t=target[bad];s=np.maximum(a,-t)
    return float(np.min((a/s)/((a/s)-(t/s))))


def bounded_coefficients(c,upper):
    c=np.asarray(c,float)
    if not 0<=upper<=1:raise ValueError('invalid positivity bound')
    bound=upper
    if np.sum(abs(weights(bound*c)))>CAP:
        lo,hi=0.,bound
        for _ in range(64):
            mid=(lo+hi)/2
            if np.sum(abs(weights(mid*c)))<=CAP:lo=mid
            else:hi=mid
        bound=lo
    beta=.9*bound
    return beta*c,dict(positivity_upper=upper,bounded_upper=bound,selected_fraction=beta,coefficient_l1=float(np.sum(abs(weights(beta*c)))))


def spectrum(z,start,geometry):
    return core.boundary_spectrum(z,geometry['mu'],geometry['weight'],geometry['width'][start:start+len(z)])


def measure_candidates(paths,shape,c,geometry,checkpoint=lambda:None):
    rows=[]
    for start,aa in core.chunks(paths,shape):
        checkpoint();q,p=basis_fields(aa,c);x,y=aa[1:3];h=.5*x+.5*q;hp=.5*y+.5*p
        for z in (q,p,h,hp):core.physical(z)
        defects=[y-x,p-q,hp-h];ff=[spectrum(z,start,geometry) for z in (x,y,q,p,h,hp)]
        rows.append(dict(first_group=start,group_count=len(x),squared_l2=[float(np.sum(z.astype(np.longdouble)**2,dtype=np.longdouble)) for z in defects],
            linf=[float(np.max(abs(z))) for z in defects],scales=[max(float(np.max(u)),float(np.max(v))) for u,v in ((x,y),(q,p),(h,hp))],
            minima=[float(z.min()) for z in (q,p,h,hp)],boundary_flux=[math.fsum(z) for z in ff],
            boundary_l1_numerator=[math.fsum(abs(ff[i+1]-ff[i])) for i in (0,2,4)],
            boundary_signed=[math.fsum(ff[i+1]-ff[i]) for i in (0,2,4)]))
    sums=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(3)];peaks=[max(r['linf'][i] for r in rows) for i in range(3)]
    if sums[0]<=0 or peaks[0]<=0:raise ValueError('zero reference defect')
    flux=[math.fsum(r['boundary_flux'][i] for r in rows) for i in range(6)];boundary=[]
    for i in range(3):
        den=max(flux[2*i:2*i+2]);scale=max(r['scales'][i] for r in rows)
        if den<=0 or scale<=0:raise ValueError('zero boundary/field scale')
        boundary.append(dict(boundary_l1=math.fsum(r['boundary_l1_numerator'][i] for r in rows)/den,
            boundary_bolometric=abs(math.fsum(r['boundary_signed'][i] for r in rows))/den,residual=peaks[i]/scale))
    ratios=[math.sqrt(z/sums[0]) for z in sums];maxima=[z/peaks[0] for z in peaks]
    checks=dict(full_l2_benefit=ratios[1]<=.8,full_linf_nonincrease=maxima[1]<=1.0000000001,
        half_l2_nonincrease=ratios[2]<=1.0000000001,half_linf_nonincrease=maxima[2]<=1.0000000001)
    for i,name in [(1,'full'),(2,'half')]:
        checks[name+'_radiation']=boundary[i]['residual']<1e-4
        for key in ('boundary_l1','boundary_bolometric'):checks[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]*1.0000000001
    return dict(slabs=rows,fixed_scale_l2_ratios=ratios,fixed_scale_linf_ratios=maxima,boundary=boundary,checks=checks,passed=all(checks.values()))


def propose(paths,shape,geometry,checkpoint=lambda:None):
    rows=[]
    for start,aa in core.chunks(paths,shape):
        checkpoint();a,b,d,h,i,j=aa;raw=d-b
        basis=[raw,(b-a)-raw,(i-h)-raw,(j-i)-raw]
        wide=[z.astype(np.longdouble) for z in basis];g=np.zeros((4,4))
        for k in range(4):
            for l in range(k,4):g[k,l]=g[l,k]=float(np.sum(wide[k]*wide[l],dtype=np.longdouble))
        ff=[spectrum(z,start,geometry) for z in aa]
        signed=[math.fsum(ff[y]-ff[x]) for x,y in ((0,1),(1,2),(3,4),(4,5))]
        rows.append(dict(first_group=start,group_count=len(a),gram=g.tolist(),signed_boundary=[signed[1],signed[0]-signed[1],signed[2]-signed[1],signed[3]-signed[1]]))
    g=[[math.fsum(r['gram'][i][j] for r in rows) for j in range(4)] for i in range(4)]
    f=[math.fsum(r['signed_boundary'][i] for r in rows) for i in range(4)]
    c,solve=constrained_solution(g,f);limits=[]
    for start,aa in core.chunks(paths,shape):
        checkpoint();q,p=basis_fields(aa,c)
        limits.append(dict(first_group=start,group_count=len(q),upper=min(positive_upper(aa[1],q),positive_upper(aa[2],p)),
            negative_candidate=int(np.count_nonzero(q<0)),negative_prediction=int(np.count_nonzero(p<0))))
    selected,bounds=bounded_coefficients(c,min(r['upper'] for r in limits))
    measured=measure_candidates(paths,shape,selected,geometry,checkpoint)
    passed=measured['passed'] and bounds['selected_fraction']>0 and bounds['coefficient_l1']<=CAP
    return dict(system_slabs=rows,gram=g,boundary_coefficients=f,solve=solve,positivity_slabs=limits,bounds=bounds,
        selected_coefficients=selected.tolist(),weights=weights(selected).tolist(),prediction=measured,
        all_predicted_checks_passed=passed,candidate_written=False,strict_error_bound=False)


def write_candidates(paths,shape,c,full,half,checkpoint=lambda:None):
    temporary=[p.with_suffix('.tmp') for p in (full,half)]
    if any(p.exists() for p in (full,half,*temporary)):raise FileExistsError('candidate path already exists')
    with temporary[0].open('xb') as f,temporary[1].open('xb') as h:
        for _,aa in core.chunks(paths,shape):
            checkpoint();q,_=basis_fields(aa,c);m=.5*aa[1]+.5*q;core.physical(q);core.physical(m);q.tofile(f);m.tofile(h)
    if any(p.stat().st_size!=int(np.prod(shape))*8 for p in temporary):raise ValueError('candidate size')
    for a,b in zip(temporary,(full,half)):a.replace(b)


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        ev=ROOT/'handoff/evidence';claims=[]
        for mode,job,run in [('scan',80826,'x20-history-scan-v2-20260929'),('midpoint',80823,'x20-history-midpoint-20260929')]:
            ap=ev/f'20260929-x20-{mode}-review.json';tp=ev/f'20260929-x20-{mode}-{job}-terminal.json';audit=pipeline.read(ap)
            if not audit['independent_small_statistic_reduction'] or audit['new_material_steps']!=0 or audit['baseline_replaced']:raise RuntimeError('independent source review missing')
            if mode=='scan' and audit['feasible']:raise RuntimeError('expected rejected single direction')
            if mode=='midpoint' and not audit['affinity_pass']:raise RuntimeError('midpoint affinity not validated')
            claims+=core.v.audited_inputs(ROOT/'outputs/hpc'/run,ap,tp,job,['declaration.json','summary.json','prediction.json' if mode=='scan' else 'validation.json'])
        pre=out/'source-preflight';pre.mkdir();plan,geometry=core.prepare(pre,'scan')
        basis=[]
        for child,n in [('late',16),('historical',24)]:
            retained=pipeline.read(ROOT/core.SOURCE/child/f'endpoints-map{n:02d}/manifest.json')
            basis += [retained['endpoints'][k] for k in ('previous','final','mapped_final')]
        if [basis[i] for i in (1,2,4,5)]!=plan['field_pairs']:raise RuntimeError('four-map basis identity changed')
        code=core.fresh.code_claims()+[pipeline.claim(ROOT/f) for f in ('operations/x20_boundary_subspace.sbatch','tests/test_x20_boundary_subspace.py','handoff/protocols/x20-boundary-subspace-v1.md')]
        claims+=plan['claims']+plan['code']+basis;claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
        declaration=dict(cases=plan['cases'],claims=claims,code=code,basis=basis,source_row=plan['source_rows'][0],source_jobs=[80554,80826,80823],
            maximum_maps=2,maximum_feedback_pairs=0,maximum_field_scans=5,maximum_proposals=1,coefficient_l1_cap=CAP,rcond=RCOND,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,automatic_promotion=False,strict_error_bound=False,
            fixed_material_x20=True,historical_failures_retained=True,environment=pipeline.environment())
        reused.immutable(out/'declaration.json',declaration);paths=[ROOT/c['path'] for c in basis]
        mark('three_pass_subspace_prediction');prediction=propose(paths,pipeline.SHAPE,geometry,reused.checkpoint)
        reused.immutable(out/'prediction.json',prediction);maps=0;validated=False;status='prediction_rejected'
        if prediction['all_predicted_checks_passed']:
            if shutil.disk_usage(out).free<10*pipeline.STATE_BYTES:raise RuntimeError('insufficient disk')
            full,half=out/'full.dat',out/'half.dat';mark('writing_candidates')
            write_candidates(paths,pipeline.SHAPE,prediction['selected_coefficients'],full,half,reused.checkpoint)
            seeds={n:pipeline.claim(p) for n,p in [('full',full),('half',half)]};reused.immutable(out/'candidate-claims.json',seeds)
            reused.LIMITS=dict(full=1,half=1);measured={}
            with core.prior.fixed.relay_dispatch():
                for name in ('full','half'):
                    mark('mapping',case=name);folder,cfg,state=reused.child(out,name,'control',seeds[name],declaration)
                    core.prior.fixed.same_trial(core.v.load_arrays(folder/'trial_material.npz'),core.v.load_arrays(ROOT/plan['cases']['control']['trial']['path']))
                    driver=core.prior.old.recovery.original.driver
                    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
                    if len(state['history'])!=1 or state['active_map'] is not None or state['status'] in driver.FAULT_STATUSES:raise RuntimeError('map state fault')
                    rr=list((folder/'map0001').glob('block*.process-*.json'))
                    if len(rr)!=76:raise RuntimeError('process receipt count')
                    for f in rr:
                        q=pipeline.read(f)
                        if q['returncode'] or not q['memory_guard_passed'] or q['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')
                    measured[name]=state['history'][0];maps+=1
                    if measured[name]['input_sha256']!=seeds[name]['sha256']:raise RuntimeError('candidate identity')
            mark('validating_true_maps')
            report=actual.validate([paths[1],paths[2],full,ROOT/measured['full']['output_path'],half,ROOT/measured['half']['output_path']],pipeline.SHAPE,blocks=tuple(range(76)),checkpoint=reused.checkpoint)
            checks=actual.checks(report,plan['source_rows'][0],measured['full'],measured['half'])
            checks['independent_half_linf_affinity']=report['fixed_scale_linf_ratios'][3]<=1e-6
            validated=all(checks.values());status='true_maps_validated_requires_review' if validated else 'true_map_validation_rejected'
            reused.immutable(out/'validation.json',dict(field_comparison=report,actual_maps=measured,checks=checks,validated=validated,baseline_replaced=False,material_step_promoted=False))
            reused.verify(list(seeds.values())+[dict(path=r['output_path'],sha256=r['output_sha256'],size_bytes=pipeline.STATE_BYTES) for r in measured.values()])
        reused.verify(claims+code);peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent memory guard')
        reused.immutable(out/'summary.json',dict(status=status,new_maps=maps,new_feedback_pairs=0,accepted_outer_steps=20,new_material_steps=0,
            baseline_replaced=False,strict_error_bound=False,all_predicted_checks_passed=prediction['all_predicted_checks_passed'],
            validated=validated,parent_peak_rss_bytes=peak,wall_s=time.monotonic()-started,historical_failures_retained=True))
        mark(status);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
