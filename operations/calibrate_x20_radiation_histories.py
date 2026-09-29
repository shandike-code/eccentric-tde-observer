"""Two radiation histories at identical x20; measure reference reproducibility, never rebase."""
import argparse,os,resource,shutil,signal,sys,time
import numpy as np
from operations import replay_material_response_witnesses as witness
source=witness.source
ROOT,pipeline,reused,v,fresh=source.ROOT,source.pipeline,source.reused,source.v,source.fresh
fixed,old,directions=source.fixed,source.old,source.directions
CURRENT,ACCEPTED,REPLAY=witness.CURRENT,witness.ACCEPTED,witness.RUN
LIMITS=dict(historical=24,late=24)
CADENCE=(16,24)
NORMS=('l2','mass_weighted','maximum_cell')


def require_replay(audit,summary):
    if (audit.get('job_id')!=80542 or audit.get('all_ten_endpoints_bitwise_equal') is not True
        or audit.get('independent_array_comparison') is not True or audit.get('physical_state_x20_unchanged') is not True
        or audit.get('accepted_outer_steps')!=20 or audit.get('new_material_steps')!=0 or audit.get('baseline_replaced') is not False
        or summary.get('status')!='complete_requires_review' or summary.get('all_replays_passed') is not True
        or summary.get('new_maps')!=0 or summary.get('new_feedback_integrations')!=0 or summary.get('baseline_replaced') is not False):
        raise RuntimeError('independently reviewed material witness replay required')


def vector_comparison(current,previous,r20,mass,signal_scale):
    """All four endpoint differences, with two independently frozen scales."""
    # 必须先减完整512维向量；相同范数不意味着同一个物质响应。
    window=old.recovery.original.window_comparison(current,previous,r20,mass)
    scale=np.asarray(signal_scale,float)
    if scale.shape!=(3,) or not np.isfinite(scale).all() or np.any(scale<=0):raise ValueError('invalid frozen signal scale')
    rows={a+'_vs_'+b:(directions.norm_vector(x-y,mass)/scale).tolist()
        for a,x in current.items() for b,y in previous.items()}
    if not np.isfinite(list(rows.values())).all():raise ValueError('nonfinite signal comparison')
    passed=all(x<.1 for row in rows.values() for x in row)
    return dict(frozen_r20=window,vector_difference_over_frozen_80195_signal=rows,
        signal_tolerance=.1,signal_pass=passed,passed=window['passed'] and passed,
        strict_error_bound=False,baseline_replaced=False)


def sequence(evaluate):
    for name,n in [('historical',16),('late',16),('historical',24),('late',24)]:
        reason=evaluate(name,n)
        if reason!='pass':return f'stopped_at_{name}_map{n:02d}_{reason}'
    return 'reference_history_windows_complete_requires_review'


def source_seed(previous_protocol,current_state,retained):
    historical=previous_protocol['sources']['final_radiation']
    rows=current_state['history'];late=retained['endpoints']['mapped_final']
    if (current_state['active_map'] is not None or len(rows)!=10
        or [r['iteration'] for r in rows]!=list(range(1,11)) or retained['history_rows']!=rows[-2:]
        or any(a['output_sha256']!=b['input_sha256'] for a,b in zip(rows,rows[1:]))
        or late['sha256']!=rows[-1]['output_sha256'] or current_state['current_sha256']!=late['sha256']):
        raise RuntimeError('source must be settled and retained ten-map history')
    if historical['sha256']==late['sha256']:
        raise RuntimeError('expected distinct historical and settled ten-map radiation histories')
    if any(c['size_bytes']!=pipeline.STATE_BYTES for c in (historical,late)):raise RuntimeError('wrong seed size')
    return dict(historical=historical,late=late)


def map_once(folder,cfg,state,limit):
    """Same guarded map kernel, with this experiment's explicit 24-map limit."""
    reused.checkpoint()
    if limit!=24 or len(state['history'])>=limit:raise RuntimeError('twenty-four-map hard limit')
    driver=old.recovery.original.driver
    if not driver.run_one_map(folder,cfg,state,folder/'state.json'):raise reused.Stopped('partial map retained')
    if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('mapping fault')
    paths=list((folder/f"map{len(state['history']):04d}").glob('block*.process-*.json'))
    if len(paths)!=76:raise RuntimeError('process receipt count')
    for path in paths:
        p=pipeline.read(path)
        if p['returncode'] or not p['memory_guard_passed'] or p['native_observed_peak_kib']>=6*1024**2:raise RuntimeError('worker guard')


def prepare(out):
    ev=ROOT/'handoff/evidence';current=ROOT/CURRENT;accepted=ROOT/ACCEPTED;rp=ROOT/REPLAY
    ap=ev/'20260929-response-replay-review.json';tp=ev/'20260929-response-replay-80542-terminal.json'
    require_replay(pipeline.read(ap),pipeline.read(rp/'summary.json'))
    claims=v.audited_inputs(rp,ap,tp,80542,['declaration.json','summary.json'])
    rd=pipeline.read(rp/'declaration.json');claims+=rd['claims']+rd['code']
    witness.require_source(pipeline.read(ev/'20260929-boundary-response-review.json'))
    files=['declaration.json','summary.json','control/state.json','control/config.json','control/trial_material.npz',
           'control/endpoints-map10/manifest.json']+[f'{name}/pair10/{f}' for name in ('control','population') for f in
           ('feedback_protocol.json','previous_feedback.npz','final_feedback.npz','previous_response.npz','final_response.npz')]
    claims+=v.audited_inputs(current,ev/'20260929-boundary-response-review.json',ev/'20260929-boundary-response-80195-terminal.json',80195,files)
    # 旧协议与响应已在重放中按接受态归档逐字节核对；数值参考仍为原r20。
    historical_protocol=pipeline.read(accepted/'confirm2/common-feedback/feedback_protocol.json')
    finite=pipeline.read(current/'population/pair10/feedback_protocol.json');zero=pipeline.read(current/'control/pair10/feedback_protocol.json')
    s=zero['sources'];base=v.load_arrays(ROOT/s['outer_base_material']['path'])
    r20=np.load(ROOT/s['base_residual']['path'],allow_pickle=False);physical_old=v.load_arrays(ROOT/s['physical_old_time_level']['path'])
    trial=v.load_arrays(current/'control/trial_material.npz');fixed.exact_trial(trial,base,r20,physical_old,'control')
    fixed.validate_base_against_accepted(base,v.load_arrays(accepted/'confirm2/trial_material.npz'))
    if not np.array_equal(r20,v.load_arrays(accepted/'confirm2/common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    state=pipeline.read(current/'control/state.json');ret=pipeline.read(current/'control/endpoints-map10/manifest.json')
    seeds=source_seed(historical_protocol,state,ret)
    cfg=pipeline.read(current/'control/config.json')
    if pipeline.sha256(current/'control/config.json')!=state['config_sha256']:raise RuntimeError('source config changed')
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(current/'control/trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfg);fixed.same_trial(v.load_arrays(inputs/'trial_material.npz'),trial)
    cases={'control':dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))}
    origins={'historical':{e:v.load_arrays(accepted/f'confirm2/common-feedback/{e}_response.npz')['residual'] for e in ('previous','final')},
        'late':{e:v.load_arrays(current/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}}
    population={e:v.load_arrays(current/f'population/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    mass=physical_old['cell_mass_g_cm2']
    scales=np.min([directions.norm_vector(p-c,mass) for p in population.values() for c in origins['late'].values()],axis=0)
    vector_comparison(origins['late'],origins['late'],r20,mass,scales)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/calibrate_x20_radiation_histories.sbatch',
        'tests/test_calibrate_x20_histories.py','handoff/protocols/x20-radiation-history-calibration-v1.md')]
    claims+=list(cases['control'].values())+list(seeds.values())+list(s.values())+list(finite['sources'].values())
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases=cases,claims=claims,code=code,seeds=seeds,source_jobs=[76727,80195,80542],
        maximum_maps=48,maximum_feedback_pairs=4,child_limits=LIMITS,cadence=list(CADENCE),
        accepted_outer_steps=20,new_material_steps=0,automatic_promotion=False,baseline_replacement_authorized=False,
        frozen_signal_scale=dict(zip(NORMS,scales.tolist())),signal_source='80195 map10 minimum over all four P-C endpoints',
        window_r20_tolerance=.001,window_signal_tolerance=.1,first_window_cross_history_is_measurement_only=True,
        both_branches_identical_x20=True,physical_dt_changed=False,historical_failures_retained=True,
        environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan);reused.immutable(out/'seed-claims.json',seeds)
    return plan,finite,zero,base,r20,physical_old,origins,scales


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<32*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained field budget')
        plan,finite,zero,base,r20,physical_old,origins,scales=prepare(out)
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
            p['diagnostic_scope']=dict(same_state_history_calibration=True,radiation_history=name,baseline_replacement_authorized=False)
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
                report['from_own_source']=vector_comparison(vec,origins[name],r20,mass,scales)
                reason='pass'
                if n==24:
                    window=vector_comparison(vec,vectors[name][16],r20,mass,scales)
                    report['eight_map_window']=window
                    if not window['passed']:reason='eight_map_window_unresolved'
                if name=='late':
                    between=vector_comparison(vec,vectors['historical'][n],r20,mass,scales)
                    rates={a+'_vs_'+b:fresh.pair._feedback_stability_gate_checks(
                        fresh.pair._feedback_stability_comparison(x,y),p['acceptance_gates'])
                        for a,x in fb.items() for b,y in feedbacks['historical'][n].items()}
                    cross[str(n)]=dict(residual_comparison=between,all_four_rate_gate_checks=rates,
                        cross_rate_pass=all(all(g.values()) for g in rates.values()))
                    report['cross_history']=cross[str(n)]
                    if n==24 and (not between['passed'] or not cross[str(n)]['cross_rate_pass']):reason='cross_history_unresolved'
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            report.update(parent_peak_rss_bytes=peak,continuation_pass=reason=='pass',reason=reason)
            reports[name][str(n)]=report;reused.immutable(rd/'decision.json',report)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'{name}-map{n:02d}-feedback')
            return reason
        with fixed.relay_dispatch():terminal=sequence(evaluate)
        counts={name:len(state['history']) for name,(_,_,state) in children.items()}
        if any(counts[n]>LIMITS[n] for n in counts) or sum(counts.values())>48:raise RuntimeError('final map budget exceeded')
        reused.verify(plan['claims']+plan['code'])
        eligible=terminal=='reference_history_windows_complete_requires_review'
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,cross_history=cross,maps=sum(counts.values()),map_counts=counts,
            reference_calibration_eligible=eligible,independent_review_required=True,accepted_outer_steps=20,new_material_steps=0,
            baseline_replaced=False,strict_error_bound=False,historical_failures_retained=True))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:
        mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:
        mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
