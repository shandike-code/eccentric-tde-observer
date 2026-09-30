"""Matched feedback windows from an audited accelerated seed and retained history.

No rebase or material acceptance; complete both matched windows unless a hard gate fails.
"""
import argparse,os,resource,shutil,signal,sys,time
import numpy as np
from operations import x20_history_operator as core
from operations import calibrate_x20_radiation_histories as prior
ROOT,pipeline,reused,v,fresh=core.ROOT,core.pipeline,core.reused,core.v,core.fresh
fixed,old,directions=prior.fixed,prior.old,prior.directions
LIMITS=dict(accelerated=16,historical=16)
CADENCE=(8,16)
NORMS=prior.NORMS


def require_validation(audit,summary):
    if (audit.get('job_id')!=81679 or not audit.get('true_maps_independently_validated')
        or not audit.get('independent_small_statistic_reduction') or audit.get('accepted_outer_steps')!=20
        or audit.get('new_material_steps')!=0 or audit.get('baseline_replaced') is not False
        or summary.get('status')!='true_maps_validated_requires_review' or summary.get('new_maps')!=2
        or summary.get('new_feedback_pairs')!=0 or summary.get('new_material_steps')!=0
        or not summary.get('validated') or summary.get('baseline_replaced') is not False):raise ValueError('reviewed true-map validation required')


def sequence(evaluate):
    for n in CADENCE:
        for name in LIMITS:
            reason=evaluate(name,n)
            if reason!='pass':return f'stopped_at_{name}_map{n:02d}_{reason}'
    return 'paired_seed_windows_complete_requires_review'


def calibration_eligible(terminal,reports,cross):
    if terminal!='paired_seed_windows_complete_requires_review':return False
    if set(reports)!=set(LIMITS) or set(cross)!={'8','16'}:raise ValueError('incomplete paired experiment')
    for name in LIMITS:
        if set(reports[name])!={'8','16'}:raise ValueError('missing feedback window')
        for row in reports[name].values():
            if (not row['feedback_evaluated'] or not row['zero_pair_stable'] or row['physical_response_failures']
                or len(row['original_zero_gates'])!=7 or not all(row['original_zero_gates'].values())):return False
    return all(reports[name]['16']['eight_map_window']['passed'] for name in LIMITS) and cross['16']['residual_comparison']['passed'] and cross['16']['cross_rate_pass']


def seed_claims(actual,full_state,history_state,retained):
    rows=full_state.get('history',[])
    if len(rows)!=1 or full_state.get('active_map') is not None or rows[0]!=actual['actual_maps']['full'] or full_state['current_sha256']!=rows[0]['output_sha256']:raise ValueError('unsettled actual full source')
    historical=core.retained_pair(history_state,retained,24)[-1]
    accelerated=dict(path=rows[0]['output_path'],size_bytes=pipeline.STATE_BYTES,sha256=rows[0]['output_sha256'])
    if historical['sha256']==accelerated['sha256']:raise ValueError('two distinct numerical seeds required')
    return dict(accelerated=accelerated,historical=historical)


def seed_operator_config(actual,history):
    if actual['maximum_maps']!=1 or history['maximum_maps']!=24:raise ValueError('unexpected source budgets')
    comparison=dict(actual);comparison['maximum_maps']=history['maximum_maps']
    core.same_operator_config(comparison,history)


def map_once(folder,cfg,state,limit):
    """Same guarded map kernel, with this experiment's explicit 16-map limit."""
    reused.checkpoint()
    before=len(state['history'])
    if limit!=16 or before>=limit:raise RuntimeError('sixteen-map hard limit')
    driver=old.recovery.original.driver
    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
    if state['status'] in driver.FAULT_STATUSES or len(state['history'])!=before+1 or state.get('active_map') is not None:raise RuntimeError('mapping fault or incomplete commit')
    paths=list((folder/f"map{len(state['history']):04d}").glob('block*.process-*.json'))
    if len(paths)!=76:raise RuntimeError('process receipt count')
    for path in paths:
        p=pipeline.read(path)
        if p['returncode'] or not p['memory_guard_passed'] or p['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')



def prepare(out):
    ev=ROOT/'handoff/evidence';validated=ROOT/'outputs/hpc/x20-expanded-validation-20260930';history=ROOT/core.SOURCE
    ap=ev/'20260930-x20-expanded-validation-review.json';tp=ev/'20260930-x20-expanded-81679-terminal.json'
    require_validation(pipeline.read(ap),pipeline.read(validated/'summary.json'))
    claims=v.audited_inputs(validated,ap,tp,81679,['declaration.json','summary.json','validation.json','candidate-claims.json','full/state.json','full/config.json','full/trial_material.npz'])
    pre=out/'source-preflight';pre.mkdir();source,geometry=core.prepare(pre,'scan')
    seed_operator_config(pipeline.read(validated/'full/config.json'),pipeline.read(history/'late/config.json'))
    seeds=seed_claims(pipeline.read(validated/'validation.json'),pipeline.read(validated/'full/state.json'),pipeline.read(history/'historical/state.json'),pipeline.read(history/'historical/endpoints-map24/manifest.json'))
    current=ROOT/prior.CURRENT
    names=[f'{name}/pair10/feedback_protocol.json' for name in ('control','population')]
    claims+=v.audited_inputs(current,ev/'20260929-boundary-response-review.json',ev/'20260929-boundary-response-80195-terminal.json',80195,names)
    finite=pipeline.read(current/'population/pair10/feedback_protocol.json');zero=pipeline.read(current/'control/pair10/feedback_protocol.json');s=zero['sources']
    base=v.load_arrays(ROOT/s['outer_base_material']['path']);r20=np.load(ROOT/s['base_residual']['path'],allow_pickle=False);physical_old=v.load_arrays(ROOT/s['physical_old_time_level']['path'])
    trial=v.load_arrays(ROOT/source['cases']['control']['trial']['path'])
    fixed.same_trial(trial,v.load_arrays(validated/'full/trial_material.npz'));fixed.exact_trial(trial,base,r20,physical_old,'control')
    accepted=ROOT/prior.ACCEPTED/'confirm2'
    fixed.validate_base_against_accepted(base,v.load_arrays(accepted/'trial_material.npz'))
    if not np.array_equal(r20,v.load_arrays(accepted/'common-feedback/final_response.npz')['residual']):raise RuntimeError('frozen r20 changed')
    origins={};oldplan=pipeline.read(history/'declaration.json')
    for name,child,n in [('accelerated','late',16),('historical','historical',24)]:
        files=[f'{child}/pair{n:02d}/{e}_response.npz' for e in ('previous','final')]
        claims+=v.audited_inputs(history,ev/'20260929-x20-history-review.json',ev/'20260929-x20-history-80554-terminal.json',80554,files)
        origins[name]={e:v.load_arrays(history/f'{child}/pair{n:02d}/{e}_response.npz')['residual'] for e in ('previous','final')}
    scales=np.array([oldplan['frozen_signal_scale'][k] for k in NORMS])
    prior.vector_comparison(origins['historical'],origins['historical'],r20,physical_old['cell_mass_g_cm2'],scales)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_accelerated_feedback_windows.sbatch','tests/test_x20_accelerated_feedback_windows.py','handoff/protocols/x20-accelerated-feedback-windows-v1.md')]
    claims+=source['claims']+source['code']+list(seeds.values())+[s[k] for k in ('outer_base_material','base_residual','physical_old_time_level')]+[pipeline.claim(p) for p in (accepted/'trial_material.npz',accepted/'common-feedback/final_response.npz',history/'declaration.json')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases=source['cases'],claims=claims,code=code,seeds=seeds,source_jobs=[76727,80195,80554,81679],
        maximum_maps=32,maximum_feedback_pairs=4,child_limits=LIMITS,cadence=list(CADENCE),case_order=list(LIMITS),
        accepted_outer_steps=20,new_material_steps=0,automatic_promotion=False,baseline_replacement_authorized=False,
        frozen_signal_scale=dict(zip(NORMS,scales.tolist())),signal_source='unchanged80554 minimum over80195 four P-C endpoints',
        prior_feedback_origins=dict(accelerated='80554 late pair16 (not feedback of accelerated seed)',historical='80554 historical pair24'),
        window_r20_tolerance=.001,window_signal_tolerance=.1,first_window_cross_history_is_measurement_only=True,
        drift_failure_does_not_skip_other_matched_case=True,both_branches_identical_x20=True,physical_dt_changed=False,historical_failures_retained=True,
        environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan);reused.immutable(out/'seed-claims.json',seeds)
    return plan,finite,zero,base,r20,physical_old,origins,scales

def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0' or os.environ.get('SLURM_CPUS_PER_TASK')!='32':raise RuntimeError('32CPU allocation and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<24*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained field budget')
        started=time.monotonic();plan,finite,zero,base,r20,physical_old,origins,scales=prepare(out)
        mass=physical_old['cell_mass_g_cm2'];reused.LIMITS=LIMITS.copy()
        children={};reports={name:{} for name in LIMITS};vectors={name:{} for name in LIMITS};feedbacks={name:{} for name in LIMITS};cross={}
        def advance(name,n):
            if name not in children:children[name]=reused.child(out,name,'control',plan['seeds'][name],plan)
            folder,cfg,state=children[name]
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),v.load_arrays(ROOT/plan['cases']['control']['trial']['path']))
            fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r20,physical_old,'control')
            if n not in CADENCE or n>LIMITS[name] or len(state['history'])>n:raise RuntimeError('map budget or order changed')
            while len(state['history'])<n:
                reused.checkpoint();mark('mapping',case=name,completed_maps=len(state['history']),target_maps=n)
                map_once(folder,cfg,state,LIMITS[name])
            return folder,cfg,state
        def evaluate(name,n):
            folder,cfg,state=advance(name,n);reused.checkpoint()
            if not pipeline.pair_ready(state['history'],1e-4):
                reports[name][str(n)]=dict(inner_pair_ready=False,feedback_evaluated=False)
                reused.immutable(folder/f'inner-not-ready-map{n:02d}.json',reports[name][str(n)])
                return 'inner_not_ready'
            fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp)
            rd=folder/f'pair{n:02d}';rd.mkdir()
            p=directions.make_protocol(finite,zero,rd,ret,pipeline.claim(folder/'trial_material.npz'),pipeline.claim(rp),pipeline.claim(out/'declaration.json'),'control')
            p['diagnostic_scope']=dict(same_state_seed_response_windows=True,radiation_history=name,baseline_replacement_authorized=False)
            fixed.native_identity(p);fresh.attach_code(p);p['common_code_claims']+=plan['code']
            pp=rd/'feedback_protocol.json';reused.immutable(pp,p);reused.verify(list(p['sources'].values())+p['common_code_claims'])
            mark('feedback',case=name,after_maps=n)
            with reused.feedback_stop_guard():stable=fixed.zero_feedback(rd,p,pp,state['history'][-2:])
            result=pipeline.read(rd/'baseline_summary.json');failures=result.get('material_response_failures',{})
            report=dict(feedback_evaluated=True,original_zero_gates=result['gate_checks'],physical_response_failures=failures,
                zero_pair_stable=stable,baseline_replaced=False,accepted_material_step=False)
            reason='physical_domain_rejected' if failures else 'zero_pair_gate_failed'
            if not failures and stable:
                vec={e:v.load_arrays(rd/f'{e}_response.npz')['residual'] for e in ('previous','final')}
                fb={e:v.load_arrays(rd/f'{e}_feedback.npz') for e in ('previous','final')}
                vectors[name][n]=vec;feedbacks[name][n]=fb
                report['from_prior_feedback']=prior.vector_comparison(vec,origins[name],r20,mass,scales)
                reason='pass'
                if n==16:
                    window=prior.vector_comparison(vec,vectors[name][8],r20,mass,scales)
                    report['eight_map_window']=window
                    # 窗口漂移失败记证据，但仍完成另一分支的同龄检查点。
                if name=='historical':
                    between=prior.vector_comparison(vec,vectors['accelerated'][n],r20,mass,scales)
                    rates={a+'_vs_'+b:fresh.pair._feedback_stability_gate_checks(
                        fresh.pair._feedback_stability_comparison(x,y),p['acceptance_gates'])
                        for a,x in fb.items() for b,y in feedbacks['accelerated'][n].items()}
                    cross[str(n)]=dict(residual_comparison=between,all_four_rate_gate_checks=rates,
                        cross_rate_pass=all(all(g.values()) for g in rates.values()))
                    report['cross_history']=cross[str(n)]
                    # 两分支完成后统一判定；这里不因可测漂移而截断配对实验。
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            report.update(parent_peak_rss_bytes=peak,continuation_pass=reason=='pass',reason=reason)
            reports[name][str(n)]=report;reused.immutable(rd/'decision.json',report)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'{name}-map{n:02d}-feedback')
            return reason
        with fixed.relay_dispatch():terminal=sequence(evaluate)
        counts={name:len(state['history']) for name,(_,_,state) in children.items()}
        if any(counts[n]>LIMITS[n] for n in counts) or sum(counts.values())>32:raise RuntimeError('final map budget exceeded')
        reused.verify(plan['claims']+plan['code'])
        eligible=calibration_eligible(terminal,reports,cross)
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,cross_history=cross,maps=sum(counts.values()),map_counts=counts,
            reference_calibration_eligible=eligible,independent_review_required=True,accepted_outer_steps=20,new_material_steps=0,
            baseline_replaced=False,strict_error_bound=False,historical_failures_retained=True,
            feedback_pair_count=sum(row.get('feedback_evaluated',False) for r in reports.values() for row in r.values()),wall_s=time.monotonic()-started,
            parent_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:
        mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:
        mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
