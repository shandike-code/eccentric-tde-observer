"""Frozen-x20 cross-history map diagnostics: scalar scan or one true midpoint map.

No material step, feedback integration, reference migration or iteration extension.
"""
import argparse, math, os, resource, shutil, signal, sys, time
from pathlib import Path
import numpy as np
from operations import calibrate_x20_radiation_histories as prior
from operations.constrained_hybrid_fields import chunks, physical
from operations.boundary_constrained_proposal import boundary_spectrum
ROOT,pipeline,reused,v,fresh=prior.ROOT,prior.pipeline,prior.reused,prior.v,prior.fresh
SOURCE='outputs/hpc/x20-radiation-history-calibration-20260929'
SOURCE_STATUS='stopped_at_historical_map24_eight_map_window_unresolved'
ALPHA_BOUNDS=(-8.,8.)
AFFINITY_LIMIT=1e-6


def retained_pair(state,retained,n):
    rows=state.get('history',[])
    if len(rows)!=n or state.get('active_map') is not None or retained['history_rows']!=rows[-2:]:
        raise ValueError('source history not settled at declared endpoint')
    if [r['iteration'] for r in rows]!=list(range(1,n+1)) or any(a['output_sha256']!=b['input_sha256'] for a,b in zip(rows,rows[1:])):
        raise ValueError('broken map sequence')
    pair=[retained['endpoints'][k] for k in ('final','mapped_final')]
    if [c['sha256'] for c in pair]!=[rows[-1]['input_sha256'],rows[-1]['output_sha256']]:raise ValueError('wrong retained map pair')
    if state['current_sha256']!=pair[-1]['sha256'] or any(c['size_bytes']!=pipeline.STATE_BYTES for c in pair):raise ValueError('wrong current state or size')
    return pair


def same_operator_config(a,b):
    # 本实验只允许目录、数值初值、来源清单不同；不能借两个trial相等忽略算子配置差异。
    ignore={'run','warm_seed','sources'}
    if {k:x for k,x in a.items() if k not in ignore}!={k:x for k,x in b.items() if k not in ignore}:
        raise ValueError('source operator configurations differ')


def prepare(out,mode):
    ap=ROOT/'handoff/evidence/20260929-x20-history-review.json';tp=ROOT/'handoff/evidence/20260929-x20-history-80554-terminal.json'
    audit=pipeline.read(ap)
    if (audit.get('job_id')!=80554 or audit.get('status')!=SOURCE_STATUS or not audit.get('independent_vector_reduction')
        or not audit.get('physical_state_x20_unchanged') or not audit.get('all_zero_pair_gates_passed')
        or audit.get('accepted_outer_steps')!=20 or audit.get('new_material_steps')!=0
        or audit.get('baseline_replaced') is not False or audit.get('reference_calibration_eligible') is not False):
        raise RuntimeError('independent rejected-history audit required')
    src=ROOT/SOURCE;names=['declaration.json','summary.json']
    for child,n in [('late',16),('historical',24)]:
        names += [f'{child}/{f}' for f in ('state.json','config.json','trial_material.npz',f'endpoints-map{n:02d}/manifest.json',f'pair{n:02d}/feedback_protocol.json')]
    claims=v.audited_inputs(src,ap,tp,80554,names)
    if pipeline.read(src/'summary.json')['status']!=SOURCE_STATUS:raise RuntimeError('source verdict changed')
    oldplan=pipeline.read(src/'declaration.json');reused.verify(oldplan['code'])
    cfgs=[];trials=[];pairs=[];rows=[]
    for child,n in [('late',16),('historical',24)]:
        folder=src/child;state=pipeline.read(folder/'state.json');cfg=pipeline.read(folder/'config.json')
        if pipeline.sha256(folder/'config.json')!=state['config_sha256']:raise RuntimeError('source config hash')
        pair=retained_pair(state,pipeline.read(folder/f'endpoints-map{n:02d}/manifest.json'),n)
        trial=v.load_arrays(folder/'trial_material.npz');p=pipeline.read(folder/f'pair{n:02d}/feedback_protocol.json');s=p['sources']
        for c in s.values():
            # 这里只直接复验本实验消费的物理输入；旧归档/代码血缘另有完整校验。
            if c in [s[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]:claims.append(c)
        base=v.load_arrays(ROOT/s['outer_base_material']['path']);r20=np.load(ROOT/s['base_residual']['path'],allow_pickle=False)
        old=v.load_arrays(ROOT/s['physical_old_time_level']['path']);prior.fixed.exact_trial(trial,base,r20,old,'control')
        native=prior.reused.audit_native_trial(cfg,trial)
        if not native['native_mirrored_material_exact'] or not native['physical_phase_and_dt_exact']:raise RuntimeError('native material mismatch')
        cfgs.append(cfg);trials.append(trial);pairs+=pair;rows.append(state['history'][-1]);claims+=pair
    same_operator_config(*cfgs);prior.fixed.same_trial(*trials)
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(src/'late/trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfgs[0])
    cases={'control':dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))}
    code=fresh.code_claims()+[pipeline.claim(ROOT/f) for f in ('operations/x20_history_scan.sbatch','operations/x20_history_midpoint.sbatch',
        'tests/test_x20_history_operator.py','handoff/protocols/x20-history-operator-v1.md')]
    claims+=list(cases['control'].values());claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    reused.verify(claims+code)
    _,_,_,ctx=pipeline.configure_native(cfgs[0],ROOT/pairs[0]['path'])
    geometry=dict(mu=np.asarray(ctx['mu']),weight=np.asarray(ctx['weight']),width=np.diff(ctx['stencil'].active_lab_edge_hz))
    np.savez(out/'boundary_geometry.npz',**geometry)
    plan=dict(mode=mode,source_job=80554,source=SOURCE,source_status=SOURCE_STATUS,field_pairs=pairs,source_rows=rows,
        cases=cases,claims=claims,code=code,environment=pipeline.environment(),frozen_x20=True,
        alpha_bounds=list(ALPHA_BOUNDS),coefficient_l1_cap=17.,step_safety=.9,affinity_limit=AFFINITY_LIMIT,
        maximum_maps=0 if mode=='scan' else 1,maximum_feedback_pairs=0,maximum_field_scans=2,
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,automatic_promotion=False,
        production_candidate_written=False,physical_dt_changed=False,historical_failures_retained=True)
    reused.immutable(out/'declaration.json',plan)
    return plan,geometry


def positivity_interval(base,direction):
    physical(base)
    if base.shape!=direction.shape or not np.isfinite(direction).all():raise ValueError('invalid affine direction')
    lo,hi=ALPHA_BOUNDS
    # 只有可能收紧已声明[-8,8]区间的分量才做除法，避免黑尾近零差值产生溢出商。
    pos=(direction>0)&(base < (-lo)*direction)
    neg=(direction<0)&(base < hi*(-direction))
    if np.any(pos):lo=max(lo,float(np.max(-base[pos]/direction[pos])))
    if np.any(neg):hi=min(hi,float(np.min(-base[neg]/direction[neg])))
    if not lo<=0<=hi:raise ValueError('zero anchor must be feasible')
    return lo,hi


def basis_stats(arrays):
    x,y,h,k=arrays
    for z in arrays:physical(z)
    if any(z.shape!=x.shape for z in arrays):raise ValueError('shape mismatch')
    # T固定物质时，差场D'=T(H)-T(L)检验慢衰减；不预设它是线性本征模。
    basis=[y-x,(k-h)-(y-x),h-x,k-y]
    wide=[z.astype(np.longdouble) for z in basis];g=np.zeros((4,4))
    for i in range(4):
        for j in range(i,4):g[i,j]=g[j,i]=float(np.sum(wide[i]*wide[j],dtype=np.longdouble))
    limits=[positivity_interval(x,h-x),positivity_interval(y,k-y)]
    return dict(gram=g.tolist(),alpha_interval=[max(t[0] for t in limits),min(t[1] for t in limits)],
        basis_linf=[float(np.max(abs(z))) for z in basis])


def select_coefficient(gram,interval):
    g=np.asarray(gram,float);lo,hi=interval
    if g.shape!=(4,4) or not np.isfinite(g).all() or not np.array_equal(g,g.T) or not ALPHA_BOUNDS[0]<=lo<=0<=hi<=ALPHA_BOUNDS[1]:
        raise ValueError('invalid moment system or interval')
    eig=np.linalg.eigvalsh(g);scale=float(np.max(abs(g)))
    if scale<=0 or eig.min() < -1e-12*scale or g[0,0]<=0 or g[2,2]<=0:raise ValueError('degenerate or non-PSD system')
    resolved=bool(g[1,1]>1e-12*g[0,0])
    optimum=-float(g[0,1]/g[1,1]) if resolved else None
    # 只在一个全局系数上做有界最小化，再退回10%；不截断任何辐射单元。
    bounded=(lo if optimum<lo else hi if optimum>hi else optimum) if resolved else 0.
    alpha=.9*bounded
    return dict(alpha=alpha,unconstrained_alpha=optimum,direction_resolved=resolved,alpha_interval=[lo,hi],
        coefficient_l1=abs(1-alpha)+abs(alpha),difference_gain_l2=math.sqrt(g[3,3]/g[2,2]),
        difference_projection=float(g[2,3]/g[2,2]),strict_error_bound=False)


def collect_scan(paths,shape,geometry,checkpoint=lambda:None):
    stats=[];fluxes=[]
    for start,aa in chunks(paths,shape):
        checkpoint();r=basis_stats(aa);r.update(first_group=start,group_count=len(aa[0]));stats.append(r)
        fluxes.append([boundary_spectrum(z,geometry['mu'],geometry['weight'],geometry['width'][start:start+len(z)]).tolist() for z in aa])
    g=np.array([[math.fsum(r['gram'][i][j] for r in stats) for j in range(4)] for i in range(4)])
    choice=select_coefficient(g,[max(r['alpha_interval'][0] for r in stats),min(r['alpha_interval'][1] for r in stats)])
    a=choice['alpha'];rows=[]
    for start,(x,y,h,k) in chunks(paths,shape):
        checkpoint();z=x+a*(h-x);p=y+a*(k-y);physical(z);physical(p)
        raw=y-x;pred=p-z;perp=(k-y)-choice['difference_projection']*(h-x)
        rows.append(dict(first_group=start,group_count=len(x),squared_l2=[float(np.sum(w.astype(np.longdouble)**2,dtype=np.longdouble)) for w in (raw,pred,perp)],
            linf=[float(np.max(abs(w))) for w in (raw,pred)],minimum_candidate=float(z.min()),minimum_prediction=float(p.min())))
    sums=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(3)];peaks=[max(r['linf'][i] for r in rows) for i in range(2)]
    spectra=[np.concatenate([np.asarray(f[i]) for f in fluxes]) for i in range(4)];fin,fout=spectra[:2]
    pin=fin+a*(spectra[2]-fin);pout=fout+a*(spectra[3]-fout)
    if np.any(pin<0) or np.any(pout<0):raise ValueError('negative predicted boundary spectrum')
    def metric(x,y):
        denom=max(math.fsum(abs(x)),math.fsum(abs(y)))
        if denom<=0:raise ValueError('zero boundary normalization')
        return dict(boundary_l1=math.fsum(abs(y-x))/denom,boundary_bolometric=abs(math.fsum(y-x))/denom)
    original,predicted=metric(fin,fout),metric(pin,pout)
    checks=dict(resolved_nonzero_direction=choice['direction_resolved'] and a!=0,
        coefficient_l1_bounded=choice['coefficient_l1']<=17,l2_benefit=math.sqrt(sums[1]/sums[0])<=.8,
        linf_nonincrease=peaks[1]<=peaks[0]*(1+1e-10))
    for k in original:checks[k]=predicted[k]<1e-3 and predicted[k]<=original[k]*(1+1e-10)
    return dict(choice=choice,gram=g.tolist(),slabs=stats,prediction_slabs=rows,surface_spectra=[z.tolist() for z in spectra],
        l2_ratio=math.sqrt(sums[1]/sums[0]),linf_ratio=peaks[1]/peaks[0],
        difference_nonparallel_fraction=math.sqrt(sums[2]/g[3,3]) if g[3,3]>0 else None,
        original_boundary=original,predicted_boundary=predicted,checks=checks,feasible=all(checks.values()),
        candidate_written=False,true_map_required=True,field_weighting='unweighted full grid; not radiative energy')


def write_midpoint(paths,target,shape,checkpoint=lambda:None):
    target=Path(target);tmp=target.with_suffix('.tmp')
    if target.exists() or tmp.exists():raise FileExistsError(target)
    with tmp.open('xb') as f:
        for _,(x,h) in chunks(paths,shape):
            checkpoint();m=.5*x+.5*h;physical(m);m.tofile(f)
    if tmp.stat().st_size!=int(np.prod(shape))*8:raise ValueError('midpoint size')
    tmp.replace(target)


def midpoint_comparison(paths,shape,checkpoint=lambda:None):
    rows=[]
    for start,(x,y,h,k,m,t) in chunks(paths,shape):
        checkpoint()
        if not np.array_equal(m,.5*x+.5*h):raise ValueError('not exact declared midpoint')
        fields=[y-x,k-h,t-m,t-(.5*y+.5*k),h-x]
        rows.append(dict(first_group=start,group_count=len(x),squared_l2=[float(np.sum(z.astype(np.longdouble)**2,dtype=np.longdouble)) for z in fields],
            linf=[float(np.max(abs(z))) for z in fields]))
    ss=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(5)];pp=[max(r['linf'][i] for r in rows) for i in range(5)]
    if min(ss[0],ss[1],ss[4],pp[0],pp[1])<=0:raise ValueError('unresolved comparison scale')
    # 两种自身原始defect尺度都检查；不能用大场强或更大的历史差把误差稀释。
    ratios=[math.sqrt(ss[3]/ss[i]) for i in (0,1)]
    infinity=[pp[3]/pp[i] for i in (0,1)]
    return dict(slabs=rows,squared_l2=ss,linf=pp,affinity_over_each_original_l2=ratios,
        affinity_over_each_original_linf=infinity,affinity_pass=all(z<=AFFINITY_LIMIT for z in ratios+infinity),
        true_map_performed=True,strict_error_bound=False,material_step_promoted=False)


def execute(out,mode):
    pipeline.require_allocation(4 if mode=='scan' else 16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,mode=mode,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        plan,geometry=prepare(out,mode);paths=[ROOT/c['path'] for c in plan['field_pairs']]
        if mode=='scan':
            mark('scanning');result=collect_scan(paths,pipeline.SHAPE,geometry,reused.checkpoint)
            reused.immutable(out/'prediction.json',result);maps=0
        else:
            if shutil.disk_usage(out).free<6*pipeline.STATE_BYTES:raise RuntimeError('insufficient midpoint disk budget')
            mark('writing_midpoint');midpoint=out/'midpoint.dat'
            write_midpoint([paths[0],paths[2]],midpoint,pipeline.SHAPE,reused.checkpoint)
            seed=pipeline.claim(midpoint);reused.immutable(out/'midpoint-claim.json',seed)
            reused.LIMITS=dict(midpoint=1)
            with prior.fixed.relay_dispatch():
                mark('initializing_midpoint');folder,cfg,state=reused.child(out,'midpoint','control',seed,plan)
                prior.fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),v.load_arrays(ROOT/plan['cases']['control']['trial']['path']))
                reused.checkpoint();mark('mapping_midpoint')
                driver=prior.old.recovery.original.driver
                if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial midpoint map retained')
                if state['status'] in driver.FAULT_STATUSES or len(state['history'])!=1 or state['active_map'] is not None:raise RuntimeError('midpoint mapping fault')
            receipts=list((folder/'map0001').glob('block*.process-*.json'))
            if len(receipts)!=76:raise RuntimeError('map receipt count')
            for f in receipts:
                q=pipeline.read(f)
                if q['returncode'] or not q['memory_guard_passed'] or q['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker resource fault')
            row=state['history'][0]
            if row['input_sha256']!=seed['sha256']:raise RuntimeError('wrong midpoint mapped')
            mark('comparing_midpoint');result=midpoint_comparison(paths+[midpoint,ROOT/row['output_path']],pipeline.SHAPE,reused.checkpoint)
            result.update(actual_map=row,worker_maximum_proc_kib=max(pipeline.read(f)['native_observed_peak_kib'] for f in receipts))
            reused.immutable(out/'validation.json',result)
            reused.verify([seed,dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES)]);maps=1
        reused.verify(plan['claims']+plan['code'])
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('parent memory guard')
        status='complete_requires_review'
        reused.immutable(out/'summary.json',dict(status=status,mode=mode,source_job=80554,new_maps=maps,new_feedback_pairs=0,
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
            scan_feasible=result['feasible'] if mode=='scan' else None,affinity_pass=result['affinity_pass'] if mode=='midpoint' else None,
            parent_peak_rss_bytes=peak,wall_s=time.monotonic()-started,historical_failures_retained=True))
        mark(status);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',error=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['scan','midpoint'],required=True);p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run),a.mode)
