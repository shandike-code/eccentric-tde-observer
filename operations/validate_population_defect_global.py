"""Full/half radiation validation, then bounded population/control feedback windows."""
import argparse
import os
import resource
import shutil
import signal
import sys
import time
import numpy as np
from operations import validate_step21_seven_refresh as old
from operations import pilot_population_defect_blocks as pilot
from operations import pilot_late_population_blocks as original_pilot
from operations import population_defect_global_fields as fields
from operations import remeasure_step21_directions as directions
from operations.scan_population_defect_arrays import check_population_source

ROOT,pipeline,fresh,fixed,reused,v=old.ROOT,old.pipeline,old.fresh,old.fixed,old.reused,old.v
SOURCE=original_pilot.SOURCE
NUMERICAL=pilot.SOURCE
PILOT='outputs/hpc/step21-population-defect-pilot-20260928'
SCAN='outputs/hpc/step21-population-defect-array-audit-20260928'
LIMITS=dict(population=10,half=1,control=10)
SELECTED=tuple(range(20,34))


def source_pair(prior, state, val):
    check_population_source(prior)
    if state['active_map'] is not None or state['history']!=[val['actual_map']] or state['history'][0]['iteration']!=1:
        raise RuntimeError('requires the settled rejected actual full map')
    inp=val['candidate'];row=state['history'][0]
    mapped=dict(path=row['output_path'],sha256=row['output_sha256'],size_bytes=pipeline.STATE_BYTES)
    if (row['input_sha256']!=inp['sha256'] or state['current_sha256']!=mapped['sha256']
            or state['slots'][state['current_slot']]!=mapped['path'] or val['validated']):
        raise RuntimeError('actual rejected source changed')
    case=prior['cases']['population']
    if case['input']!=inp or case['output']!=mapped:
        raise RuntimeError('local source map pair changed')
    return inp,mapped


def require_array_review(review,terminal):
    if (review['job_id']!=79850 or review['source_job_id']!=79747
            or review['frozen_material_case']!='population' or review['verified_frequency_rows']!=1792
            or not review['mac_independent_fsum'] or not review['school_raw_arrays_scanned']
            or review['operator_recomputed'] or review['new_material_steps']!=0
            or terminal['job_id']!=79850 or terminal['state']!='COMPLETED'
            or 'ExitCode=0:0' not in terminal['scontrol']):
        raise RuntimeError('independent population array scan required')


def sequence(validate,evaluate):
    if not validate():return 'stopped_at_full_half_validation'
    for n in (2,10):
        for name in ('control','population'):
            reason=evaluate(name,n)
            if reason!='pass':return f'stopped_at_{name}_map{n:02d}_{reason}'
    return 'population_global_windows_complete_requires_review'


def signal_gate(n,measurement):
    if n not in (2,10):raise ValueError('undeclared feedback window')
    # 第2张只检验相邻端点可分辨性；跨修正的跳变量不能冒充八张持续性。
    return bool(measurement['endpoint_signal_resolved'] and
                (n==2 or measurement['eight_map_signal_persistent']))


def write_candidates(source,replacements,full,half,shape,checkpoint=lambda:None):
    return fields.write_candidates(source,replacements,full,half,shape,checkpoint)


def validate_fields(paths,original_pair,shape,checkpoint=lambda:None):
    return fields.validate(paths,original_pair,shape,checkpoint)


def prepare(out):
    ev=ROOT/'handoff/evidence';source=ROOT/SOURCE;local=ROOT/PILOT
    metadata=ev/'20260928-population-defect-metadata-review.json'
    names=['declaration.json','summary.json','status.json']+[f'population-block{i:02d}.json' for i in pilot.BLOCKS]
    claims=v.audited_inputs(local,metadata,ev/'20260928-population-defect-79747-terminal.json',79747,names)
    review=pipeline.read(metadata);prior=pipeline.read(local/'declaration.json');summary=pipeline.read(local/'summary.json')
    if not review['all_local_cases_passed'] or not summary['all_local_cases_passed']:
        raise RuntimeError('both local pilots must pass')
    check_population_source(prior)
    ap=ev/'20260928-population-defect-array-independent-review.json'
    tp=ev/'20260928-population-defect-array-79850-terminal.json'
    ar=pipeline.read(ap);require_array_review(ar,pipeline.read(tp))
    scanroot=ROOT/SCAN;scan=pipeline.read(scanroot/'declaration.json');ss=pipeline.read(scanroot/'summary.json')
    if scan['claims']!=ar['claims'] or scan['code']!=ar['code'] or ss['status']!='complete_requires_mac_reduction' or not ss['source_unchanged']:
        raise RuntimeError('scan lineage changed')
    for c in ar['download_receipt']:
        path=scanroot/c['name']
        if path.stat().st_size!=c['size_bytes'] or pipeline.sha256(path)!=c['sha256']:
            raise RuntimeError('scan file no longer matches independent reduction')
        claims.append(pipeline.claim(path))
    claims+=scan['claims']+scan['code']+[pipeline.claim(ap),pipeline.claim(tp)]+prior['claims']+prior['code']
    replacements={}
    for i,row in zip(pilot.BLOCKS,review['rows'],strict=True):
        report=pipeline.read(local/f'population-block{i:02d}.json')
        if row['block']!=i or row['local_arrays']!=report['local_arrays'] or not all(report['checks'].values()):
            raise RuntimeError('local field identity or gates changed')
        replacements[str(i)]=report['local_arrays']
    names=['declaration.json','summary.json']+[f'{name}/{file}' for name in ('control','population') for file in
        ('state.json','config.json','trial_material.npz','endpoints-map08/manifest.json','pair08/feedback_protocol.json',
         'pair08/previous_response.npz','pair08/final_response.npz')]
    claims+=v.audited_inputs(source,ev/'20260928-late-direction-complete-review.json',
        ev/'20260928-late-direction-79151-terminal.json',79151,names)
    state=pipeline.read(source/'population/state.json');ret=pipeline.read(source/'population/endpoints-map08/manifest.json')
    original_pair=original_pilot.settled_pair(state,ret)
    if prior['original_pre_correction_pair']!=list(original_pair):raise RuntimeError('original 79151 reference changed')
    numeric=ROOT/NUMERICAL
    numeric_names=['declaration.json','summary.json','population/state.json','population/config.json',
                   'population/trial_material.npz','population/validation.json']
    claims+=v.audited_inputs(numeric,ev/'20260928-late-population-global-review.json',
        ev/'20260928-late-population-global-79631-terminal.json',79631,numeric_names)
    nstate=pipeline.read(numeric/'population/state.json');nval=pipeline.read(numeric/'population/validation.json')
    inp,mapped=source_pair(prior,nstate,nval)
    if pipeline.read(numeric/'summary.json')['status']!='stopped_at_full_half_validation':raise RuntimeError('source rejection changed')
    fixed.same_trial(v.load_arrays(numeric/'population/trial_material.npz'),v.load_arrays(source/'population/trial_material.npz'))
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
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/validate_population_defect_global.sbatch',
        'tests/test_population_defect_global.py','handoff/protocols/population-defect-global-v1.md')]
    claims+=[inp,mapped,control_seed]+list(original_pair)+list(replacements.values())+list(finite['sources'].values())
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases=cases,claims=claims,code=code,source=SOURCE,source_job=79151,source_pilot=PILOT,pilot_job=79747,
        array_job=79850,source_pair=[inp,mapped],source_row=nstate['history'][0],control_seed=control_seed,
        numerical_source=NUMERICAL,numerical_source_job=79631,source_rejected=True,
        original_pair=list(original_pair),original_row=state['history'][-1],
        both_references_must_pass=True,half_midpoint_reference='79631 current q and new full',
        replacements=replacements,centers=list(pilot.BLOCKS),selected_blocks=list(SELECTED),gates=fields.GATES,
        child_limits=LIMITS,maximum_maps=21,maximum_feedback_pairs=4,cadence=[2,10],
        accepted_outer_steps=20,automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,
        matched_initial_radiation=False,first_pair_shift_is_not_stability=True,
        signal_tolerance=.1,control_window_tolerance=.001,
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
        write_candidates(paths[0],{int(i):ROOT/c['path'] for i,c in plan['replacements'].items()},full,half,pipeline.SHAPE,reused.checkpoint)
        seeds={'population':pipeline.claim(full),'half':pipeline.claim(half),'control':plan['control_seed']}
        reused.immutable(out/'candidate-claims.json',seeds);reused.verify(plan['source_pair']+list(plan['replacements'].values()))
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
            comparison,original_comparison=validate_fields(paths+[full,ROOT/row['output_path'],half,ROOT/hrow['output_path']],
                [ROOT/c['path'] for c in plan['original_pair']],pipeline.SHAPE,reused.checkpoint)
            checks=fields.checks(comparison,original_comparison,plan['source_row'],plan['original_row'],row,hrow)
            peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if peak>=6*1024**3:raise RuntimeError('parent memory guard')
            result=dict(source_pair=plan['source_pair'],candidate=seeds['population'],half_candidate=seeds['half'],
                actual_map=row,half_map=hrow,field_comparison=comparison,original_comparison=original_comparison,
                original_pair=plan['original_pair'],checks=checks,validated=all(checks.values()),
                parent_peak_rss_bytes=peak,frozen_material_case='population',accepted_material_step=False)
            reused.verify(plan['source_pair']+plan['original_pair']+list(seeds.values()))
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
