"""User-authorized tenfold response tolerance; fresh eight-map branches from audited 85889. Historical gates remain reported."""
import argparse,os,resource,shutil,signal,sys,time,subprocess
import numpy as np
from operations import x20_history_operator as core
from operations import calibrate_x20_radiation_histories as prior
ROOT,pipeline,reused,v,fresh=core.ROOT,core.pipeline,core.reused,core.v,core.fresh
fixed,old,directions=prior.fixed,prior.old,prior.directions
LIMITS=dict(accelerated=8,historical=8)
CADENCE=(8,)
NORMS=prior.NORMS


from operations.x20_85859_true_validation import checkout_identity,field_stats

SOURCE_JOBS=[76727,80195,82518,84026,85821,85856,85859,85861,85875,85889]
SOURCES={name:('outputs/hpc/x20-85875-matched-feedback-20261006',85889,
    '20261006-x20-85889-final-review.json','20261006-x20-85889-terminal.json') for name in LIMITS}
SEED_SHA=dict(accelerated='3f6c898f765e9854e378579f0f2fdc65fabe4def2f09d2a9554a4334d1a827b7',
    historical='6e10ec8904295909314a8cfa9022f541d0875209d4a42397d28e47728eed59eb')
R20_TOLERANCE=.01
SIGNAL_TOLERANCE=1.


def annotate(comparison):
    """新增探索性判据；保留旧门、全部四组合和原尺度，不改写历史结论。"""
    rows=comparison['frozen_r20']['vector_difference_over_frozen_r20_norms']
    signals=comparison['vector_difference_over_frozen_80195_signal']
    names=[a+'_vs_'+b for a in ('previous','final') for b in ('previous','final')]
    if list(rows)!=names or list(signals)!=names:raise ValueError('all ordered four endpoints required')
    for table in (rows,signals):
        for values in table.values():
            if len(values)!=3 or any(type(x) not in (float,int) or not np.isfinite(x) or x<0 for x in values):
                raise ValueError('three finite nonnegative ratios required')
    rp=all(x<R20_TOLERANCE for row in rows.values() for x in row)
    sp=all(x<SIGNAL_TOLERANCE for row in signals.values() for x in row)
    return dict(comparison,relaxed_response_consistency=dict(policy='user_20261007_tenfold_exploratory_v1',
        r20_tolerance=R20_TOLERANCE,signal_tolerance=SIGNAL_TOLERANCE,r20_pass=rp,signal_pass=sp,passed=rp and sp,
        exploratory_only=True,reference_calibration_eligible=False,strict_error_bound=False))


def vector_comparison(current,previous,r20,mass,scale):
    return annotate(prior.vector_comparison(current,previous,r20,mass,scale))


def compare_saved(vec,fb,origins,ref_fb,r20,mass,scales,gates):
    rates={a+'_vs_'+b:fresh.pair._feedback_stability_gate_checks(fresh.pair._feedback_stability_comparison(x,y),gates)
        for a,x in fb.items() for b,y in ref_fb.items()}
    return dict(residual_comparison=vector_comparison(vec,origins,r20,mass,scales),all_four_rate_gate_checks=rates,
        cross_rate_pass=all(all(g.values()) for g in rates.values()),saved_reference_job=85889,
        saved_reference_case='accelerated',saved_reference_map=16,reference_recomputed=False,strict_error_bound=False)


def require_source(audit,summary,name):
    if name not in LIMITS:raise ValueError('source branch')
    expected=dict(job_id=85889,completed_experiment=True,independent_vector_reduction=True,
        all_original_zero_gates_passed=True,accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,
        reference_calibration_eligible=False,map_process_receipts=2432,feedback_process_receipts=608,
        numerical_artifacts_complete=True,scheduler_terminal_verified=True,source_85821_scheduler_terminal_verified=True,
        source_85875_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,
        scheduler_terminal_state='COMPLETED',child_exit_status=0,numerical_commit='9555a78a77b9025e30405684dee2669d9e43baee')
    if any(type(audit.get(k)) is not type(v) or audit.get(k)!=v for k,v in expected.items()):
        raise ValueError('complete 85889 source provenance required')
    values=dict(maps=32,feedback_pair_count=4,accepted_outer_steps=20,new_material_steps=0,
        baseline_replaced=False,reference_calibration_eligible=False)
    if any(type(summary.get(k)) is not type(v) or summary.get(k)!=v for k,v in values.items()):raise ValueError('source summary')
    if summary['cases'][name]['16']['eight_map_window']['passed'] is not True:raise ValueError('source window identity')


def seed_claim(name,state,manifest):
    seed=core.retained_pair(state,manifest,16)[-1]
    expected=dict(path=SOURCES[name][0]+f'/{name}/endpoints-map16/mapped_final.dat',
        size_bytes=pipeline.STATE_BYTES,sha256=SEED_SHA[name])
    if seed!=expected:raise ValueError('seed must be the audited iteration16 real output')
    return seed


def sequence(evaluate):
    for n in CADENCE:
        for name in LIMITS:
            reason=evaluate(name,n)
            if reason!='pass':return f'stopped_at_{name}_map{n:02d}_{reason}'
    return 'paired_seed_windows_complete_requires_review'


def relaxed_consistency_pass(terminal,reports,cross):
    if terminal!='paired_seed_windows_complete_requires_review':return False
    if set(reports)!=set(LIMITS) or set(cross)!={'8'}:raise ValueError('incomplete paired experiment')
    for name in LIMITS:
        if set(reports[name])!={'8'}:raise ValueError('missing feedback window')
        for row in reports[name].values():
            if (not row['feedback_evaluated'] or not row['zero_pair_stable'] or row['physical_response_failures']
                or len(row['original_zero_gates'])!=7 or not all(row['original_zero_gates'].values())):return False
    return all(reports[name]['8']['eight_map_window']['relaxed_response_consistency']['passed'] for name in LIMITS) and cross['8']['residual_comparison']['relaxed_response_consistency']['passed'] and cross['8']['cross_rate_pass']


def map_once(folder,cfg,state,limit):
    """Same guarded map kernel, with this experiment's explicit 8-map limit."""
    reused.checkpoint()
    before=len(state['history'])
    if type(limit) is not int or limit!=8 or before>=limit:raise RuntimeError('eight-map hard limit')
    driver=old.recovery.original.driver
    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
    if state['status'] in driver.FAULT_STATUSES or len(state['history'])!=before+1 or state.get('active_map') is not None:raise RuntimeError('mapping fault or incomplete commit')
    paths=list((folder/f"map{len(state['history']):04d}").glob('block*.process-*.json'))
    if len(paths)!=76:raise RuntimeError('process receipt count')
    for path in paths:
        p=pipeline.read(path)
        if p['returncode'] or not p['memory_guard_passed'] or p['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')



def tracked_code():
    # 全部tracked Python/sbatch另冻结，旧物理协议和原核SHA不改。
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,text=True).split('\0')
    return [pipeline.claim(ROOT/name) for name in names if name.endswith(('.py','.sbatch'))]


def prepare(out):
    commit=checkout_identity();frozen_tracked=tracked_code();ev=ROOT/'handoff/evidence';claims=[];plans={};seeds={};cfgs={};trials={};origins={}
    for name,(relative,job,ap,tp) in SOURCES.items():
        src=ROOT/relative;summary=pipeline.read(src/'summary.json');audit=pipeline.read(ev/ap)
        require_source(audit,summary,name)
        terminal=pipeline.read(ev/tp)
        tokens=dict(t.split('=',1) for t in terminal['scontrol'].split() if '=' in t)
        if any(tokens.get(k)!=val for k,val in dict(JobId=str(job),JobState='COMPLETED',ExitCode='0:0').items()):
            raise ValueError('actual successful source scheduler receipt required')
        names=['declaration.json','summary.json']+[name+'/'+f for f in (
            'state.json','config.json','trial_material.npz','endpoints-map16/manifest.json','pair16/feedback_protocol.json',
            'pair16/previous_response.npz','pair16/final_response.npz','pair16/previous_feedback.npz','pair16/final_feedback.npz')]
        claims+=v.audited_inputs(src,ev/ap,ev/tp,job,names)
        plans[name]=pipeline.read(src/'declaration.json');claims+=plans[name]['claims']+plans[name]['code']
        state=pipeline.read(src/name/'state.json');cfgs[name]=pipeline.read(src/name/'config.json')
        if state['config_sha256']!=pipeline.sha256(src/name/'config.json'):raise ValueError('source configuration SHA')
        if cfgs[name]['maximum_maps']!=16:raise ValueError('source map budget changed')
        seeds[name]=seed_claim(name,state,pipeline.read(src/name/'endpoints-map16/manifest.json'))
        trials[name]=v.load_arrays(src/name/'trial_material.npz')
        origins[name]={e:v.load_arrays(src/name/f'pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    core.same_operator_config(cfgs['accelerated'],cfgs['historical'])
    fixed.same_trial(trials['accelerated'],trials['historical'])
    seed_stats=field_stats([ROOT/c['path'] for c in seeds.values()])
    current=ROOT/prior.CURRENT
    names=[f'{name}/pair10/{f}' for name in ('control','population') for f in ('feedback_protocol.json','previous_response.npz','final_response.npz')]
    claims+=v.audited_inputs(current,ev/'20260929-boundary-response-review.json',ev/'20260929-boundary-response-80195-terminal.json',80195,names)
    finite=pipeline.read(current/'population/pair10/feedback_protocol.json');zero=pipeline.read(current/'control/pair10/feedback_protocol.json');s=zero['sources']
    needed=[s[k] for k in ('outer_base_material','base_residual','physical_old_time_level')];reused.verify(needed)
    base=v.load_arrays(ROOT/needed[0]['path']);r20=np.load(ROOT/needed[1]['path'],allow_pickle=False);physical_old=v.load_arrays(ROOT/needed[2]['path'])
    for name,trial in trials.items():
        fixed.exact_trial(trial,base,r20,physical_old,'control')
        if int(trial['phase_index'])!=1367 or float(trial['step_duration_s'])!=889.419892762322:raise ValueError('phase or physical dt changed')
        native=prior.reused.audit_native_trial(cfgs[name],trial)
        if not native['native_mirrored_material_exact'] or not native['physical_phase_and_dt_exact']:raise ValueError('native identity')
    accepted=ROOT/prior.ACCEPTED/'confirm2'
    fixed.validate_base_against_accepted(base,v.load_arrays(accepted/'trial_material.npz'))
    if not np.array_equal(r20,v.load_arrays(accepted/'common-feedback/final_response.npz')['residual']):raise ValueError('frozen r20 changed')
    control={e:v.load_arrays(current/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    pop={e:v.load_arrays(current/f'population/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    mass=physical_old['cell_mass_g_cm2']
    scales=np.min([directions.norm_vector(p-c,mass) for p in pop.values() for c in control.values()],axis=0)
    for plan in plans.values():
        if not np.allclose(scales,[plan['frozen_signal_scale'][k] for k in NORMS],rtol=1e-12,atol=0):raise ValueError('original 80195 signal changed')
    inputs=out/'inputs';inputs.mkdir()
    shutil.copyfile(ROOT/SOURCES['accelerated'][0]/'accelerated/trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfgs['accelerated'])
    fixed.same_trial(trials['accelerated'],v.load_arrays(inputs/'trial_material.npz'))
    cases={'control':dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))}
    ref_fb={e:v.load_arrays(ROOT/SOURCES['accelerated'][0]/f'accelerated/pair16/{e}_feedback.npz') for e in ('previous','final')}
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/x20_85889_relaxed_feedback.sbatch',
        'tests/test_x20_85889_relaxed_feedback.py','handoff/protocols/x20-85889-relaxed-feedback-v1.md')]
    claims+=list(cases['control'].values())+list(seeds.values())+needed
    claims+=[pipeline.claim(p) for p in (accepted/'trial_material.npz',accepted/'common-feedback/final_response.npz')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    field_paths=sorted({c['path'] for c in claims if c['path'].endswith('.dat')})
    source_stats=field_stats([ROOT/p for p in field_paths]);reused.verify(claims+code)
    if field_stats([ROOT/p for p in field_paths])!=source_stats:raise ValueError('source fields changed during SHA verification')
    if checkout_identity()!=commit or field_stats([ROOT/c['path'] for c in seeds.values()])!=seed_stats:raise ValueError('source or checkout changed during preparation')
    plan=dict(cases=cases,claims=claims,code=code,tracked_code=frozen_tracked,seeds=seeds,source_jobs=SOURCE_JOBS,
        source_85821_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,
        source_85875_scheduler_terminal_verified=True,source_85889_scheduler_terminal_verified=True,git_commit=commit,git_clean=True,seed_stats_before=seed_stats,source_field_stats_before=source_stats,
        maximum_maps=16,maximum_feedback_pairs=2,child_limits=LIMITS,cadence=list(CADENCE),case_order=list(LIMITS),
        accepted_outer_steps=20,new_material_steps=0,automatic_promotion=False,baseline_replacement_authorized=False,
        frozen_signal_scale=dict(zip(NORMS,scales.tolist())),signal_source='fresh reduction of original80195 four P-C full response vectors',
        prior_feedback_origins=dict(accelerated='85889 accelerated pair16',historical='85889 historical pair16'),
        matched_new_two_branch_experiment=True,reference_recomputed=True,reference_calibration_eligible=False,
        matching_scope='equal additional map budgets, not cumulative ages or independent random seeds',
        wall_limit_s=14400,minimum_free_fields=18,parent_worker_rss_limit_bytes=6*1024**3,
        window_r20_tolerance=.001,window_signal_tolerance=.1,relaxed_r20_tolerance=.01,relaxed_signal_tolerance=1.,
        policy="user_20261007_tenfold_exploratory_v1",first_window_cross_history_is_measurement_only=False,
        drift_failure_does_not_skip_other_matched_case=True,both_branches_identical_x20=True,physical_dt_changed=False,historical_failures_retained=True,
        environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan);reused.immutable(out/'seed-claims.json',seeds)
    return plan,finite,zero,base,r20,physical_old,origins,scales,ref_fb

def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0' or os.environ.get('SLURM_CPUS_PER_TASK')!='32':raise RuntimeError('32CPU allocation and hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<18*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained field budget')
        started=time.monotonic();plan,finite,zero,base,r20,physical_old,origins,scales,ref_fb=prepare(out)
        mass=physical_old['cell_mass_g_cm2'];reused.LIMITS=LIMITS.copy()
        children={};reports={name:{} for name in LIMITS};vectors={name:{} for name in LIMITS};feedbacks={name:{} for name in LIMITS};cross={}
        def advance(name,n):
            if name not in children:children[name]=reused.child(out,name,'control',plan['seeds'][name],plan)
            folder,cfg,state=children[name]
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),v.load_arrays(ROOT/plan['cases']['control']['trial']['path']))
            fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r20,physical_old,'control')
            if n not in CADENCE or n>LIMITS[name] or len(state['history'])>n:raise RuntimeError('map budget or order changed')
            while len(state['history'])<n:
                if time.monotonic()-started>=13500:raise reused.Stopped('bounded new job time exhausted')
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
            if time.monotonic()-started>=13500:raise reused.Stopped('bounded new job time exhausted before feedback')
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
                report['from_prior_feedback']=vector_comparison(vec,origins[name],r20,mass,scales)
                reason='pass'
                if n==8:
                    window=vector_comparison(vec,origins[name],r20,mass,scales)
                    report['eight_map_window']=window
                    # 窗口漂移失败记证据，但仍完成另一分支的同龄检查点。
                if name=='historical':
                    between=vector_comparison(vec,vectors['accelerated'][n],r20,mass,scales)
                    rates={a+'_vs_'+b:fresh.pair._feedback_stability_gate_checks(
                        fresh.pair._feedback_stability_comparison(x,y),p['acceptance_gates'])
                        for a,x in fb.items() for b,y in feedbacks['accelerated'][n].items()}
                    cross[str(n)]=dict(residual_comparison=between,all_four_rate_gate_checks=rates,
                        cross_rate_pass=all(all(g.values()) for g in rates.values()))
                    report['cross_history']=cross[str(n)]
                    report['vs_saved_reference']=compare_saved(vec,fb,origins['accelerated'],ref_fb,r20,mass,scales,p['acceptance_gates'])
                    # 两分支完成后统一判定；这里不因可测漂移而截断配对实验。
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
        if tracked_code()!=plan['tracked_code']:raise RuntimeError('tracked code changed')
        after=field_stats([ROOT/c['path'] for c in plan['seeds'].values()]);commit_after=checkout_identity()
        source_after=field_stats([ROOT/c['path'] for c in plan['source_field_stats_before']])
        if source_after!=plan['source_field_stats_before']:raise RuntimeError('source field metadata changed during run')
        if after!=plan['seed_stats_before'] or commit_after!=plan['git_commit']:raise RuntimeError('source or checkout changed during run')
        eligible=relaxed_consistency_pass(terminal,reports,cross)
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,cross_history=cross,maps=sum(counts.values()),map_counts=counts,
            seed_stats_after=after,source_field_stats_after=source_after,git_commit_after=commit_after,git_clean_after=True,all_hashes_verified_before_after=True,
            matched_new_two_branch_experiment=True,reference_recomputed=True,
            reference_calibration_eligible=False,relaxed_consistency_pass=eligible,exploratory_only=True,independent_review_required=True,accepted_outer_steps=20,new_material_steps=0,
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
