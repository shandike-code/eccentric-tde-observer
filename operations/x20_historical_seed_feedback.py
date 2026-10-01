"""New historical-seed feedback windows against an explicitly saved 82518 reference.

The reference is not newly evolved. No automatic calibration or material acceptance.
"""
import argparse,os,resource,shutil,signal,sys,time
import numpy as np
from operations import x20_history_operator as core
from operations import calibrate_x20_radiation_histories as prior
ROOT,pipeline,reused,v,fresh=core.ROOT,core.pipeline,core.reused,core.v,core.fresh
fixed,old,directions=prior.fixed,prior.old,prior.directions
LIMITS=dict(historical=16)
CADENCE=(8,16)
NORMS=prior.NORMS


def require_validation(audit,summary):
    expected={'full_l2_benefit','full_linf_nonincrease','half_l2_nonincrease','half_linf_nonincrease',
        'full_radiation','full_boundary_l1','full_boundary_bolometric','half_radiation','half_boundary_l1',
        'half_boundary_bolometric','independent_half_affinity','independent_half_linf_affinity',
        'full_l2_affinity','full_linf_affinity','half_l2_affinity','half_linf_affinity'}
    checks=audit.get('actual',{}).get('checks',{})
    if set(checks)!=expected or not all(v is True for v in checks.values()):raise ValueError('all sixteen independent true-map gates required')
    if (audit.get('job_id')!=82765 or not audit.get('true_maps_independently_validated')
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
    return 'historical_seed_windows_complete_requires_review'


def seed_claim(actual,full_state):
    rows=full_state.get('history',[])
    if (len(rows)!=1 or full_state.get('active_map') is not None
        or rows[0]!=actual['actual_maps']['full']
        or full_state['current_sha256']!=rows[0]['output_sha256']):
        raise ValueError('unsettled actual full source')
    return dict(path=rows[0]['output_path'],size_bytes=pipeline.STATE_BYTES,sha256=rows[0]['output_sha256'])


def require_saved_reference(audit,summary):
    if (audit.get('job_id')!=82518 or not audit.get('completed_experiment')
        or not audit.get('independent_vector_reduction') or not audit.get('all_original_zero_gates_passed')
        or audit.get('accepted_outer_steps')!=20 or audit.get('new_material_steps')!=0
        or audit.get('baseline_replaced') is not False or audit.get('reference_calibration_eligible') is not False
        or summary.get('maps')!=32 or summary.get('feedback_pair_count')!=4):
        raise ValueError('audited complete saved reference required')
    row=summary['cases']['accelerated']['16']
    if not row['eight_map_window']['passed']:
        raise ValueError('saved reference window was not stable')


def compare_saved(vec,fb,ref_vec,ref_fb,r20,mass,scales,acceptance_gates):
    rates={a+'_vs_'+b:fresh.pair._feedback_stability_gate_checks(
        fresh.pair._feedback_stability_comparison(x,y),acceptance_gates)
        for a,x in fb.items() for b,y in ref_fb.items()}
    return dict(residual_comparison=prior.vector_comparison(vec,ref_vec,r20,mass,scales),
        all_four_rate_gate_checks=rates,cross_rate_pass=all(all(g.values()) for g in rates.values()),
        saved_reference_job=82518,saved_reference_case='accelerated',saved_reference_map=16,
        reference_recomputed=False,strict_error_bound=False)


def seed_operator_config(actual,history):
    if actual['maximum_maps']!=1 or history['maximum_maps']!=16:raise ValueError('unexpected source budgets')
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
    ev=ROOT/'handoff/evidence'
    validated=ROOT/'outputs/hpc/x20-historical-half-validation-20261001'
    history=ROOT/'outputs/hpc/x20-global-window-feedback-20261001'
    ap=ev/'20261001-x20-historical-half-validation-82765-review.json';tp=ev/'20261001-x20-historical-half-validation-82765-terminal.json'
    audit=pipeline.read(ap);require_validation(audit,pipeline.read(validated/'summary.json'))
    if len(audit['actual']['checks'])!=16 or not all(audit['actual']['checks'].values()):raise ValueError('all sixteen actual checks required')
    names=['declaration.json','summary.json','validation.json','candidate-claims.json','full/state.json','full/config.json','full/trial_material.npz']
    claims=v.audited_inputs(validated,ap,tp,82765,names)
    ref_audit=pipeline.read(ev/'20261001-x20-82518-final-review.json')
    ref_summary=pipeline.read(history/'summary.json');require_saved_reference(ref_audit,ref_summary)
    names=['declaration.json','summary.json']+[f'{name}/{f}' for name in ('accelerated','historical') for f in
        ('state.json','config.json','trial_material.npz','endpoints-map16/manifest.json')]
    names += [f'{name}/pair{n:02d}/{f}' for name,n in [('accelerated',8),('accelerated',16),('historical',16)]
        for f in ('feedback_protocol.json','baseline_summary.json','decision.json','previous_response.npz','final_response.npz','previous_feedback.npz','final_feedback.npz')]
    claims+=v.audited_inputs(history,ev/'20261001-x20-82518-final-review.json',ev/'20261001-x20-82518-terminal.json',82518,names)
    actual=pipeline.read(validated/'validation.json');oldplan=pipeline.read(history/'declaration.json')
    validated_plan=pipeline.read(validated/'declaration.json')
    reused.verify(validated_plan['code']+oldplan['code'])
    full_state=pipeline.read(validated/'full/state.json')
    cfg=pipeline.read(validated/'full/config.json')
    if full_state['config_sha256']!=pipeline.sha256(validated/'full/config.json'):raise ValueError('source config hash')
    for name in ('accelerated','historical'):
        st=pipeline.read(history/name/'state.json')
        if st['config_sha256']!=pipeline.sha256(history/name/'config.json'):raise ValueError('saved config hash')
        seed_operator_config(cfg,pipeline.read(history/name/'config.json'))
        core.retained_pair(st,pipeline.read(history/name/'endpoints-map16/manifest.json'),16)
    seeds={'historical':seed_claim(actual,full_state)}
    if full_state['history'][0]!=audit['actual_maps']['full']:
        raise ValueError('true output differs from independent audit')
    if full_state['history'][0]['input_sha256']!=pipeline.read(validated/'candidate-claims.json')['full']['sha256']:raise ValueError('full candidate lineage')
    current=ROOT/prior.CURRENT
    names=[f'{name}/pair10/feedback_protocol.json' for name in ('control','population')]
    claims+=v.audited_inputs(current,ev/'20260929-boundary-response-review.json',ev/'20260929-boundary-response-80195-terminal.json',80195,names)
    finite=pipeline.read(current/'population/pair10/feedback_protocol.json');zero=pipeline.read(current/'control/pair10/feedback_protocol.json');s=zero['sources']
    needed=[s[k] for k in ('outer_base_material','base_residual','physical_old_time_level')];reused.verify(needed)
    base=v.load_arrays(ROOT/needed[0]['path']);r20=np.load(ROOT/needed[1]['path'],allow_pickle=False);physical_old=v.load_arrays(ROOT/needed[2]['path'])
    trial=v.load_arrays(validated/'full/trial_material.npz')
    for name in ('accelerated','historical'):
        fixed.same_trial(trial,v.load_arrays(history/name/'trial_material.npz'))
    fixed.exact_trial(trial,base,r20,physical_old,'control')
    if int(trial['phase_index'])!=1367 or float(trial['step_duration_s'])!=889.419892762322:raise ValueError('phase or physical dt changed')
    native=prior.reused.audit_native_trial(cfg,trial)
    if not native['native_mirrored_material_exact'] or not native['physical_phase_and_dt_exact']:raise ValueError('native identity')
    accepted=ROOT/prior.ACCEPTED/'confirm2'
    fixed.validate_base_against_accepted(base,v.load_arrays(accepted/'trial_material.npz'))
    if not np.array_equal(r20,v.load_arrays(accepted/'common-feedback/final_response.npz')['residual']):raise RuntimeError('frozen r20 changed')
    inputs=out/'inputs';inputs.mkdir()
    shutil.copyfile(validated/'full/trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfg)
    fixed.same_trial(trial,v.load_arrays(inputs/'trial_material.npz'))
    cases={'control':dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))}
    origins={name:{e:v.load_arrays(history/name/f'pair16/{e}_response.npz')['residual'] for e in ('previous','final')} for name in LIMITS}
    ref_vec={e:v.load_arrays(history/f'accelerated/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    ref_fb={e:v.load_arrays(history/f'accelerated/pair16/{e}_feedback.npz') for e in ('previous','final')}
    scales=np.array([oldplan['frozen_signal_scale'][k] for k in NORMS])
    prior.vector_comparison(origins['historical'],origins['historical'],r20,physical_old['cell_mass_g_cm2'],scales)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_historical_seed_feedback.sbatch','tests/test_x20_historical_seed_feedback.py','handoff/protocols/x20-historical-seed-feedback-v1.md')]
    claims+=validated_plan['claims']+validated_plan['code']+list(cases['control'].values())+list(seeds.values())+needed
    claims+=[pipeline.claim(p) for p in (accepted/'trial_material.npz',accepted/'common-feedback/final_response.npz')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases=cases,claims=claims,code=code,seeds=seeds,source_jobs=[76727,80195,82518,82765],
        maximum_maps=16,maximum_feedback_pairs=2,child_limits=LIMITS,cadence=list(CADENCE),case_order=list(LIMITS),
        accepted_outer_steps=20,new_material_steps=0,automatic_promotion=False,baseline_replacement_authorized=False,
        frozen_signal_scale=dict(zip(NORMS,scales.tolist())),signal_source='unchanged82273/81769/80554 minimum over80195 four P-C endpoints',
        prior_feedback_origins=dict(historical='82518 historical pair16, prior to candidate acceleration'),
        saved_reference=dict(job_id=82518,case='accelerated',map=16,new_maps=0,new_feedback_pairs=0,
            eight_map_window=ref_summary['cases']['accelerated']['16']['eight_map_window']),
        matched_new_two_branch_experiment=False,reference_calibration_eligible=False,
        window_r20_tolerance=.001,window_signal_tolerance=.1,first_window_cross_history_is_measurement_only=True,
        drift_failure_does_not_skip_second_window=True,saved_and_new_identical_x20=True,physical_dt_changed=False,historical_failures_retained=True,
        environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan);reused.immutable(out/'seed-claims.json',seeds)
    return plan,finite,zero,base,r20,physical_old,origins,scales,ref_vec,ref_fb

def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0' or os.environ.get('SLURM_CPUS_PER_TASK')!='32':raise RuntimeError('32CPU allocation and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<14*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained field budget')
        started=time.monotonic();plan,finite,zero,base,r20,physical_old,origins,scales,ref_vec,ref_fb=prepare(out)
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
            p['diagnostic_scope']=dict(same_state_seed_response_windows=True,saved_reference_job=82518,reference_recomputed=False,radiation_history=name,baseline_replacement_authorized=False)
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
                    # 新支16−8漂移与保存参考的差异分别报告，不冒充新双分支实验。
                cross[str(n)]=compare_saved(vec,fb,ref_vec,ref_fb,r20,mass,scales,p['acceptance_gates'])
                report['vs_saved_reference']=cross[str(n)]
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            report.update(parent_peak_rss_bytes=peak,continuation_pass=reason=='pass',reason=reason)
            reports[name][str(n)]=report;reused.immutable(rd/'decision.json',report)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'{name}-map{n:02d}-feedback')
            return reason
        with fixed.relay_dispatch():terminal=sequence(evaluate)
        counts={name:len(state['history']) for name,(_,_,state) in children.items()}
        if any(counts[n]>LIMITS[n] for n in counts) or sum(counts.values())>16:raise RuntimeError('final map budget exceeded')
        reused.verify(plan['claims']+plan['code'])
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,vs_saved_reference=cross,maps=sum(counts.values()),map_counts=counts,
            reference_calibration_eligible=False,matched_new_two_branch_experiment=False,reference_recomputed=False,independent_review_required=True,accepted_outer_steps=20,new_material_steps=0,
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
