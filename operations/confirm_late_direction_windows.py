"""Prospective late-window diagnosis of frozen trials; no material promotion.

The initial 8-to-16 failures remain immutable. Local windows start at the
audited 16-map endpoint. Drift from the original 78594 seed is still reported,
and exceeding its old bound forbids a claim of continuous original stability.
"""
import argparse
import os
import resource
import shutil
import signal
import sys
import time
import numpy as np
from operations import remeasure_step21_directions as prior

station, pipeline, ROOT = prior.station, prior.pipeline, prior.ROOT
fixed, fresh, reused = prior.fixed, prior.fresh, prior.reused
SOURCE = 'outputs/hpc/step21-refreshed-directions-20260928'
NAMES = prior.NAMES
CADENCE = (8, 16)
LIMITS = {k:16 for k in NAMES}
AUDIT = 'handoff/evidence/20260928-refreshed-directions-complete-review.json'
TERMINAL = 'handoff/evidence/20260928-refreshed-directions-78950-terminal.json'


def validate_source(summary, audit, states, retained):
    if (summary['status'] != 'refreshed_direction_measurement_requires_review'
            or summary['maps'] != 48 or summary['accepted_outer_steps'] != 20
            or summary['new_material_steps'] != 0 or summary['baseline_replaced']
            or summary['strict_error_bound']):
        raise RuntimeError('source is not the completed diagnostic')
    if (audit['job_id'] != 78950 or not audit['final_summary_present']
            or audit['events'] != [[n,k] for n in (8,16) for k in NAMES]
            or audit['accepted_outer_steps'] != 20 or audit['new_material_steps'] != 0
            or audit['baseline_replaced'] or audit['strict_error_bound']):
        raise RuntimeError('complete independent audit missing')
    seeds = {}
    for k in NAMES:
        if len(audit['maps'][k]) != 16:
            raise RuntimeError('audited map count changed')
        for n in (8,16):
            a, s = audit['pairs'][f'{k}{n:02d}'], summary['cases'][k][str(n)]
            if (not s['feedback_evaluated'] or s['physical_response_failures']
                    or s['promoted'] or s['baseline_replaced']
                    or a['gate_checks'] != s['original_gates']):
                raise RuntimeError('source feedback identity or domain changed')
            if k == 'control':
                if (not s['control_pass'] or not a['control_pass']
                        or set(s['original_gates']) != station.ZERO_GATES
                        or not all(s['original_gates'].values())):
                    raise RuntimeError('source control not stable')
                for w in (a['window'],a['cumulative'],s['window_comparison'],s['from_78594_comparison']):
                    if not station.validate_window(w):raise RuntimeError('source control window failed')
            elif n == 16:
                for measure in (s['response_measurement'],a['response_measurement']):
                    # This experiment is justified by clear current endpoints
                    # but unresolved earlier-window persistence, not acceptance.
                    if (not measure['endpoint_signal_resolved'] or measure['eight_map_signal_persistent']
                            or measure['strict_error_bound'] or measure['exact_jacobian']):
                        raise RuntimeError('late-window rationale changed')
        state, ret = states[k], retained[k]
        rows = state['history']
        if (state['active_map'] is not None or len(rows) != 16
                or [r['iteration'] for r in rows] != list(range(1,17))
                or ret['history_rows'] != rows[-2:]
                or any(x['output_sha256'] != y['input_sha256'] for x,y in zip(rows,rows[1:]))):
            raise RuntimeError('source map chain changed')
        for e,row in zip(('previous','final'),rows[-2:]):
            if ret['endpoints'][e]['sha256'] != row['input_sha256']:
                raise RuntimeError('retained endpoint changed')
        seed = ret['endpoints']['mapped_final']
        if seed['sha256'] != rows[-1]['output_sha256'] or seed['size_bytes'] != pipeline.STATE_BYTES:
            raise RuntimeError('not the individual latest successor')
        seeds[k] = seed
    return seeds


def sequence(evaluate):
    """Stop on the first failed late diagnostic; never spend the next window."""
    for n in CADENCE:
        for name in NAMES:
            result = evaluate(name,n)
            if result != 'late_window_pass':
                return f'stopped_at_{name}_map{n:02d}_{result}'
    return 'late_direction_windows_complete_requires_review'


def control_decision(stable, window, cumulative, historical):
    # 新的局部窗口只诊断后期变化；历史累计超门必须保留，不能称全程稳定。
    history_pass = station.validate_window(historical)
    window_pass = station.validate_window(window)
    cumulative_pass = station.validate_window(cumulative)
    local_pass = window_pass and cumulative_pass
    return dict(control_pass=bool(stable and local_pass),
                historical_78594_cumulative_pass=history_pass,
                original_78594_cumulative_stability_claim=bool(stable and history_pass))


def direction_pass(window, cumulative):
    return all(m['endpoint_signal_resolved'] and m['eight_map_signal_persistent']
               for m in (window,cumulative))


def prepare(out):
    root = ROOT / SOURCE
    files = ['summary.json','declaration.json'] + [f'{k}/{f}' for k in NAMES for f in
        ('state.json','config.json','trial_material.npz','endpoints-map16/manifest.json',
         'pair16/feedback_protocol.json','pair16/previous_response.npz','pair16/final_response.npz',
         'pair16/decision.json')]
    claims = station.v.audited_inputs(root,ROOT/AUDIT,ROOT/TERMINAL,78950,files)
    states = {k:pipeline.read(root/k/'state.json') for k in NAMES}
    retained = {k:pipeline.read(root/k/'endpoints-map16/manifest.json') for k in NAMES}
    seeds = validate_source(pipeline.read(root/'summary.json'),pipeline.read(ROOT/AUDIT),states,retained)
    zero = pipeline.read(root/'control/pair16/feedback_protocol.json')
    finite = pipeline.read(root/'thermal/pair16/feedback_protocol.json')
    sources = zero['sources']
    base = fresh.load_arrays(ROOT/sources['outer_base_material']['path'])
    r = np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
    old = fresh.load_arrays(ROOT/sources['physical_old_time_level']['path'])
    accepted = ROOT / fixed.BASE
    fixed.validate_base_against_accepted(base,fresh.load_arrays(accepted/'trial_material.npz'))
    if not np.array_equal(r,fresh.load_arrays(accepted/'common-feedback/final_response.npz')['residual']):
        raise RuntimeError('original r20 changed')
    acceptance = ROOT/'handoff/evidence/20260924-accepted-step20.json'
    acceptance_terminal = ROOT/'handoff/evidence/20260924-confirmation20-76727-terminal.json'
    fixed.validate_acceptance(pipeline.read(acceptance),pipeline.read(acceptance_terminal))
    claims += [pipeline.claim(acceptance),pipeline.claim(acceptance_terminal)] + pipeline.read(acceptance)['claims']
    inputs=out/'inputs';inputs.mkdir();cases={};origins={}
    for k in NAMES:
        trial=fresh.load_arrays(root/k/'trial_material.npz');fixed.exact_trial(trial,base,r,old,k)
        cfg=pipeline.read(root/k/'config.json')
        if pipeline.sha256(root/k/'config.json') != states[k]['config_sha256']:
            raise RuntimeError('source config changed')
        folder=inputs/k;folder.mkdir();shutil.copyfile(root/k/'trial_material.npz',folder/'trial_material.npz')
        fixed.same_trial(fresh.load_arrays(folder/'trial_material.npz'),trial)
        pipeline.write_json(folder/'config.json',cfg)
        cases[k]=dict(trial=pipeline.claim(folder/'trial_material.npz'),config=pipeline.claim(folder/'config.json'))
        preview=prior.make_protocol(finite,zero,out/k/'pair08',retained[k],cases[k]['trial'],
            pipeline.claim(root/k/'endpoints-map16/manifest.json'),pipeline.claim(root/'declaration.json'),k)
        fixed.native_identity(preview)
        origins[k]={e:fresh.load_arrays(root/k/f'pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
        # 每个冻结候选继续自己的辐射后继态，避免交换种子重新引入松弛瞬态。
        claims+=list(cases[k].values())+[seeds[k]]
    historical_root=ROOT/prior.SOURCE
    historical={e:fresh.load_arrays(historical_root/f'control/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    claims+=[pipeline.claim(historical_root/f'control/pair16/{e}_response.npz') for e in ('previous','final')]
    parent=pipeline.read(root/'declaration.json');claims+=parent['claims']+parent['code']+list(sources.values())
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in
        ('operations/confirm_late_direction_windows.sbatch','tests/test_confirm_late_direction_windows.py',
         'handoff/protocols/step21-late-direction-windows-v1.md')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(source=SOURCE,source_job=78950,cases=cases,seeds=seeds,claims=claims,code=code,
        limits=LIMITS,cadence=list(CADENCE),source_maps_per_case=16,absolute_feedback_maps=[24,32],
        maximum_maps=48,maximum_feedback_pairs=6,case_order=list(NAMES),amplitudes=prior.directions.ALPHAS,
        control_window_tolerance=.001,signal_tolerance=.1,stop_on_first_failed_late_window=True,
        cumulative_anchor='78950 map16',matched_initial_radiation=False,own_successor_continuation=True,
        historical_78594_drift_reported=True,
        historical_78594_gate_controls_dispatch=False,old_8_to_16_verdicts_retained=True,
        accepted_outer_steps=20,automatic_promotion=False,baseline_replacement_authorized=False,
        physical_dt_changed=False,strict_error_bound=False,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    return plan,finite,zero,base,r,old,origins,historical


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):
        pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<36*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained disk budget')
        plan,finite,zero,base,r,old,origins,historical=prepare(out)
        reused.LIMITS=LIMITS.copy();children={};reports={k:{} for k in NAMES};controls={}
        first_signals={k:prior.response_measurement(origins[k],origins['control'],old['cell_mass_g_cm2'],1/256)[1] for k in NAMES[1:]}
        previous_signals={k:{e:v.copy() for e,v in first_signals[k].items()} for k in first_signals}
        previous_control=origins['control']
        def evaluate(name,n):
            nonlocal previous_control
            reused.checkpoint()
            if name not in children:children[name]=reused.child(out,name,name,plan['seeds'][name],plan)
            folder,cfg,state=children[name]
            fixed.same_trial(fresh.load_arrays(folder/'trial_material.npz'),fresh.load_arrays(ROOT/plan['cases'][name]['trial']['path']))
            while len(state['history'])<n:
                mark('mapping',case=name,completed_maps=len(state['history']),target_maps=n,absolute_target_maps=16+n)
                station.original.map_once(folder,cfg,state)
            if len(state['history'])!=n:raise RuntimeError('map counter changed')
            if not pipeline.pair_ready(state['history'],1e-4):
                reports[name][str(n)]=dict(feedback_evaluated=False,inner_pair_ready=False,promoted=False)
                reused.immutable(folder/f'inner-not-ready-map{n:02d}.json',reports[name][str(n)])
                reused.archive(out,f'{name}-map{n:02d}-inner-not-ready');return 'inner_not_ready'
            fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp)
            rd=folder/f'pair{n:02d}';rd.mkdir()
            p=prior.make_protocol(finite,zero,rd,ret,pipeline.claim(folder/'trial_material.npz'),pipeline.claim(rp),pipeline.claim(out/'declaration.json'),name)
            p['sources']['late_direction_declaration']=pipeline.claim(out/'declaration.json')
            fixed.exact_trial(fresh.load_arrays(folder/'trial_material.npz'),base,r,old,name);fixed.native_identity(p)
            fresh.attach_code(p);p['common_code_claims']+=plan['code'];pp=rd/'feedback_protocol.json';reused.immutable(pp,p)
            reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',case=name,after_maps=n,absolute_after_maps=16+n)
            with reused.feedback_stop_guard():
                if name=='control':
                    stable=fixed.zero_feedback(rd,p,pp,state['history'][-2:]);result=pipeline.read(rd/'baseline_summary.json')
                else:
                    result=fresh.pair.run_pair(pp,pipeline.sha256(pp));prior.directions.verify_step21_pair(rd,p,result)
            failures=result.get('material_response_failures',{})
            report=dict(feedback_evaluated=True,absolute_maps=16+n,original_gates=result['gate_checks'],physical_response_failures=failures,promoted=False,baseline_replaced=False)
            outcome='physical_domain_rejected'
            if not failures:
                vectors={e:fresh.load_arrays(rd/f'{e}_response.npz')['residual'] for e in ('previous','final')}
                if name=='control':
                    wc=station.original.window_comparison
                    window=wc(vectors,previous_control,r,old['cell_mass_g_cm2'])
                    total=wc(vectors,origins['control'],r,old['cell_mass_g_cm2'])
                    history=wc(vectors,historical,r,old['cell_mass_g_cm2'])
                    verdict=control_decision(stable,window,total,history)
                    report.update(zero_control_stable=stable,window_comparison=window,from_78950_map16_comparison=total,from_78594_comparison=history,**verdict)
                    controls[n]=vectors;previous_control=vectors;passed=verdict['control_pass']
                else:
                    measure,current=prior.response_measurement(vectors,controls[n],old['cell_mass_g_cm2'],1/256,previous_signals[name])
                    total,_=prior.response_measurement(vectors,controls[n],old['cell_mass_g_cm2'],1/256,first_signals[name])
                    np.savez(rd/'direction_response_vectors.npz',**current)
                    passed=direction_pass(measure,total);previous_signals[name]=current
                    report.update(response_measurement=measure,from_78950_map16_signal=total,late_direction_pass=passed,
                        fresh_baseline_comparison=prior.cross_comparisons(vectors,controls[n],old['cell_mass_g_cm2']),all_16_pair_gates=prior.all_pair_gates(result))
                outcome='late_window_pass' if passed else 'late_window_not_confirmed'
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            report['parent_peak_rss_bytes']=peak;reports[name][str(n)]=report
            reused.immutable(rd/'decision.json',report);reused.verify(list(p['sources'].values())+p['common_code_claims'])
            reused.archive(out,f'{name}-map{n:02d}-feedback');return outcome
        with fixed.relay_dispatch():terminal=sequence(evaluate)
        reused.verify(plan['claims']+plan['code'])
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,maps=sum(len(x[2]['history']) for x in children.values()),
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
            late_windows_only=True,old_8_to_16_verdicts_retained=True))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:
        mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:
        mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
