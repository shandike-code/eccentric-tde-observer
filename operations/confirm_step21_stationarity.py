"""Confirm persistent fixed-x20 response stationarity; never rebase or accept matter."""
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
from operations import recover_step21_control_windows as recovery

original=recovery.original
v,pipeline,ROOT,fixed,fresh,reused=original.v,original.pipeline,original.ROOT,original.fixed,original.fresh,original.reused
SOURCE='outputs/hpc/step21-seven-refresh-short-validation-20260927'
LIMIT=16
CADENCE=(8,16)
TOLERANCE=1e-3
ZERO_GATES={'last_two_photoionization_pass','last_two_total_recombination_pass','last_two_atomic_heating_pass',
    'last_two_direct_heating_pass','last_two_formal_heating_pass','inner_pair_ready','physical_response_pass'}


def validate_window(window):
    keys={a+'_vs_'+b for a in ('previous','final') for b in ('previous','final')}
    values=window['vector_difference_over_frozen_r20_norms']
    if set(values)!=keys or window['tolerance']!=TOLERANCE or window['baseline_replaced'] or window['strict_error_bound']:
        raise RuntimeError('window identity changed')
    a=np.asarray(list(values.values()),float)
    if a.shape!=(4,3) or not np.isfinite(a).all() or np.any(a<0):raise RuntimeError('invalid window ratios')
    passed=bool(np.all(a<TOLERANCE))
    if window['passed']!=passed:raise RuntimeError('window verdict inconsistent')
    return passed


def source_seed(summary,audit,state,retained):
    if (summary['status']!='seven_refresh_short_validation_complete_requires_review'
            or summary['maps']!=11 or summary['control_maps']!=10 or summary['half_maps']!=1
            or summary['accepted_outer_steps']!=20 or summary['new_material_steps']!=0
            or summary['baseline_replaced'] or summary['strict_error_bound']):
        raise RuntimeError('source not a completed fixed-x20 witness')
    if (audit['job_id']!=78548 or not audit['final_summary_present'] or audit['feedback_rounds']!=[2,10]
            or audit['accepted_outer_steps']!=20 or audit['new_material_steps']!=0
            or audit['baseline_replaced'] or audit['strict_error_bound']):raise RuntimeError('independent source audit missing')
    for n in ('2','10'):
        row=summary['cases'][n]
        if (not row['zero_control_stable'] or not row['conditional_continuation_pass']
                or set(row['original_gates'])!=ZERO_GATES or not all(row['original_gates'].values())
                or row['original_gates']!=audit['windows'][n]['gate_checks']):
            raise RuntimeError('source feedback not stable')
    if not validate_window(summary['cases']['10']['window_comparison']) or not validate_window(audit['windows']['10']['window']):
        raise RuntimeError('source eight-map window not stable')
    # 新零位移对照只能从已审最新映射后继继续，不从初始候选重启。
    rows=state['history']
    if state['active_map'] is not None or len(rows)!=10 or retained['history_rows']!=rows[-2:]:
        raise RuntimeError('source endpoint history incomplete')
    if any(a['output_sha256']!=b['input_sha256'] for a,b in zip(rows,rows[1:])):raise RuntimeError('source chain differs')
    for key,row in zip(('previous','final'),rows[-2:]):
        if retained['endpoints'][key]['sha256']!=row['input_sha256']:raise RuntimeError('source input mismatch')
    seed=retained['endpoints']['mapped_final']
    if seed['sha256']!=rows[-1]['output_sha256'] or seed['size_bytes']!=pipeline.STATE_BYTES:
        raise RuntimeError('seed is not the audited latest successor')
    return seed


def sequence(map_one,feedback):
    # 第一个新增八张窗口若失败，不再消耗第二段；不盲目追加预算。
    for stop in CADENCE:
        for n in range(stop-7,stop+1):map_one(n)
        if not feedback(stop):return 'stationarity_not_confirmed'
    return 'persistent_control_stationarity_requires_review'


def prepare(out):
    ev=ROOT/'handoff/evidence';root=ROOT/SOURCE
    names=['summary.json','declaration.json','control/state.json','control/config.json','control/trial_material.npz',
        'control/endpoints-map10/manifest.json','control/pair10/feedback_protocol.json',
        'control/pair10/previous_response.npz','control/pair10/final_response.npz']
    ap=ev/'20260927-seven-refresh-short-complete-review.json'
    claims=v.audited_inputs(root,ap,ev/'20260927-seven-refresh-short-78548-terminal.json',78548,names)
    state=pipeline.read(root/'control/state.json');ret=pipeline.read(root/'control/endpoints-map10/manifest.json')
    seed=source_seed(pipeline.read(root/'summary.json'),pipeline.read(ap),state,ret)
    zero=pipeline.read(root/'control/pair10/feedback_protocol.json');sources=zero['sources']
    base=v.load_arrays(ROOT/sources['outer_base_material']['path']);r=np.load(ROOT/sources['base_residual']['path'],allow_pickle=False)
    old=v.load_arrays(ROOT/sources['physical_old_time_level']['path']);trial=v.load_arrays(root/'control/trial_material.npz')
    fixed.exact_trial(trial,base,r,old,'control');fixed.same_trial(trial,base)
    accepted=ROOT/fixed.BASE
    fixed.validate_base_against_accepted(base,v.load_arrays(accepted/'trial_material.npz'))
    if not np.array_equal(r,v.load_arrays(accepted/'common-feedback/final_response.npz')['residual']):raise RuntimeError('r20 changed')
    cfg=pipeline.read(root/'control/config.json')
    if pipeline.sha256(root/'control/config.json')!=state['config_sha256']:raise RuntimeError('source config changed')
    inputs=out/'inputs';inputs.mkdir();shutil.copyfile(root/'control/trial_material.npz',inputs/'trial_material.npz')
    pipeline.write_json(inputs/'config.json',cfg);fixed.same_trial(v.load_arrays(inputs/'trial_material.npz'),trial)
    owned=dict(trial=pipeline.claim(inputs/'trial_material.npz'),config=pipeline.claim(inputs/'config.json'))
    finite_root=ROOT/original.SOURCE
    claims+=v.audited_inputs(finite_root,ev/'20260925-positive-validation-complete-review.json',
        ev/'20260925-positive-validation-77126-terminal.json',77126,['thermal/pair03/feedback_protocol.json'])
    finite=pipeline.read(finite_root/'thermal/pair03/feedback_protocol.json')
    preview=recovery.control_protocol(finite,zero,out/'control/pair08',ret['endpoints'],ret['history_rows'],
        owned['trial'],pipeline.claim(root/'control/endpoints-map10/manifest.json'),pipeline.claim(root/'declaration.json'))
    fixed.native_identity(preview)
    prior=pipeline.read(root/'declaration.json')
    claims+=prior['claims']+prior['code']+list(sources.values())+[seed]+list(owned.values())
    claims+=[pipeline.claim(accepted/p) for p in ('trial_material.npz','common-feedback/final_response.npz')]
    code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/confirm_step21_stationarity.sbatch',
        'tests/test_confirm_step21_stationarity.py','handoff/protocols/step21-stationarity-confirmation-v1.md')]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values());reused.verify(claims+code)
    plan=dict(cases={'control':owned},source=SOURCE,source_job=78548,seed=seed,claims=claims,code=code,
        maximum_maps=16,maximum_feedback_pairs=2,cadence=[8,16],window_tolerance=TOLERANCE,
        cumulative_drift_gate=True,stop_on_first_failed_window=True,accepted_outer_steps=20,
        automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,environment=pipeline.environment())
    reused.immutable(out/'declaration.json',plan)
    origin={e:v.load_arrays(root/f'control/pair10/{e}_response.npz')['residual'] for e in ('previous','final')}
    return plan,finite,zero,base,r,old,origin


def execute(out):
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):pipeline.write_json(out/'status.json',dict(status=status,accepted_outer_steps=20,new_material_steps=0,updated_unix=time.time(),**kw))
    mark('preparing')
    try:
        if shutil.disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained space')
        plan,finite,zero,base,r,old,origin=prepare(out);previous={k:a.copy() for k,a in origin.items()};reports={}
        reused.LIMITS={'control':LIMIT}
        with fixed.relay_dispatch():
            folder,cfg,state=reused.child(out,'control','control',plan['seed'],plan)
            fixed.same_trial(v.load_arrays(folder/'trial_material.npz'),base)
            def map_one(n):
                if len(state['history'])!=n-1:raise RuntimeError('map counter changed')
                mark('mapping',completed_maps=n-1);original.map_once(folder,cfg,state)
            def feedback(n):
                nonlocal previous
                reused.checkpoint()
                if len(state['history'])!=n or not pipeline.pair_ready(state['history'],1e-4):raise RuntimeError('inner pair not ready')
                fixed.retain_pair(folder,state);rp=folder/f'endpoints-map{n:02d}/manifest.json';ret=pipeline.read(rp);rd=folder/f'pair{n:02d}';rd.mkdir()
                p=recovery.control_protocol(finite,zero,rd,ret['endpoints'],ret['history_rows'],pipeline.claim(folder/'trial_material.npz'),pipeline.claim(rp),pipeline.claim(out/'declaration.json'))
                p['sources']['stationarity_confirmation_declaration']=pipeline.claim(out/'declaration.json')
                fixed.exact_trial(v.load_arrays(folder/'trial_material.npz'),base,r,old,'control');fixed.native_identity(p)
                fresh.attach_code(p);p['common_code_claims']+=plan['code'];pp=rd/'feedback_protocol.json';reused.immutable(pp,p)
                reused.verify(list(p['sources'].values())+p['common_code_claims']);mark('feedback',after_maps=n)
                with reused.feedback_stop_guard():stable=fixed.zero_feedback(rd,p,pp,state['history'][-2:])
                summary=pipeline.read(rd/'baseline_summary.json')
                if summary.get('material_response_failures'):raise RuntimeError('physical response rejected')
                vectors={e:v.load_arrays(rd/f'{e}_response.npz')['residual'] for e in ('previous','final')}
                window=original.window_comparison(vectors,previous,r,old['cell_mass_g_cm2'])
                total=original.window_comparison(vectors,origin,r,old['cell_mass_g_cm2'])
                # 同时保留逐段和累计漂移，避免两个小变化相加后越过原尺度。
                passed=stable and validate_window(window) and validate_window(total)
                peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
                if peak>=6*1024**3:raise RuntimeError('parent memory guard')
                report=dict(feedback_evaluated=True,zero_control_stable=stable,original_gates=summary['gate_checks'],
                    window_comparison=window,from_78548_comparison=total,confirmation_pass=bool(passed),
                    fresh_control_minus_r20_norms=asdict(fresh.bridge.encoded_residual_norms(vectors['final']-r,old['cell_mass_g_cm2'])),
                    parent_peak_rss_bytes=peak,baseline_replaced=False,promoted=False)
                reused.immutable(rd/'decision.json',report);reports[str(n)]=report;previous=vectors
                reused.verify(list(p['sources'].values())+p['common_code_claims']);reused.archive(out,f'control-map{n:02d}-feedback')
                return passed
            terminal=sequence(map_one,feedback)
        reused.verify(plan['claims']+plan['code'])
        reused.immutable(out/'summary.json',dict(status=terminal,windows=reports,maps=len(state['history']),
            accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark(terminal);reused.archive(out,'complete')
    except reused.Stopped as exc:mark('interrupted',reason=str(exc));reused.archive(out,'interrupted')
    except Exception as exc:mark('failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,reused.stop)
    execute(pipeline.safe_path(ROOT,a.run))
