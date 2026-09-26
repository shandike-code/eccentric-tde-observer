"""Real radiation and atomic-heating validation of one frozen thermal projection."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import resource
import shutil
import signal
import sys
import time
import numpy as np
from operations import scan_step21_wide_plane as wide
from operations import recover_step21_control_windows as recovery
from operations import probe_step21_heating_projection as probe

v=wide.validation
ROOT,pipeline,fresh,fixed,reused,driver=v.ROOT,v.pipeline,v.fresh,v.fixed,v.reused,v.driver
StreamState=v.StreamState
SOURCE=probe.SOURCE
SCAN='outputs/hpc/step21-heating-projection-20260926'
LIMIT=10
HEATING_ERROR_LIMIT=1e-3


def select_candidate(declaration,prediction,audit,basis,proxy):
    if not prediction['eligible_for_independent_review'] or not audit['eligible_for_independent_review']:
        raise RuntimeError('candidate not independently eligible')
    gates=probe.screening_gates(prediction['field'],proxy)
    if gates!=prediction['gates'] or gates!=audit['gates'] or not all(gates.values()):
        raise RuntimeError('screening gates changed')
    if declaration['basis']!=basis or declaration['proxy']!=proxy or prediction['proxy']!=proxy:
        raise RuntimeError('audited source or proxy changed')
    uv=[0.,proxy['alpha']]
    if declaration['uv']!=uv or prediction['field']['uv']!=uv:
        raise RuntimeError('audited coefficients changed')
    for key in ('actual_map_performed','actual_candidate_heating_computed','accepted_material_step'):
        if prediction[key]:raise RuntimeError('source prediction is not unmeasured')
    for key,value in (('alpha',proxy['alpha']),('proxy_ratio',proxy['proxy_ratio'])):
        if not np.isclose(audit[key],value,rtol=1e-13,atol=0):raise RuntimeError('independent proxy differs')
    return uv


def conditional_sequence(validate,map_one,feedback):
    if not validate():return 'true_map_not_validated'
    map_one(2)
    if not feedback(2):return 'first_control_or_heating_not_validated'
    for n in range(3,11):map_one(n)
    if not feedback(10):return 'second_control_pair_not_stable'
    return 'heating_projection_validation_complete_requires_review'


def freeze_heating(q,reference_energy,dt,rho,mass,alpha):
    proxy=probe.heating_projection(q,dt,rho,reference_energy,mass)
    if not np.isclose(proxy['alpha'],alpha,rtol=1e-13,atol=0):raise RuntimeError('projection coefficient differs')
    # Q单位erg s^-1 cm^-3；dt/rho/u_ref乘Q后无量纲，只固定旧参考能量。
    q=np.asarray(q);scale=dt/np.asarray(rho)/np.asarray(reference_energy)
    predicted_q=q[2]+alpha*(q[0]-q[2]);predicted_p=q[3]+alpha*(q[1]-q[3])
    late=(q[3]-q[2])*scale;early=(q[1]-q[0])*scale
    predicted_s=late+alpha*(early-late)
    return dict(alpha=alpha,source_q=q.tolist(),reference_energy=np.asarray(reference_energy).tolist(),
        dt=float(dt),rho=np.asarray(rho).tolist(),mass=np.asarray(mass).tolist(),scale=scale.tolist(),
        predicted_q=predicted_q.tolist(),predicted_p=predicted_p.tolist(),predicted_s=predicted_s.tolist(),
        source_late_s=late.tolist(),source_proxy_norm=proxy['source_proxy_norm'],
        source_proxy_max=float(np.max(np.abs(late))),proxy=proxy,
        prediction_error_limit=HEATING_ERROR_LIMIT,actual_cost_ratio_limit=.8)


def heating_checks(reference,previous,final):
    # The reference is frozen before mapping. No new response energy appears here.
    arrays={k:np.asarray(reference[k],float) for k in
        ('scale','mass','predicted_q','predicted_p','predicted_s','source_late_s')}
    shape=arrays['mass'].shape
    q=np.asarray(previous,float);p=np.asarray(final,float)
    if len(shape)!=1 or q.shape!=shape or p.shape!=shape or any(x.shape!=shape for x in arrays.values()):
        raise ValueError('heating cell shape mismatch')
    if not all(np.isfinite(x).all() for x in [q,p,*arrays.values()]):raise ValueError('nonfinite heating')
    if np.any(arrays['mass']<=0) or np.any(arrays['scale']<=0):raise ValueError('positive scale and mass required')
    w=arrays['mass']/arrays['mass'].sum()
    norm=lambda x:float(np.sqrt(np.sum(w*x*x)))
    denominator=reference['source_proxy_norm'];maximum=reference['source_proxy_max']
    if denominator<=0 or maximum<=0 or not np.isclose(norm(arrays['source_late_s']),denominator,rtol=1e-13,atol=0):
        raise RuntimeError('invalid source normalization')
    s=(p-q)*arrays['scale']
    errors={'previous':(q-arrays['predicted_q'])*arrays['scale'],
            'final':(p-arrays['predicted_p'])*arrays['scale'],'difference':s-arrays['predicted_s']}
    metrics={k:dict(mass_over_source=norm(x)/denominator,max_over_source=float(np.max(np.abs(x)))/maximum)
             for k,x in errors.items()}
    cost=norm(s)/denominator
    checks={'actual_heating_cost_pass':0<=cost<.8}
    checks.update({k+'_prediction_error_pass':all(0<=z<HEATING_ERROR_LIMIT for z in v.values()) for k,v in metrics.items()})
    return dict(actual_s=s.tolist(),previous_q=q.tolist(),final_q=p.tolist(),actual_proxy_norm=norm(s),
        source_proxy_norm=denominator,actual_proxy_ratio=cost,prediction_errors=metrics,checks=checks,
        validated=all(checks.values()),reference_changed=False,accepted_material_step=False)


def positive_pair(values,uv):
    # 必须沿用扫描的差分运算顺序；零容忍负强度，不裁剪弱尾。
    with np.errstate(invalid='raise',over='raise',divide='raise'):
        q,p=wide.affine_pair(values,uv)
    if np.any(q<0) or np.any(p<0):raise ArithmeticError('negative predicted intensity')
    return q,p


def write_candidate(paths,destination,shape,uv,chunk=16):
    if len(paths)!=6:raise ValueError('six paired states required')
    states=wide.paired_streams(paths,shape)
    if destination.exists():raise FileExistsError(destination)
    temporary=destination.with_suffix('.partial');minimum=float('inf')
    with temporary.open('xb') as f:
        for start in range(0,shape[0],chunk):
            reused.checkpoint();stop=min(start+chunk,shape[0])
            q,_=positive_pair(wide.read_slab(states,start,stop),uv)
            minimum=min(minimum,float(q.min()));q.tofile(f)
    if temporary.stat().st_size!=int(np.prod(shape))*8:raise RuntimeError('candidate size mismatch')
    os.replace(temporary,destination)
    return minimum


def ratio(a,b):
    if b==0:
        if a==0:return 0.
        raise ArithmeticError('nonzero change with zero scale')
    return a/b


def compare_fields(paths,shape,uv,chunk=16):
    """Compare all cells of the measured map with the affine predicted map."""
    # 六个同物质非连续配对态、新候选q、真实T(q)；重建候选逐位核对，再比较全场。
    if len(paths)!=8:raise ValueError("six paired basis states, candidate and mapped candidate required")
    states=[StreamState(p,shape) for p in paths];rows=[]
    err=scale=change=actual_scale=0.;err2=map2=change2=0.
    for start in range(0,shape[0],chunk):
        reused.checkpoint();stop=min(start+chunk,shape[0])
        *values,q,actual=[state[start:stop] for state in states]
        if not np.isfinite(actual).all() or np.any(actual<0):raise ArithmeticError('invalid actual intensity')
        expected,predicted=positive_pair(values,uv)
        if not np.array_equal(q,expected):raise RuntimeError("stored candidate differs from audited formula")
        with np.errstate(invalid='raise',over='raise',divide='raise'):
            delta=actual-predicted;res=actual-q
            e=float(np.max(np.abs(delta)));z=max(float(np.max(actual)),float(np.max(predicted)))
            r=float(np.max(np.abs(res)))
            err=max(err,e);scale=max(scale,z);change=max(change,r)
            actual_scale=max(actual_scale,float(np.max(actual)),float(np.max(q)))
            err2+=float(np.sum(delta*delta));map2+=float(np.sum(actual*actual));change2+=float(np.sum(res*res))
        rows.append({'start':start,'stop':stop,'error_max':e,'field_scale':z,'actual_change_max':r,
                     'error_relative_to_local_field':ratio(e,z),'actual_local_residual':ratio(r,max(z,float(np.max(q))))})
    return {'max_error_over_field':ratio(err,scale),'max_error_over_actual_change':ratio(err,change),
            'l2_error_over_actual_field':np.sqrt(ratio(err2,map2)),
            'l2_error_over_actual_change':np.sqrt(ratio(err2,change2)),
            'actual_global_residual':ratio(change,actual_scale),
            'slabs':rows,'full_intensity_prediction_error_evaluated':True}


def prepare(out):
    ev=ROOT/'handoff/evidence';scan=ROOT/SCAN;source=ROOT/SOURCE
    audit=pipeline.read(ev/'20260926-heating-projection-review.json')
    claims=v.audited_inputs(scan,ev/'20260926-heating-projection-review.json',
        ev/'20260926-heating-projection-77531-terminal.json',77531,['status.json','declaration.json','prediction.json'])
    if pipeline.read(scan/'status.json')['status']!='complete_requires_review':raise RuntimeError('scan incomplete')
    prior=pipeline.read(scan/'declaration.json');prediction=pipeline.read(scan/'prediction.json')
    basis,source_claims,latest,proxy=probe.prepare()
    uv=select_candidate(prior,prediction,audit,basis,proxy)
    claims+=source_claims+prior['claims']+prior['code']
    claims+=v.audited_inputs(source,ev/'20260925-wide-validation-complete-review.json',
        ev/'20260925-wide-validation-77371-terminal.json',77371,
        ['control/pair11/previous_response.npz','control/pair11/final_response.npz'])
    template_root=ROOT/recovery.original.SOURCE
    claims+=v.audited_inputs(template_root,ev/'20260925-positive-validation-complete-review.json',
        ev/'20260925-positive-validation-77126-terminal.json',77126,['thermal/pair03/feedback_protocol.json'])
    finite=pipeline.read(template_root/'thermal/pair03/feedback_protocol.json')
    zero=pipeline.read(source/'control/pair11/feedback_protocol.json')
    s=zero['sources'];base=v.load_arrays(ROOT/s['outer_base_material']['path']);r=np.load(ROOT/s['base_residual']['path'],allow_pickle=False)
    old=v.load_arrays(ROOT/s['physical_old_time_level']['path']);trial=v.load_arrays(source/'control/trial_material.npz')
    fixed.exact_trial(trial,base,r,old,'control');fixed.same_trial(trial,base)
    q=[v.load_arrays(source/f'control/pair{n:02d}/{e}_feedback.npz')['half_atomic_rate_heating_erg_s_cm3']
       for n in (3,11) for e in ('previous','final')]
    book=v.load_arrays(source/'control/pair11/final_energy_ledger.npz')
    thermal=freeze_heating(q,book['remaining'],float(trial['step_duration_s']),trial['density_g_cm3'],old['cell_mass_g_cm2'],uv[1])
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(source/'control/trial_material.npz',inputs/'trial_material.npz')
    cfg=pipeline.read(source/'control/config.json');pipeline.write_json(inputs/'config.json',cfg)
    fixed.same_trial(v.load_arrays(inputs/'trial_material.npz'),trial)
    reused.immutable(inputs/'heating_reference.json',thermal)
    owned={'trial':pipeline.claim(inputs/'trial_material.npz'),'config':pipeline.claim(inputs/'config.json')}
    ret=pipeline.read(source/'control/endpoints-map11/manifest.json')
    preview=recovery.control_protocol(finite,zero,out/'control/pair02',ret['endpoints'],ret['history_rows'],owned['trial'],
        pipeline.claim(source/'control/endpoints-map11/manifest.json'),pipeline.claim(source/'declaration.json'))
    fixed.native_identity(preview)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/validate_step21_heating_projection.sbatch',
        'tests/test_validate_step21_heating_projection.py','handoff/protocols/step21-heating-validation-v1.md')]
    claims+=list(owned.values())+list(finite['sources'].values())+[pipeline.claim(inputs/'heating_reference.json')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases={'control':owned},claims=claims,code=code,selected='frozen-heating-projection',basis=basis,
        prediction=prediction,uv=uv,heating_reference=thermal,latest_actual_residual=latest,
        maximum_maps=LIMIT,maximum_feedback_pairs=2,cadence=[2,10],
        accepted_outer_steps=20,automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,
        source_scan=SCAN,source_control=SOURCE,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    previous={e:v.load_arrays(source/f'control/pair11/{e}_response.npz')['residual'] for e in ('previous','final')}
    return plan,finite,zero,base,r,old,previous


def map_once(folder,cfg,state):
    if len(state['history'])>=LIMIT:raise RuntimeError('ten-map hard limit')
    recovery.original.map_once(folder,cfg,state)


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('insufficient checkpoint space')
        plan,finite,zero,base,r,old,previous=prepare(out);origin={k:a.copy() for k,a in previous.items()}
        reused.LIMITS={'control':LIMIT};uv=np.asarray(plan['uv']);paths=[ROOT/c['path'] for c in plan['basis']]
        mark('writing_candidate');seedpath=out/'heating-projection-candidate.dat';minimum=write_candidate(paths,seedpath,pipeline.SHAPE,uv)
        reused.verify(plan['basis']);seed=pipeline.claim(seedpath);reports={}
        with fixed.relay_dispatch():
            folder,cfg,state=reused.child(out,'control','control',seed,plan)
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),base)
            for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
            def next_map(n):
                if len(state['history'])!=n-1:raise RuntimeError('map count differs')
                mark('mapping',completed_maps=n-1);map_once(folder,cfg,state)
            def validate():
                next_map(1);row=state['history'][0]
                if row['input_sha256']!=seed['sha256']:raise RuntimeError('candidate not mapped')
                fields=compare_fields(paths+[seedpath,ROOT/row['output_path']],pipeline.SHAPE,uv)
                np.testing.assert_allclose(fields['actual_global_residual'],row['residual'],rtol=1e-12,atol=0)
                checks=v.measured_checks(row,plan['latest_actual_residual'],fields)
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                result=dict(selected=plan['selected'],candidate=seed,minimum_candidate=minimum,effective_uv=uv.tolist(),actual_map=row,
                    field_comparison=fields,checks=checks,validated=all(checks.values()),parent_peak_rss_bytes=peak,accepted_material_step=False)
                reused.immutable(folder/'validation.json',result);reused.verify(plan['basis']);reused.archive(out,'true-map-validation')
                return result['validated']
            def feedback(n):
                nonlocal previous
                reused.checkpoint()
                if len(state['history'])!=n or not pipeline.pair_ready(state['history'],1e-4):
                    reports[str(n)]=dict(feedback_evaluated=False,inner_pair_ready=False);return False
                fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp);rd=folder/f'pair{n:02d}';rd.mkdir()
                p=recovery.control_protocol(finite,zero,rd,ret['endpoints'],ret['history_rows'],pipeline.claim(folder/'trial_material.npz'),
                    pipeline.claim(rp),pipeline.claim(out/'declaration.json'))
                p['sources']['heating_projection_validation']=pipeline.claim(folder/'validation.json')
                fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r,old,'control');fixed.native_identity(p)
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];pp=rd/'feedback_protocol.json';reused.immutable(pp,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',after_maps=n)
                with reused.feedback_stop_guard():stable=fixed.zero_feedback(rd,p,pp,state['history'][-2:])
                summary=pipeline.read(rd/'baseline_summary.json')
                if summary.get('material_response_failures'):raise RuntimeError('physical response rejected')
                vectors={e:v.load_arrays(rd/f'{e}_response.npz')['residual'] for e in ('previous','final')}
                report=dict(feedback_evaluated=True,zero_control_stable=stable,original_gates=summary['gate_checks'],
                    comparison_kind='post_extrapolation_shift' if n==2 else 'eight_map_drift',
                    window_comparison=recovery.original.window_comparison(vectors,previous,r,old['cell_mass_g_cm2']),
                    from_77371_comparison=recovery.original.window_comparison(vectors,origin,r,old['cell_mass_g_cm2']),
                    fresh_control_minus_r20_norms=asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2'])),
                    baseline_replaced=False,promoted=False)
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                if n==2:
                    if ret['endpoints']['previous']['sha256']!=seed['sha256'] or ret['endpoints']['final']['sha256']!=state['history'][0]['output_sha256']:
                        raise RuntimeError('first feedback is not q and T(q)')
                    fb=[v.load_arrays(rd/f'{e}_feedback.npz') for e in ('previous','final')]
                    emitted=v.load_arrays(ROOT/SOURCE/'control/pair11/final_feedback.npz')['emitted_power_erg_s_cm3']
                    if any(not np.array_equal(x['emitted_power_erg_s_cm3'],emitted) for x in fb):
                        raise RuntimeError('fixed emitted power changed')
                    thermal=heating_checks(plan['heating_reference'],*[x['half_atomic_rate_heating_erg_s_cm3'] for x in fb])
                    reused.immutable(rd/'heating_validation.json',thermal)
                    report['heating_validation']=thermal
                    stable=stable and thermal['validated']
                report['conditional_continuation_pass']=bool(stable)
                report['parent_peak_rss_bytes']=peak;reused.immutable(rd/'decision.json',report);reports[str(n)]=report;previous=vectors
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'control-map{n:02d}-feedback')
                return stable
            terminal=conditional_sequence(validate,next_map,feedback)
        reused.verify(plan['claims']+plan['code'])
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,accepted_outer_steps=20,new_material_steps=0,
            maps=len(state['history']),baseline_replaced=False,strict_error_bound=False))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,args.run))
