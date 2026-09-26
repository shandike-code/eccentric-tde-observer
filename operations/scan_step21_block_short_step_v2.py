"""Read-only full-domain Linf-constrained line scan after the 77701 rejection."""
import argparse,math,os,resource,signal,sys,time
from pathlib import Path
import numpy as np
from operations import validate_step21_heating_blocks as global_run
from operations.constrained_hybrid_fields import chunks,physical
ROOT,pipeline,reused,fresh,v=global_run.ROOT,global_run.pipeline,global_run.reused,global_run.fresh,global_run.v
SOURCE='outputs/hpc/step21-heating-block-global-20260926'
BLOCKS=(24,48)
CONTROLS=dict(step_safety=.9,maximum_fraction=1.,minimum_l2_gain=.001,linf_roundoff=1e-10,
              radiation_limit=1e-4,boundary_limit=1e-3,maximum_field_passes=3)


def constrained_bound(raw,delta,maximum):
    if maximum<=0 or not np.isfinite([maximum]).all() or not np.isfinite(raw).all() or not np.isfinite(delta).all():raise ValueError('invalid constraint')
    if np.max(abs(raw))>maximum:raise ValueError('reference exceeds its own maximum')
    best=1.;position=None
    for mask,numerator,denominator in [(delta>0,maximum-raw,delta),(delta<0,maximum+raw,-delta)]:
        if not mask.any():continue
        indices=np.flatnonzero(mask)
        # 极小方向给出无约束的无穷上界；这里只忽略上界除法溢出，不修补物理场。
        with np.errstate(over='ignore',divide='raise',invalid='raise'):
            values=numerator.ravel()[indices]/denominator.ravel()[indices]
        j=int(np.argmin(values));value=float(values[j])
        if value<best:best=value;position=np.unravel_index(int(indices[j]),raw.shape)
    if best<0:raise ArithmeticError('zero fraction infeasible')
    return best,position


def choose(s0,dd,rd,upper):
    if not np.isfinite([s0,dd,rd,upper]).all() or s0<=0 or dd<0 or not 0<=upper<=1:raise ValueError('invalid line geometry')
    if dd==0 or rd>=0 or upper==0:return dict(fraction=0.,predicted_l2_ratio=1.,l2_cost_pass=False,reason='no nonzero constrained descent')
    optimum=-rd/dd;t=.9*min(optimum,upper,1.)
    square=s0+2*t*rd+t*t*dd
    if square<0:raise ArithmeticError('negative squared norm')
    ratio=math.sqrt(square/s0)
    return dict(fraction=t,unconstrained_l2_optimum=optimum,predicted_l2_ratio=ratio,l2_cost_pass=ratio<=.999,reason='fixed constrained optimum with ten percent step margin')


def scan(paths,shape,flux,original_row):
    slabs=[];fs=[[] for _ in paths];maximum=unchanged_scale=0.
    for start,(x,y,q,tq) in chunks(paths,shape):
        reused.checkpoint()
        if start//128 not in BLOCKS:
            if not np.array_equal(x,q):raise RuntimeError('undeclared input change')
            unchanged_scale=max(unchanged_scale,float(np.max(x)))
        with np.errstate(over='raise',invalid='raise'):
            r=y-x;d=(tq-q)-r
            s0=float(np.sum(r*r));dd=float(np.sum(d*d));rd=float(np.sum(r*d));m=float(np.max(abs(r)))
        maximum=max(maximum,m);slabs.append(dict(start=start,stop=start+len(x),s0=s0,dd=dd,rd=rd,maximum=m))
        for store,a in zip(fs,(x,y,q,tq)):store.append(flux(a,start))
    s0,dd,rd=[math.fsum(row[k] for row in slabs) for k in ('s0','dd','rd')]
    upper=1.;witness=None
    for start,(x,y,q,tq) in chunks(paths,shape):
        reused.checkpoint();r=y-x;d=(tq-q)-r;bound,index=constrained_bound(r,d,maximum)
        if bound<upper:
            upper=bound;i,j,k=index
            witness=dict(index=[int(start+i),int(j),int(k)],raw_hex=float(r[index]).hex(),delta_hex=float(d[index]).hex(),maximum_hex=float(maximum).hex(),upper=bound)
    choice=choose(s0,dd,rd,upper);checks={'nonzero_step':choice['fraction']>0,'l2_cost_pass':choice['l2_cost_pass']}
    fluxes=[np.concatenate(v) for v in fs]
    if any(a.shape!=(shape[0],) or not np.isfinite(a).all() for a in fluxes):raise ValueError('flux shape or finite failure')
    predictions={}
    if choice['fraction']>0:
        t=choice['fraction'];ss=[];selected_max=0.;affine_min=float('inf')
        # 第三遍逐点检验实际浮点组合与预测缺陷；不写候选、不调用算子。
        for start,(x,y,q,tq) in chunks(paths,shape):
            reused.checkpoint();a=(1-t)*x+t*q if start//128 in BLOCKS else x;b=(1-t)*y+t*tq
            physical(a);physical(b);delta=b-a
            selected_max=max(selected_max,float(np.max(abs(delta))));ss.append(float(np.sum(delta*delta)));affine_min=min(affine_min,float(a.min()),float(b.min()))
        ratio=math.sqrt(math.fsum(ss)/s0);checks['streamed_l2_cost_pass']=ratio<=.999
        checks['streamed_linf_nonincrease']=selected_max<=maximum*(1+1e-10)
        choice.update(streamed_l2_ratio=ratio,streamed_linf_ratio=selected_max/maximum,predicted_minimum=affine_min)
        if unchanged_scale<=0:raise ValueError('no positive unchanged field scale')
        checks['radiation_upper_bound']=selected_max/unchanged_scale<1e-4
        for label,f in [('selected',t),('half',t/2)]:
            inp=(1-f)*fluxes[0]+f*fluxes[2];out=(1-f)*fluxes[1]+f*fluxes[3]
            l1=float(np.sum(abs(out-inp)))/max(float(np.sum(abs(inp))),float(np.sum(abs(out))))
            bol=abs(float(out.sum()-inp.sum()))/max(abs(float(out.sum())),abs(float(inp.sum())))
            predictions[label]=dict(boundary_l1=l1,boundary_bolometric=bol)
            for key,value in predictions[label].items():checks[label+'_'+key]=np.isfinite(value) and 0<=value<1e-3 and value<=original_row[key]*(1+1e-10)
    return dict(choice=choice,checks={k:bool(v) for k,v in checks.items()},eligible_for_independent_review=all(checks.values()),
        original_l2=math.sqrt(s0),original_maximum=maximum,s0=s0,dd=dd,rd=rd,linf_upper=upper,witness=witness,
        slabs=slabs,boundary_predictions=predictions,fluxes=[a.tolist() for a in fluxes],
        unchanged_field_scale=unchanged_scale,passes=3 if choice['fraction']>0 else 2,
        actual_map_performed=False,candidate_written=False,accepted_material_step=False)


def prepare(out):
    ev=ROOT/'handoff/evidence';source=ROOT/SOURCE
    names=['declaration.json','summary.json','control/validation.json','control/config.json','control/trial_material.npz','control/state.json','half/state.json']
    claims=v.audited_inputs(source,ev/'20260926-block-global-review.json',ev/'20260926-heating-block-global-77701-terminal.json',77701,names)
    review=pipeline.read(ev/'20260926-block-global-review.json');val=pipeline.read(source/'control/validation.json');prior=pipeline.read(source/'declaration.json')
    if review['validated'] or val['validated'] or not val['checks']['independent_half_affinity']:raise RuntimeError('expected reviewed full-step rejection with valid half test')
    paths=list(val['source_pair'])+[val['candidate']]
    row=val['actual_map'];state=pipeline.read(source/'control/state.json')
    if state['active_map'] is not None or state['history']!=[row]:raise RuntimeError('source map must be settled and unique')
    paths.append(dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES))
    claims+=paths+prior['claims']+prior['code']
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/scan_step21_block_short_step_v2.sbatch','tests/test_scan_step21_block_short_step_serialization.py','handoff/protocols/step21-block-short-step-scan-v2.md')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(paths=paths,claims=claims,code=code,controls=CONTROLS,source_row=prior['source_row'],accepted_outer_steps=20,
        maximum_maps=0,maximum_feedback_pairs=0,maximum_candidate_writes=0,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    cfg=pipeline.read(source/'control/config.json');native,_,_,context=pipeline.configure_native(cfg,ROOT/paths[0]['path'])
    widths=np.diff(context['stencil'].active_lab_edge_hz)
    flux=lambda a,start:native.base._block_flux(a,context['mu'],context['weight'],widths[start:start+len(a)])
    return plan,flux


def execute(out):
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kwargs):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kwargs))
    mark('preparing')
    try:
        plan,flux=prepare(out);mark('scanning')
        result=scan([ROOT/c['path'] for c in plan['paths']],pipeline.SHAPE,flux,plan['source_row'])
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('scanner memory guard')
        result['peak_rss_bytes']=peak;reused.verify(plan['claims']+plan['code']);reused.immutable(out/'prediction.json',result)
        mark('complete_requires_review');reused.archive(out,'complete')
    except BaseException as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
