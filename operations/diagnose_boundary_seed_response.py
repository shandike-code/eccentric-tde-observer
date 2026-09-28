"""Diagnostic-only material response from a rejected, independently audited radiation seed."""
import argparse,os,resource,shutil,signal,sys,time
import numpy as np
from operations import validate_boundary_constrained_global as foundation
ROOT,pipeline,fresh,fixed,reused,v=foundation.ROOT,foundation.pipeline,foundation.fresh,foundation.fixed,foundation.reused,foundation.v
old,directions,original_pilot=foundation.old,foundation.directions,foundation.original_pilot
signal_gate=foundation.signal_gate
SOURCE=foundation.SOURCE
REJECTED='outputs/hpc/step21-boundary-constrained-global-20260928'
LIMITS=dict(population=10,control=10)


CONTRACTION_GATES=frozenset(('candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass',
    'candidate_maximum_cell_contraction_pass'))
REQUIRED_GATES=frozenset(('last_two_photoionization_pass','last_two_total_recombination_pass',
    'last_two_atomic_heating_pass','last_two_direct_heating_pass','last_two_formal_heating_pass',
    'inner_noise_resolved_pass','two_formal_feedback_states_pass','two_inner_radiation_residuals_pass',
    'two_boundary_spectra_pass','two_boundary_bolometric_pass','candidate_state_bytes_pass',
    'population_nonnegative_pass','all_residual_components_finite_pass'))


def require_rejected_source(audit,summary,declaration,validation,state):
    expected=foundation.fields.checks(validation['field_comparison'],validation['prior_q_comparison'],
        declaration['source_row'],declaration['prior_q_row'],validation['actual_map'],validation['half_map'])
    if (audit.get('job_id')!=80052 or audit.get('accepted_outer_steps')!=20
        or audit.get('new_material_steps')!=0 or not audit.get('independent_slab_and_block_reduction')
        or audit.get('validated') is not False or validation.get('validated') is not False
        or expected!=audit.get('checks') or expected!=validation.get('checks') or len(expected)!=21
        or {k for k,v in expected.items() if not v}!={'prior_q_half_boundary_l1'}
        or summary.get('status')!='stopped_at_full_half_validation' or summary.get('maps')!=2
        or summary.get('new_material_steps')!=0 or state.get('active_map') is not None
        or state.get('history')!=[validation['actual_map']]
        or declaration.get('coefficients')!=dict(a=.4892755093069306,b=1.)):
        raise RuntimeError('requires exactly the audited rejected 80052 experiment')
    row=validation['actual_map'];candidate=validation['candidate']
    seed=dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES)
    if (row['input_sha256']!=candidate['sha256'] or state['current_sha256']!=seed['sha256']
        or state['slots'][state['current_slot']]!=seed['path']):
        raise RuntimeError('settled mapped seed identity changed')
    return seed


def diagnostic_gate_report(gates):
    # 收缩三门只允许诊断测量继续，仍逐项保存为失败；其余13门任一失败均停止。
    if set(gates)!=REQUIRED_GATES|CONTRACTION_GATES or any(type(v) is not bool for v in gates.values()):
        raise RuntimeError('incomplete or invalid original sixteen-gate report')
    failures=[k for k in sorted(REQUIRED_GATES) if not gates[k]]
    return dict(diagnostic_only=True,required_gate_failures=failures,
        contraction_gate_failures=[k for k in sorted(CONTRACTION_GATES) if not gates[k]],
        may_continue_diagnostic=not failures,original_all_16_pass=all(gates.values()),
        accepted_material_step=False,historical_acceleration_veto_retained=True)


def sequence(evaluate):
    for name,n in [('control',2),('population',2),('control',10),('population',10)]:
        reason=evaluate(name,n)
        if reason!='pass':return f'diagnostic_{name}_map{n:02d}_{reason}'
    return 'diagnostic_response_windows_complete_requires_review'


def prepare(out):
    ev=ROOT/'handoff/evidence';rejected=ROOT/REJECTED;source=ROOT/SOURCE
    ap=ev/'20260928-boundary-global-review.json';tp=ev/'20260928-boundary-global-80052-terminal.json'
    files=['declaration.json','summary.json','population/validation.json','population/state.json',
           'population/config.json','population/trial_material.npz']
    claims=v.audited_inputs(rejected,ap,tp,80052,files)
    prior=pipeline.read(rejected/'declaration.json');val=pipeline.read(rejected/'population/validation.json')
    seed=require_rejected_source(pipeline.read(ap),pipeline.read(rejected/'summary.json'),prior,val,
        pipeline.read(rejected/'population/state.json'))
    claims+=prior['claims']+prior['code']+[seed,val['candidate']]
    names=['declaration.json','summary.json']+[f'{name}/{file}' for name in ('control','population') for file in
        ('state.json','config.json','trial_material.npz','endpoints-map08/manifest.json','pair08/feedback_protocol.json',
         'pair08/previous_response.npz','pair08/final_response.npz')]
    claims+=v.audited_inputs(source,ev/'20260928-late-direction-complete-review.json',
        ev/'20260928-late-direction-79151-terminal.json',79151,names)
    fixed.same_trial(v.load_arrays(rejected/'population/trial_material.npz'),v.load_arrays(source/'population/trial_material.npz'))
    finite=pipeline.read(source/'population/pair08/feedback_protocol.json')
    zero=pipeline.read(source/'control/pair08/feedback_protocol.json');sources=finite['sources']
    base=v.load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
    physical_old=v.load_arrays(ROOT/sources['physical_old_time_level']['path'])
    fixed.validate_base_against_accepted(base,v.load_arrays(ROOT/fixed.BASE/'trial_material.npz'))
    if not np.array_equal(r,v.load_arrays(ROOT/fixed.BASE/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    inputs=out/'inputs';inputs.mkdir();cases={};origins={}
    for name in ('control','population'):
        trial=v.load_arrays(source/name/'trial_material.npz');fixed.exact_trial(trial,base,r,physical_old,name)
        folder=inputs/name;folder.mkdir();shutil.copyfile(source/name/'trial_material.npz',folder/'trial_material.npz')
        cfg=pipeline.read(source/name/'config.json')
        if pipeline.sha256(source/name/'config.json')!=pipeline.read(source/name/'state.json')['config_sha256']:raise RuntimeError('config changed')
        pipeline.write_json(folder/'config.json',cfg);fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),trial)
        cases[name]=dict(trial=pipeline.claim(folder/'trial_material.npz'),config=pipeline.claim(folder/'config.json'))
        own=pipeline.read(source/name/'endpoints-map08/manifest.json')
        preview=directions.make_protocol(finite,zero,out/name/'pair02',own,cases[name]['trial'],
            pipeline.claim(source/name/'endpoints-map08/manifest.json'),pipeline.claim(source/'declaration.json'),name)
        fixed.native_identity(preview)
        origins[name]={e:v.load_arrays(source/name/f'pair08/{e}_response.npz')['residual'] for e in ('previous','final')}
        claims+=list(cases[name].values())
    cs=pipeline.read(source/'control/state.json');cr=pipeline.read(source/'control/endpoints-map08/manifest.json')
    _,control_seed=original_pilot.settled_pair(cs,cr)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/diagnose_boundary_seed_response.sbatch',
        'tests/test_boundary_seed_response.py','handoff/protocols/boundary-seed-response-diagnostic-v1.md')]
    claims+=[control_seed]+list(finite['sources'].values())
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases=cases,claims=claims,code=code,source=SOURCE,source_job=79151,
        rejected_source=REJECTED,rejected_job=80052,rejected_source_checks=val['checks'],
        rejected_source_validated=False,historical_acceleration_veto_retained=True,
        population_seed=seed,control_seed=control_seed,coefficients=prior['coefficients'],
        diagnostic_only=True,child_limits=LIMITS,maximum_maps=20,maximum_feedback_pairs=4,cadence=[2,10],
        accepted_outer_steps=20,automatic_promotion=False,baseline_replacement_authorized=False,
        physical_dt_changed=False,matched_initial_radiation=False,first_pair_shift_is_not_stability=True,
        signal_tolerance=.1,control_window_tolerance=.001,required_feedback_gates=sorted(REQUIRED_GATES),
        diagnostic_contraction_gates=sorted(CONTRACTION_GATES),
        frozen_historical_failures_retained=True,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    return plan,finite,zero,base,r,physical_old,origins


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<32*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained field budget')
        plan,finite,zero,base,r,physical_old,origins=prepare(out)
        reused.LIMITS=LIMITS.copy();children={};reports={name:{} for name in ('control','population')};controls={}
        previous_control=origins['control'];previous_signals=None;mass=physical_old['cell_mass_g_cm2']
        _,original_signals=directions.response_measurement(origins['population'],origins['control'],mass,1/256)
        # T(z)只是数值种子；新两张连续map重新提供反馈端点的辐射与边界证明。
        seeds={'population':plan['population_seed'],'control':plan['control_seed']}
        reused.immutable(out/'seed-claims.json',seeds);reused.verify(list(seeds.values()))
        def child(name):
            label=name
            if name not in children:children[name]=reused.child(out,name,label,seeds[name],plan)
            folder,cfg,state=children[name]
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),v.load_arrays(ROOT/plan['cases'][label]['trial']['path']))
            fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r,physical_old,label)
            return folder,cfg,state
        def advance(name,n):
            folder,cfg,state=child(name)
            if n>LIMITS[name] or len(state['history'])>n:raise RuntimeError('map budget or order changed')
            while len(state['history'])<n:
                reused.checkpoint();mark('mapping',case=name,completed_maps=len(state['history']),target_maps=n)
                old.recovery.original.map_once(folder,cfg,state)
            return folder,cfg,state
        def evaluate(name,n):
            nonlocal previous_control,previous_signals
            folder,cfg,state=advance(name,n);reused.checkpoint()
            if not pipeline.pair_ready(state['history'],1e-4):
                reports[name][str(n)]=dict(feedback_evaluated=False,inner_pair_ready=False,promoted=False)
                reused.immutable(folder/f'inner-not-ready-map{n:02d}.json',reports[name][str(n)])
                return 'inner_not_ready'
            fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp);rd=folder/f'pair{n:02d}';rd.mkdir()
            p=directions.make_protocol(finite,zero,rd,ret,pipeline.claim(folder/'trial_material.npz'),pipeline.claim(rp),pipeline.claim(out/'declaration.json'),name)
            p['sources']['rejected_seed_validation']=pipeline.claim(ROOT/REJECTED/'population/validation.json')
            p['diagnostic_scope']=dict(diagnostic_only=True,historical_acceleration_veto_retained=True,automatic_promotion=False)
            fixed.native_identity(p);fresh.attach_code(p);p['common_code_claims']+=plan['code']
            pp=rd/'feedback_protocol.json';reused.immutable(pp,p);reused.verify(list(p['sources'].values())+p['common_code_claims'])
            mark('feedback',case=name,after_maps=n)
            with reused.feedback_stop_guard():
                if name=='control':
                    stable=fixed.zero_feedback(rd,p,pp,state['history'][-2:]);result=pipeline.read(rd/'baseline_summary.json')
                else:
                    result=fresh.pair.run_pair(pp,pipeline.sha256(pp));directions.directions.verify_step21_pair(rd,p,result)
            failures=result.get('material_response_failures',{})
            report=dict(diagnostic_only=True,historical_acceleration_veto_retained=True,feedback_evaluated=True,original_gates=result['gate_checks'],physical_response_failures=failures,promoted=False,baseline_replaced=False)
            reason='physical_domain_rejected'
            if not failures:
                vectors={e:v.load_arrays(rd/f'{e}_response.npz')['residual'] for e in ('previous','final')}
                if name=='control':
                    wc=old.recovery.original.window_comparison
                    window=wc(vectors,previous_control,r,mass);total=wc(vectors,origins['control'],r,mass)
                    passed=stable and window['passed'] and total['passed']
                    report.update(control_pass=bool(passed),zero_control_stable=stable,window_comparison=window,from_79151_control_comparison=total)
                    controls[n]=vectors;previous_control=vectors
                else:
                    # 全512分量先作P-C再取范数；r20原验收分母和历史失败仍保留。
                    measure,signals=directions.response_measurement(vectors,controls[n],mass,1/256,previous_signals)
                    shift,_=directions.response_measurement(vectors,controls[n],mass,1/256,original_signals)
                    gate_report=diagnostic_gate_report(result['gate_checks'])
                    signal_pass=signal_gate(n,measure)
                    passed=signal_pass and gate_report['may_continue_diagnostic']
                    report['diagnostic_gate_report']=gate_report
                    report.update(response_measurement=measure,from_79151_signal_shift=shift,
                        comparison_kind='post_correction_shift_not_persistence' if n==2 else 'eight_map_signal_persistence',
                        signal_pass=signal_pass,fresh_baseline_comparison=directions.cross_comparisons(vectors,controls[n],mass),
                        all_16_pair_gates=all(result['gate_checks'].values()))
                    np.savez(rd/'direction_response_vectors.npz',**signals);previous_signals=signals
                reason='pass' if passed else 'window_not_confirmed'
                if name=='population' and not gate_report['may_continue_diagnostic']:
                    reason='required_feedback_gate_failed'
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            report.update(parent_peak_rss_bytes=peak,conditional_continuation_pass=reason=='pass')
            reports[name][str(n)]=report;reused.immutable(rd/'decision.json',report)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'{name}-map{n:02d}-feedback')
            return reason
        with fixed.relay_dispatch():terminal=sequence(evaluate)
        count={name:len(st['history']) for name,(_,_,st) in children.items()}
        if any(count[n]>LIMITS[n] for n in count) or sum(count.values())>20:raise RuntimeError('final map budget exceeded')
        reused.verify(plan['claims']+plan['code']+list(seeds.values()))
        reused.immutable(out/'summary.json',dict(status=terminal,diagnostic_only=True,historical_acceleration_veto_retained=True,cases=reports,map_counts=count,maps=sum(count.values()),
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
            frozen_historical_failures_retained=True))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:
        mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:
        mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
