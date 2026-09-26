"""Full-frequency checks of two local corrections, then bounded control windows."""
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
from operations import pilot_step21_joint_blocks as pilot
from operations import joint_block_global_fields as fields

v=wide.validation
ROOT,pipeline,fresh,fixed,reused,driver=v.ROOT,v.pipeline,v.fresh,v.fixed,v.reused,v.driver
StreamState=v.StreamState
SOURCE=pilot.SOURCE
PILOT='outputs/hpc/step21-joint-block-pilot-20260926'
LIMIT=10



def conditional_sequence(validate,map_one,feedback):
    if not validate():return 'true_map_not_validated'
    map_one(2)
    if not feedback(2):return 'first_control_pair_not_stable'
    for n in range(3,11):map_one(n)
    if not feedback(10):return 'second_control_pair_not_stable'
    return 'joint_block_global_validation_complete_requires_review'


def prepare(out):
    ev=ROOT/'handoff/evidence';source=ROOT/SOURCE;local=ROOT/PILOT
    names=['declaration.json','summary.json','status.json']+[f'control-block{i:02d}.json' for i in pilot.BLOCKS]
    claims=v.audited_inputs(local,ev/'20260926-joint-block-pilot-review.json',
        ev/'20260926-joint-block-pilot-77817-terminal.json',77817,names)
    review=pipeline.read(ev/'20260926-joint-block-pilot-review.json')
    prior=pipeline.read(local/'declaration.json');summary=pipeline.read(local/'summary.json')
    if not review['all_local_cases_passed'] or not summary['all_local_cases_passed'] or prior['blocks']!=list(pilot.BLOCKS):
        raise RuntimeError('reviewed local eligibility required')
    replacements={}
    for i,audit in zip(pilot.BLOCKS,review['rows'],strict=True):
        report=pipeline.read(local/f'control-block{i:02d}.json')
        if audit['block']!=i or audit['local_arrays']!=report['local_arrays'] or not all(report['checks'].values()):
            raise RuntimeError('local candidate lineage or eligibility changed')
        replacements[str(i)]=report['local_arrays']
    claims+=prior['claims']+prior['code']+list(replacements.values())
    names=['control/state.json','control/config.json','control/trial_material.npz',
           'control/endpoints-map10/manifest.json','control/pair10/feedback_protocol.json',
           'control/pair10/previous_response.npz','control/pair10/final_response.npz','declaration.json']
    claims+=v.audited_inputs(source,ev/'20260926-heating-validation-complete-review.json',
        ev/'20260926-heating-validation-77577-terminal.json',77577,names)
    state=pipeline.read(source/names[0]);ret=pipeline.read(source/names[3]);inp,mapped=pilot.settled_pair(state,ret)
    record=prior['cases']['control']
    if record['input']!=inp or record['output']!=mapped:raise RuntimeError('local source map differs')
    template_root=ROOT/recovery.original.SOURCE
    claims+=v.audited_inputs(template_root,ev/'20260925-positive-validation-complete-review.json',
        ev/'20260925-positive-validation-77126-terminal.json',77126,['thermal/pair03/feedback_protocol.json'])
    finite=pipeline.read(template_root/'thermal/pair03/feedback_protocol.json')
    zero=pipeline.read(source/'control/pair10/feedback_protocol.json');sources=zero['sources']
    base=v.load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
    old=v.load_arrays(ROOT/sources['physical_old_time_level']['path']);trial=v.load_arrays(source/'control/trial_material.npz')
    fixed.exact_trial(trial,base,r,old,'control');fixed.same_trial(trial,base)
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(source/'control/trial_material.npz',inputs/'trial_material.npz')
    cfg=pipeline.read(source/'control/config.json');pipeline.write_json(inputs/'config.json',cfg)
    fixed.same_trial(v.load_arrays(inputs/'trial_material.npz'),trial)
    owned={'trial':pipeline.claim(inputs/'trial_material.npz'),'config':pipeline.claim(inputs/'config.json')}
    preview=recovery.control_protocol(finite,zero,out/'control/pair02',ret['endpoints'],ret['history_rows'],owned['trial'],
        pipeline.claim(source/'control/endpoints-map10/manifest.json'),pipeline.claim(source/'declaration.json'))
    fixed.native_identity(preview)
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/validate_step21_joint_blocks.sbatch',
        'tests/test_validate_step21_joint_blocks.py','handoff/protocols/step21-joint-block-global-v1.md')]
    claims+=list(owned.values())+list(finite['sources'].values())
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases={'control':owned},claims=claims,code=code,selected='joint-cores23-to25-and47-to49-full',
        source_pair=[inp,mapped],source_row=state['history'][-1],replacements=replacements,gates=fields.GATES,
        maximum_maps=11,child_limits={'control':10,'half':1},maximum_feedback_pairs=2,cadence=[2,10],
        accepted_outer_steps=20,automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,
        source_pilot=PILOT,source_control=SOURCE,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    previous={e:v.load_arrays(source/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
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
        if shutil.disk_usage(out).free<18*pipeline.STATE_BYTES:raise RuntimeError('insufficient checkpoint space')
        plan,finite,zero,base,r,old,previous=prepare(out);origin={k:a.copy() for k,a in previous.items()}
        reused.LIMITS=plan['child_limits'];paths=[ROOT/c['path'] for c in plan['source_pair']]
        mark('writing_candidates');seedpath=out/'full-candidate.dat';halfpath=out/'half-candidate.dat'
        fields.write_candidates(paths[0],{int(i):ROOT/c['path'] for i,c in plan['replacements'].items()},
            seedpath,halfpath,pipeline.SHAPE,checkpoint=reused.checkpoint)
        reused.verify(plan['source_pair']+list(plan['replacements'].values()))
        seed=pipeline.claim(seedpath);halfseed=pipeline.claim(halfpath);reports={}
        reused.immutable(out/'candidate-claims.json',{'full':seed,'half':halfseed})
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
                mark('mapping_half',completed_maps=1)
                hf,hcfg,hstate=reused.child(out,'half','control',halfseed,plan)
                fixed.same_trial(v.load_arrays(hf/'trial_material.npz'),base)
                recovery.original.map_once(hf,hcfg,hstate)
                if len(hstate['history'])!=1 or hstate['history'][0]['input_sha256']!=halfseed['sha256']:
                    raise RuntimeError('half candidate not mapped exactly once')
                hrow=hstate['history'][0]
                newpaths=paths+[seedpath,ROOT/row['output_path'],halfpath,ROOT/hrow['output_path']]
                comparison=fields.validate(newpaths,pipeline.SHAPE,checkpoint=reused.checkpoint)
                checks=fields.checks(comparison,plan['source_row'],row,hrow)
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                result=dict(selected=plan['selected'],candidate=seed,half_candidate=halfseed,
                    source_pair=plan['source_pair'],actual_map=row,half_map=hrow,
                    field_comparison=comparison,checks=checks,validated=all(checks.values()),
                    parent_peak_rss_bytes=peak,accepted_material_step=False)
                reused.immutable(folder/'validation.json',result)
                reused.verify(plan['source_pair']+[seed,halfseed]);reused.archive(out,'full-half-validation')
                return result['validated']
            def feedback(n):
                nonlocal previous
                reused.checkpoint()
                if len(state['history'])!=n or not pipeline.pair_ready(state['history'],1e-4):
                    reports[str(n)]=dict(feedback_evaluated=False,inner_pair_ready=False);return False
                fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp);rd=folder/f'pair{n:02d}';rd.mkdir()
                p=recovery.control_protocol(finite,zero,rd,ret['endpoints'],ret['history_rows'],pipeline.claim(folder/'trial_material.npz'),
                    pipeline.claim(rp),pipeline.claim(out/'declaration.json'))
                p['sources']['joint_block_global_validation']=pipeline.claim(folder/'validation.json')
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
                    from_77577_comparison=recovery.original.window_comparison(vectors,origin,r,old['cell_mass_g_cm2']),
                    fresh_control_minus_r20_norms=asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2'])),
                    baseline_replaced=False,promoted=False)
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                if n==2:
                    if ret['endpoints']['previous']['sha256']!=seed['sha256'] or ret['endpoints']['final']['sha256']!=state['history'][0]['output_sha256']:
                        raise RuntimeError('first feedback is not q and T(q)')
                if n==10:stable=stable and report['window_comparison']['passed']
                report['conditional_continuation_pass']=bool(stable)
                report['parent_peak_rss_bytes']=peak;reused.immutable(rd/'decision.json',report);reports[str(n)]=report;previous=vectors
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'control-map{n:02d}-feedback')
                return stable
            terminal=conditional_sequence(validate,next_map,feedback)
        reused.verify(plan['claims']+plan['code'])
        reused.immutable(out/'summary.json',dict(status=terminal,cases=reports,accepted_outer_steps=20,new_material_steps=0,
            maps=len(state['history'])+1,control_maps=len(state['history']),half_maps=1,baseline_replaced=False,strict_error_bound=False))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,args.run))
