"""Actual validation of the audited boundary-constrained candidate, then bounded feedback."""
import argparse,os,resource,shutil,signal,sys,time
import numpy as np
from operations import validate_population_defect_global as foundation
from operations import boundary_constrained_global_fields as fields
ROOT,pipeline,fresh,fixed,reused,v=foundation.ROOT,foundation.pipeline,foundation.fresh,foundation.fixed,foundation.reused,foundation.v
old,directions,original_pilot=foundation.old,foundation.directions,foundation.original_pilot
sequence,signal_gate=foundation.sequence,foundation.signal_gate
SOURCE=foundation.SOURCE
PROPOSAL='outputs/hpc/step21-boundary-constrained-proposal-20260928'
LIMITS=dict(population=10,half=1,control=10)


def require_proposal(audit,summary):
    if (audit.get('job_id')!=80005 or audit.get('source_job_id')!=79878
        or audit.get('accepted_outer_steps')!=20 or audit.get('new_material_steps')!=0
        or not audit.get('all_predicted_checks_passed') or not audit.get('independent_small_statistic_reduction')
        or not audit.get('actual_map_required') or summary.get('status')!='complete_requires_review'
        or not summary.get('source_unchanged') or not summary.get('all_predicted_checks_passed')
        or summary.get('new_maps')!=0 or summary.get('new_feedback_pairs')!=0
        or summary.get('production_candidate_written') or summary.get('operator_recomputed')):
        raise RuntimeError('independently reviewed zero-map proposal required')
    a,b=(audit['coefficients'][k] for k in ('a','b'))
    if not 0<=a<=1 or not 0<=b<=1:raise ValueError('coefficient outside box')
    if any(summary['coefficients'][k]!=audit['coefficients'][k] for k in ('a','b')):raise RuntimeError('coefficient identity changed')
    return a,b


def prepare(out):
    ev=ROOT/'handoff/evidence';proposal=ROOT/PROPOSAL;source=ROOT/SOURCE
    ap=ev/'20260928-boundary-proposal-independent-review.json';tp=ev/'20260928-boundary-proposal-80005-terminal.json'
    names=['declaration.json','summary.json','prediction.json','gram.json','status.json']
    claims=v.audited_inputs(proposal,ap,tp,80005,names)
    audit=pipeline.read(ap);summary=pipeline.read(proposal/'summary.json');a,b=require_proposal(audit,summary)
    pd=pipeline.read(proposal/'declaration.json');pairs=pd['field_pairs']
    if len(pairs)!=6 or pd['half_anchor']!='original 79151 x' or pd['maximum_field_scans']!=2:raise RuntimeError('proposal declaration changed')
    claims+=pd['claims']+pd['code']+pairs
    names=['declaration.json','summary.json']+[f'{name}/{file}' for name in ('control','population') for file in
        ('state.json','config.json','trial_material.npz','endpoints-map08/manifest.json','pair08/feedback_protocol.json',
         'pair08/previous_response.npz','pair08/final_response.npz')]
    claims+=v.audited_inputs(source,ev/'20260928-late-direction-complete-review.json',
        ev/'20260928-late-direction-79151-terminal.json',79151,names)
    state=pipeline.read(source/'population/state.json');ret=pipeline.read(source/'population/endpoints-map08/manifest.json')
    if pairs[:2]!=list(original_pilot.settled_pair(state,ret)):raise RuntimeError('original actual map pair changed')
    previous=ROOT/'outputs/hpc/step21-population-defect-global-20260928'
    claims+=v.audited_inputs(previous,ev/'20260928-population-defect-global-review.json',
        ev/'20260928-population-defect-global-79878-terminal.json',79878,
        ['declaration.json','summary.json','population/validation.json','population/state.json','population/trial_material.npz'])
    prior=pipeline.read(previous/'declaration.json');pv=pipeline.read(previous/'population/validation.json');row=pv['actual_map']
    if pairs[2:4]!=prior['source_pair'] or pairs[4:]!=[pv['candidate'],dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES)]:
        raise RuntimeError('measured direction lineage changed')
    fixed.same_trial(v.load_arrays(previous/'population/trial_material.npz'),v.load_arrays(source/'population/trial_material.npz'))
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
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/validate_boundary_constrained_global.sbatch',
        'tests/test_boundary_constrained_global.py','handoff/protocols/boundary-constrained-global-v1.md')]
    claims+=[control_seed]+list(finite['sources'].values())
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases=cases,claims=claims,code=code,source=SOURCE,source_job=79151,proposal=PROPOSAL,proposal_job=80005,
        source_pair=pairs[:2],source_row=state['history'][-1],prior_q_pair=pairs[2:4],prior_q_row=prior['source_row'],
        field_pairs=pairs,coefficients=dict(a=a,b=b),control_seed=control_seed,
        half_anchor='original 79151 x',both_references_must_pass=True,
        selected_blocks=list(range(20,48)),gates=fields.GATES,child_limits=LIMITS,
        maximum_maps=21,maximum_feedback_pairs=4,cadence=[2,10],accepted_outer_steps=20,
        automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,
        matched_initial_radiation=False,first_pair_shift_is_not_stability=True,signal_tolerance=.1,control_window_tolerance=.001,
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
        if shutil.disk_usage(out).free<40*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained field budget')
        plan,finite,zero,base,r,physical_old,origins=prepare(out)
        reused.LIMITS=LIMITS.copy();children={};reports={name:{} for name in ('control','population')};controls={}
        previous_control=origins['control'];previous_signals=None;mass=physical_old['cell_mass_g_cm2']
        _,original_signals=directions.response_measurement(origins['population'],origins['control'],mass,1/256)
        mark('writing_candidates');full=out/'full-candidate.dat';half=out/'half-candidate.dat'
        paths=[ROOT/c['path'] for c in plan['source_pair']]
        # 只改辐射初值，population/half始终使用布居候选物质；control使用自身物质。
        fields.write_candidates([ROOT/plan['field_pairs'][i]['path'] for i in (0,2,4)],full,half,pipeline.SHAPE,
            plan['coefficients']['a'],plan['coefficients']['b'],reused.checkpoint)
        seeds={'population':pipeline.claim(full),'half':pipeline.claim(half),'control':plan['control_seed']}
        reused.immutable(out/'candidate-claims.json',seeds);reused.verify(plan['field_pairs'])
        def child(name):
            label='population' if name=='half' else name
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
        def validate():
            folder,cfg,state=advance('population',1);hf,hcfg,hs=advance('half',1)
            row,hrow=state['history'][0],hs['history'][0]
            if row['input_sha256']!=seeds['population']['sha256'] or hrow['input_sha256']!=seeds['half']['sha256']:raise RuntimeError('wrong mapped candidates')
            comparison,prior_q_comparison=fields.validate(paths+[full,ROOT/row['output_path'],half,ROOT/hrow['output_path']],
                [ROOT/c['path'] for c in plan['prior_q_pair']],pipeline.SHAPE,reused.checkpoint)
            checks=fields.checks(comparison,prior_q_comparison,plan['source_row'],plan['prior_q_row'],row,hrow)
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            result=dict(source_pair=plan['source_pair'],candidate=seeds['population'],half_candidate=seeds['half'],
                actual_map=row,half_map=hrow,field_comparison=comparison,prior_q_comparison=prior_q_comparison,
                prior_q_pair=plan['prior_q_pair'],half_anchor=plan['half_anchor'],checks=checks,validated=all(checks.values()),
                parent_peak_rss_bytes=peak,frozen_material_case='population',accepted_material_step=False)
            reused.verify(plan['source_pair']+plan['prior_q_pair']+list(seeds.values()))
            reused.immutable(folder/'validation.json',result);reused.archive(out,'full-half-validation')
            return result['validated']
        def evaluate(name,n):
            nonlocal previous_control,previous_signals
            folder,cfg,state=advance(name,n);reused.checkpoint()
            if not pipeline.pair_ready(state['history'],1e-4):
                reports[name][str(n)]=dict(feedback_evaluated=False,inner_pair_ready=False,promoted=False)
                reused.immutable(folder/f'inner-not-ready-map{n:02d}.json',reports[name][str(n)])
                return 'inner_not_ready'
            fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp);rd=folder/f'pair{n:02d}';rd.mkdir()
            p=directions.make_protocol(finite,zero,rd,ret,pipeline.claim(folder/'trial_material.npz'),pipeline.claim(rp),pipeline.claim(out/'declaration.json'),name)
            p['sources']['population_global_validation']=pipeline.claim(out/'population/validation.json')
            fixed.native_identity(p);fresh.attach_code(p);p['common_code_claims']+=plan['code']
            pp=rd/'feedback_protocol.json';reused.immutable(pp,p);reused.verify(list(p['sources'].values())+p['common_code_claims'])
            mark('feedback',case=name,after_maps=n)
            with reused.feedback_stop_guard():
                if name=='control':
                    stable=fixed.zero_feedback(rd,p,pp,state['history'][-2:]);result=pipeline.read(rd/'baseline_summary.json')
                else:
                    result=fresh.pair.run_pair(pp,pipeline.sha256(pp));directions.directions.verify_step21_pair(rd,p,result)
            failures=result.get('material_response_failures',{})
            report=dict(feedback_evaluated=True,original_gates=result['gate_checks'],physical_response_failures=failures,promoted=False,baseline_replaced=False)
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
                    passed=signal_gate(n,measure)
                    report.update(response_measurement=measure,from_79151_signal_shift=shift,
                        comparison_kind='post_correction_shift_not_persistence' if n==2 else 'eight_map_signal_persistence',
                        signal_pass=passed,fresh_baseline_comparison=directions.cross_comparisons(vectors,controls[n],mass),
                        all_16_pair_gates=all(result['gate_checks'].values()))
                    np.savez(rd/'direction_response_vectors.npz',**signals);previous_signals=signals
                reason='pass' if passed else 'window_not_confirmed'
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            report.update(parent_peak_rss_bytes=peak,conditional_continuation_pass=reason=='pass')
            reports[name][str(n)]=report;reused.immutable(rd/'decision.json',report)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'{name}-map{n:02d}-feedback')
            return reason
        with fixed.relay_dispatch():terminal=sequence(validate,evaluate)
        count={name:len(st['history']) for name,(_,_,st) in children.items()}
        if any(count[n]>LIMITS[n] for n in count) or sum(count.values())>21:raise RuntimeError('final map budget exceeded')
        reused.verify(plan['claims']+plan['code']+list(seeds.values()))
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,map_counts=count,maps=sum(count.values()),
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
