"""Confirm accepted step 2, then conditionally attempt one bounded step 3.

Preparation bodies retain the reviewed lineage checks of accepted_step_confirmation
and second_outer_step, with an explicit source and step-3 contract. Old modules
and old declarations are immutable; no physical time advancement is permitted.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import signal
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
import pipeline
from operations import accepted_step_confirmation as confirm
from operations import response_direction_batch as batch
from operations import second_outer_step as outer
from operations import composite_hybrid_batch as reused
from operations.constrained_hybrid_batch import relay_dispatch, counts
from operations.prepare_encoded_backtrack import load_arrays
from operations.radiation_history_diagnostic import identical_material
from operations.second_outer_step import confirmed_source, rebase_trial, validate_trial
SOURCE='outputs/hpc/outer-step2-20260921'
TERMINAL={'complete','confirmation_not_passed','formal_acceptance_requires_review','science_stopped','failed'}
MAXIMUM_MAPS=24
MAXIMUM_PAIRS=8


def budget(out):
    confirmation=out/'confirmation';next_step=out/'next-step'
    for stage in (confirmation,next_step):
        if (stage/'status.json').exists() and pipeline.read(stage/'status.json')['status']=='failed':
            raise RuntimeError('stage program/resource failure is terminal')
    confirm.budget(confirmation)
    batch.check_budget(batch.child_states(next_step))
    stages={'confirmation':counts(confirm.states(confirmation)),
            'next_step':counts(batch.child_states(next_step))}
    used_maps=sum(s['completed_maps']+s['active_maps'] for s in stages.values())
    used_pairs=sum(s['completed_pairs']+s['pending_pairs'] for s in stages.values())
    if used_maps>MAXIMUM_MAPS or used_pairs>MAXIMUM_PAIRS:
        raise RuntimeError('combined immutable budget exceeded')
    return {'stages':stages,'maps_committed_or_active':used_maps,
            'pairs_completed_or_pending':used_pairs}


def mark(out,status,**extra):
    p=out/'status.json';previous=pipeline.read(p) if p.exists() else {}
    if previous.get('status')=='failed' and status!='failed':
        raise RuntimeError('failure is terminal')
    if previous.get('status') in TERMINAL and status not in (previous['status'],'failed'):
        raise RuntimeError('terminal status immutable')
    # Fault reporting must itself work even when a child budget/fault check fails.
    if status=='failed':
        previous.update(status=status,updated_unix=time.time(),**extra)
    else:
        previous.update(status=status,updated_unix=time.time(),**budget(out),**extra)
    pipeline.write_json(p,previous);print(previous,flush=True)


def declare(out):
    p=out/'declaration.json'
    if p.exists():
        plan=pipeline.read(p);reused.verify(plan['pinned'])
        if plan['maximum_maps']!=MAXIMUM_MAPS or plan['maximum_pairs']!=MAXIMUM_PAIRS:
            raise RuntimeError('combined budget changed')
        return plan
    source=pipeline.read(ROOT/SOURCE/'status.json')
    if source['status']!='formal_acceptance_requires_review' or source['candidate']!='full':
        raise RuntimeError('expected accepted second outer step')
    code=[pipeline.claim(f) for d in ('operations','diagnostics') for f in sorted((ROOT/d).iterdir()) if f.suffix in ('.py','.sbatch')]
    claims=[pipeline.claim(ROOT/SOURCE/f) for f in ('status.json','declaration.json','full/state.json',
        'full/feedback-round2/feedback_summary.json','full/feedback-round2/fresh_control_comparison.json')]
    comparison=pipeline.read(ROOT/SOURCE/'full/feedback-round2/fresh_control_comparison.json')
    if not fresh_contraction(comparison):raise RuntimeError('source lacks fresh-control contraction')
    plan={'source':SOURCE,'pinned':code+claims,'environment':pipeline.environment(),
          'maximum_maps':MAXIMUM_MAPS,'maximum_pairs':MAXIMUM_PAIRS,
          'confirmation_maps':6,'confirmation_pairs':3,'conditional_next_maps':18,'conditional_next_pairs':5,
          'next_outer_step_index':3,'physical_time_advanced':False,'automatic_resubmit':False,
          'gates_relaxed':False,'maximum_new_accepted_material_steps':1}
    reused.immutable(p,plan);return plan


def fresh_contraction(report):
    cs=report.get('comparisons',{})
    return set(cs)=={'previous','final'} and all(
        set(v)=={'previous','final'} and all(
            set(row.get('candidate_over_base',{}))=={'l2','mass_weighted','maximum_cell'}
            and all(np.isfinite(x) and 0<=x<1 for x in row['candidate_over_base'].values())
            for row in v.values()) for v in cs.values())


def confirmation_passed(folder):
    s=pipeline.read(folder/'status.json')
    if s['status']!='complete' or s.get('precision_confirmation_passed') is not True:return False
    p=folder/'confirmation.json'
    if not p.exists():raise RuntimeError('completed confirmation lacks its report')
    report=pipeline.read(p)
    if report.get('precision_confirmation_passed') is not True:return False
    if set(report['cases'])!={'confirm2','confirm4'}:raise RuntimeError('confirmation case inventory changed')
    for name,c in report['cases'].items():
        rd=folder/name/'feedback-round1';summary=pipeline.read(rd/'feedback_summary.json')
        state=pipeline.read(folder/name/'state.json')
        outer.confirmed_source(s,report,state,summary)
        if c['all_original_gates'] is not True or c['fresh_control_contraction'] is not True:return False
        reused.verify([c['comparison']])
        if c['comparison']!=pipeline.claim(rd/'fresh_control_comparison.json'):
            raise RuntimeError('confirmation comparison path differs from declared round')
        if not fresh_contraction(pipeline.read(rd/'fresh_control_comparison.json')):return False
    return True


@contextmanager
def stage_protocols(index,source):
    original=pipeline.feedback_protocol
    def build(cfg,state):
        legacy=original(cfg,state);payload=outer.rebase_payload(pipeline.read(legacy),cfg)
        payload['outer_iteration'].update(index=index,source=source)
        target=legacy.with_name('rebased_feedback_template.json');reused.immutable(target,payload)
        return target
    pipeline.feedback_protocol=build
    try:yield
    finally:pipeline.feedback_protocol=original


def run_confirmation(folder):
    previous=confirm.prepare;confirm.prepare=prepare_confirmation
    try:
        # This confirms x2 relative to x1/R1; its nonlinear baseline is unchanged.
        with stage_protocols(2,'outputs/hpc/accepted-confirmation-20260921/confirm4'):
            confirm.execute(folder)
    finally:confirm.prepare=previous


def run_next(folder,confirmation_root):
    previous=batch.prepare;batch.prepare=lambda out:prepare_next(out,confirmation_root)
    try:
        with stage_protocols(3,str((confirmation_root/'confirm4').relative_to(ROOT))):
            batch.execute(folder)
    finally:batch.prepare=previous


def execute(out):
    budget(out)
    if (out/'status.json').exists() and pipeline.read(out/'status.json')['status'] in TERMINAL:return
    declare(out);reused.checkpoint()
    if __import__('shutil').disk_usage(out).free<24*pipeline.STATE_BYTES:
        raise RuntimeError('insufficient space for both retained stages')
    confirmation=out/'confirmation';confirmation.mkdir(exist_ok=True)
    mark(out,'confirmation');run_confirmation(confirmation);budget(out);reused.checkpoint()
    if not confirmation_passed(confirmation):
        mark(out,'confirmation_not_passed');reused.archive(out,'confirmation-not-passed');return
    # Persist a hash-bound transition before creating any next-step material.
    transition={'confirmation':pipeline.claim(confirmation/'confirmation.json'),
                'state':pipeline.claim(confirmation/'confirm4/state.json'),
                'summary':pipeline.claim(confirmation/'confirm4/feedback-round1/feedback_summary.json'),
                'next_outer_step_index':3,'physical_time_advanced':False}
    reused.immutable(out/'transition.json',transition)
    next_step=out/'next-step';next_step.mkdir(exist_ok=True)
    mark(out,'next_step');run_next(next_step,confirmation);budget(out);reused.checkpoint()
    s=pipeline.read(next_step/'status.json')
    if s['status']=='formal_acceptance_requires_review':
        name=s['candidate'];state=pipeline.read(next_step/name/'state.json')
        rd=ROOT/Path(state['diagnostic']['rounds'][-1]['ledger']).parent
        corroborated=fresh_contraction(pipeline.read(rd/'fresh_control_comparison.json'))
        mark(out,'formal_acceptance_requires_review',candidate=name,fresh_control_corroborated=corroborated)
    elif s['status']=='complete':mark(out,'complete',new_material_step_accepted=False)
    elif s['status']=='baseline_unstable':mark(out,'science_stopped',reason='next baseline unstable')
    else:raise RuntimeError('unexpected next-stage return: '+s['status'])
    reused.archive(out,'batch-finished')

def prepare_confirmation(out):
    p=out/'declaration.json'
    if p.exists():
        plan=pipeline.read(p);reused.verify(plan['pinned']);return plan
    snap=reused.Snapshot(out);parent=snap.read(SOURCE+'/status.json')
    if parent['status']!='formal_acceptance_requires_review' or parent['candidate']!='full':raise RuntimeError('wrong source batch')
    cases={};seeds={};vectors={};trials={}
    for label,child,round_index in [('base','control',1),('trial','full',2)]:
        folder=SOURCE+'/'+child;state=snap.read(folder+'/state.json');rd=folder+'/feedback-round'+str(round_index)
        cfg=snap.read(folder+'/config.json',state['config_sha256']);reused.verify(cfg['sources'])
        t=load_arrays(snap.save(folder+'/trial_material.npz',state['trial_sha256']));trials[label]=t
        rec=snap.read(rd+'/round_summary.json');proto=snap.read(rd+('/baseline_control_protocol.json' if label=='base' else '/feedback_protocol.json'),rec['protocol_sha256'])
        if proto['sources']['trial_material']['sha256']!=state['trial_sha256']:raise RuntimeError('protocol material differs from source trial')
        if label=='trial':
            summary=snap.read(rd+'/feedback_summary.json');confirm.accepted_source(state,summary)
            if summary['protocol_sha256']!=rec['protocol_sha256']:raise RuntimeError('summary protocol changed')
        elif state.get('active_map') or state.get('pending_feedback') or state['status']!='baseline_control_complete':
            raise RuntimeError('source control unsettled')
        vectors[label]={};feedbacks={}
        for c in proto['sources'].values():
            if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
        for e,row in zip(('previous','final'),state['history'][-2:]):
            m=snap.read(rd+'/feedback/'+e+'_manifest.json');c=proto['sources'][e+'_radiation']
            if (m['status']!='complete' or not m['state_gate_passed'] or m['protocol_sha256']!=rec['protocol_sha256']
                or m['state_path']!=c['path'] or m['state_sha256']!=c['sha256']
                or row['input_path']!=c['path'] or row['input_sha256']!=c['sha256']
                or sorted(v['block_index'] for v in m['completed_blocks'])!=list(range(76))):raise RuntimeError('accepted source lineage failed')
            for block in m['completed_blocks']:snap.save(block['partial_path'],block['partial_sha256'])
            fb=load_arrays(snap.save(m['feedback_artifact_path'],m['feedback_artifact_sha256']))
            _,residual,context=reused.pair._material_response_residual(proto,fb);vectors[label][e]=residual;feedbacks[e]=fb
            if label=='trial' and e=='final':
                stored=np.load(snap.save(summary['encoded_residual_path'],summary['encoded_residual_sha256']),allow_pickle=False)
                if not np.array_equal(residual,stored):raise RuntimeError('accepted residual did not replay bitwise')
        if label=='trial':
            baseline=np.load(ROOT/proto['sources']['base_residual']['path'],allow_pickle=False)
            if not np.array_equal(baseline,t['base_residual']):raise RuntimeError('formal baseline differs from trial metadata')
            diagnostics=reused.pair.trial_feedback_pair_diagnostics(previous_feedback=feedbacks['previous'],final_feedback=feedbacks['final'],
                previous_encoded_residual=vectors[label]['previous'],final_encoded_residual=vectors[label]['final'],
                base_encoded_residual=baseline,cell_width=feedbacks['final']['subcell_width_cm'],cell_mass=context['cell_mass'])
            checks=reused.pair.trial_feedback_pair_gate_checks(diagnostics,proto['acceptance_gates'])
            if not all(checks.values()) or any(v!=summary['gate_checks'][k] for k,v in checks.items()):raise RuntimeError('replayed scientific gate differs')
            reused.immutable(out/'source-gate-replay.json',{'checks':checks,'final_residual_bitwise_equal':True,
                'atomic_heating_volume_l1':diagnostics.atomic_heating_volume_l1,
                'inner_noise_to_trial_signal_l2_ratio':diagnostics.inner_noise_to_trial_signal_l2_ratio,
                'candidate_norms':asdict(diagnostics.candidate_norms),'base_norms':asdict(diagnostics.base_norms)})
        row=state['history'][-1]
        if state['slots'][state['current_slot']]!=row['output_path'] or state['current_sha256']!=row['output_sha256']:raise RuntimeError('seed is not latest output')
        seeds[label]={'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES};reused.verify([seeds[label]])
        cases[label]={'trial':pipeline.claim(ROOT/folder/'trial_material.npz'),'config':pipeline.claim(ROOT/folder/'config.json')}
    b,t=trials['base'],trials['trial']
    if float(b['relaxation'])!=0 or float(t['relaxation'])!=1/256 or not np.array_equal(b['encoded_state'],t['base_encoded_state']):raise RuntimeError('wrong material candidate')
    for k in ('base_encoded_state','base_residual','density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(b[k],t[k]):raise RuntimeError('physical lineage changed: '+k)
    direction=snap.read(SOURCE+'/declaration.json')['outer_baseline']['residual'];reused.verify([direction])
    if not np.array_equal(t['finite_direction'],np.load(ROOT/direction['path'],allow_pickle=False)):raise RuntimeError('accepted direction changed')
    code=[pipeline.claim(f) for directory in ('operations','diagnostics') for f in sorted((ROOT/directory).iterdir()) if f.suffix in ('.py','.sbatch')]
    for label in vectors:
        for e,v in vectors[label].items():np.save(out/(label+'-source-'+e+'-residual.npy'),v,allow_pickle=False)
    plan={'environment':pipeline.environment(),'cases':cases,'code':code,'seeds':seeds,'limits':confirm.LIMITS,
          'pinned':list(snap.records.values())+code+list(seeds.values())+[direction],
          'maximum_maps':6,'maximum_pairs':3,'source_accepted':True,'changed_material':False,
          'changed_physical_dt':False,'changed_formal_denominator':False,'true_error_bound':False,
          'scope':'source replay, two-map control, fixed candidate +2 then +4 maps; no new outer step'}
    reused.immutable(p,plan);return plan


def prepare_next(out, confirmation_root):
    source = str(confirmation_root.relative_to(ROOT))
    path = out/'declaration.json'
    if path.exists():
        plan = pipeline.read(path); reused.verify(plan['pinned'])
        if plan['limits'] != batch.LIMITS or plan['alphas'] != batch.ALPHAS:
            raise RuntimeError('declared budget or amplitude changed')
        return plan
    snap = reused.Snapshot(out)
    parent = snap.read(source+'/status.json'); confirmation = snap.read(source+'/confirmation.json')
    folder = source+'/confirm4'; rd = folder+'/feedback-round1'
    state = snap.read(folder+'/state.json'); summary = snap.read(rd+'/feedback_summary.json')
    confirmed_source(parent, confirmation, state, summary)
    cfg = snap.read(folder+'/config.json', state['config_sha256']); reused.verify(cfg['sources'])
    accepted = load_arrays(snap.save(folder+'/trial_material.npz', state['trial_sha256']))
    rec = snap.read(rd+'/round_summary.json')
    proto = snap.read(rd+'/feedback_protocol.json', rec['protocol_sha256'])
    if summary['protocol_sha256'] != rec['protocol_sha256'] or proto['sources']['trial_material']['sha256'] != state['trial_sha256']:
        raise RuntimeError('source protocol or material mismatch')
    for c in proto['sources'].values():
        if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
    feedbacks = {}; vectors = {}
    for e, row in zip(('previous', 'final'), state['history'], strict=True):
        m = snap.read(rd+'/feedback/'+e+'_manifest.json'); c = proto['sources'][e+'_radiation']
        if (m['status'] != 'complete' or not m['state_gate_passed']
            or m['protocol_sha256'] != rec['protocol_sha256']
            or m['state_path'] != c['path'] or m['state_sha256'] != c['sha256']
            or row['input_path'] != c['path'] or row['input_sha256'] != c['sha256']
            or sorted(v['block_index'] for v in m['completed_blocks']) != list(range(76))):
            raise RuntimeError('confirmed feedback lineage failed')
        for b in m['completed_blocks']: snap.save(b['partial_path'], b['partial_sha256'])
        fb = load_arrays(snap.save(m['feedback_artifact_path'], m['feedback_artifact_sha256']))
        _, r, context = reused.pair._material_response_residual(proto, fb)
        feedbacks[e] = fb; vectors[e] = r
    stored = np.load(snap.save(summary['encoded_residual_path'], summary['encoded_residual_sha256']), allow_pickle=False)
    if not np.array_equal(stored, vectors['final']): raise RuntimeError('confirmed residual failed bitwise replay')
    old_baseline = np.load(ROOT/proto['sources']['base_residual']['path'], allow_pickle=False)
    if not np.array_equal(accepted['base_residual'], old_baseline): raise RuntimeError('source denominator mismatch')
    diag = reused.pair.trial_feedback_pair_diagnostics(
        previous_feedback=feedbacks['previous'], final_feedback=feedbacks['final'],
        previous_encoded_residual=vectors['previous'], final_encoded_residual=stored,
        base_encoded_residual=old_baseline, cell_width=feedbacks['final']['subcell_width_cm'],
        cell_mass=context['cell_mass'])
    checks = reused.pair.trial_feedback_pair_gate_checks(diag, proto['acceptance_gates'])
    if not all(checks.values()) or any(summary['gate_checks'][k] != v for k,v in checks.items()):
        raise RuntimeError('confirmed scientific gate failed replay')
    reused.immutable(out/'source-gate-replay.json', {'checks': checks,
        'residual_bitwise_equal': True, 'new_base_residual_norms': asdict(diag.candidate_norms),
        'physical_time_advanced': False})
    old = load_arrays(ROOT/proto['sources']['physical_old_time_level']['path'])
    base = rebase_trial(accepted, stored, old)
    residual_path = out/'base_residual.npy'
    if residual_path.exists():
        if not np.array_equal(np.load(residual_path, allow_pickle=False), stored): raise RuntimeError('base residual changed')
    else: np.save(residual_path, stored, allow_pickle=False)
    basefolder = out/'proposal-base'; basefolder.mkdir(exist_ok=True)
    basepath = basefolder/'trial_material.npz'
    if basepath.exists(): identical_material(base, load_arrays(basepath))
    else: np.savez(basepath, **base)
    claims = {'material': pipeline.claim(basepath), 'residual': pipeline.claim(residual_path),
              'physical_old_time_level': proto['sources']['physical_old_time_level']}
    cases = {}
    for label, alpha in [('base', 0.), *batch.ALPHAS.items()]:
        trial = base if label == 'base' else batch.make_trial(base, stored, alpha)
        validate_trial(trial, base, stored)
        dest = out/('proposal-'+label); dest.mkdir(exist_ok=True); tp = dest/'trial_material.npz'
        if tp.exists(): identical_material(trial, load_arrays(tp))
        else: np.savez(tp, **trial)
        identical_material(trial, load_arrays(tp))
        newcfg = deepcopy(cfg)
        newcfg.update(candidate_relaxation=alpha, outer_baseline=claims,
            physics_scope='third nonlinear material step; confirmed trial as base; unchanged physical old time')
        newcfg['sources'] = list(cfg['sources']) + list(claims.values())
        reused.immutable(dest/'config.json', newcfg)
        cases[label] = {'trial': pipeline.claim(tp), 'config': pipeline.claim(dest/'config.json')}
    row = state['history'][-1]
    if state['slots'][state['current_slot']] != row['output_path'] or state['current_sha256'] != row['output_sha256']:
        raise RuntimeError('seed is not latest confirmed-material output')
    seed = {'path': row['output_path'], 'sha256': row['output_sha256'], 'size_bytes': pipeline.STATE_BYTES}
    reused.verify([seed])
    code = [pipeline.claim(p) for folder in ('operations', 'diagnostics')
            for p in sorted((ROOT/folder).iterdir()) if p.suffix in ('.py', '.sbatch')]
    plan = {'environment': pipeline.environment(), 'cases': cases, 'code': code,
        'pinned': list(snap.records.values())+cfg['sources']+code+[seed]+list(claims.values())
            +[v for c in cases.values() for v in c.values()],
        'seed': seed, 'outer_baseline': claims, 'alphas': batch.ALPHAS, 'limits': batch.LIMITS,
        'maximum_maps': 18, 'maximum_pairs': 5, 'outer_step_index': 3,
        'physical_dt_changed': False, 'physical_time_advanced': False,
        'formal_baseline_changed': True, 'gates_relaxed': False,
        'automatic_resubmit': False, 'accepted_column': False}
    reused.immutable(path, plan)
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);a=p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out=pipeline.safe_path(ROOT,a.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=True)
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signal.signal(signal.SIGUSR1,reused.stop);signal.signal(signal.SIGTERM,reused.stop)
        with relay_dispatch():
            try:execute(out)
            except reused.Stopped as exc:
                mark(out,'interrupted',reason=str(exc));reused.archive(out,'interrupted')
            except Exception as exc:
                states=list(confirm.states(out/'confirmation').values())+list(batch.child_states(out/'next-step').values())
                pending=any(s.get('status')=='diagnosis_incomplete' and s.get('pending_feedback',{}).get('stage')=='ledger' for s in states)
                mark(out,'diagnosis_incomplete' if pending else 'failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':main()
