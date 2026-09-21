"""Replay an accepted finite step, then test persistence at fixed material."""
from __future__ import annotations
import argparse
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
from diagnostics import interval_diagnostic as driver
from operations import composite_hybrid_batch as reused
from operations.constrained_hybrid_batch import relay_dispatch, counts
from operations.response_direction_batch import control_check, round_review
from operations.prepare_encoded_backtrack import load_arrays
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms

SOURCE='outputs/hpc/response-direction-20260921'
LIMITS={'control':2,'confirm2':2,'confirm4':2}
TERMINAL={'complete','baseline_unstable','physical_domain_rejected','failed'}


def accepted_source(state,summary):
    if (state['status']!='one_material_trial_accepted' or state.get('active_map')
        or state.get('pending_feedback') or len(state['history'])!=8
        or set(summary['gate_checks'])!=REQUIRED_GATES
        or not all(v is True for v in summary['gate_checks'].values())
        or summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] is not True):
        raise ValueError('source is not the declared settled all-gate accepted step')


def states(out):
    return {k:pipeline.read(out/k/'state.json') for k in LIMITS if (out/k/'state.json').exists()}


def budget(out):
    for k,s in states(out).items():
        if s['status'] in driver.FAULT_STATUSES: raise RuntimeError('child fault: '+k)
        if len(s['history'])+int(s.get('active_map') is not None)>2: raise RuntimeError('two-map child limit exceeded')
        if len(s.get('diagnostic',{}).get('rounds',[]))+int(bool(s.get('pending_feedback')))>1:
            raise RuntimeError('one-pair child limit exceeded')


def mark(out,status,**extra):
    p=out/'status.json';old=pipeline.read(p) if p.exists() else {}
    if old.get('status') in TERMINAL and old['status']!=status:raise RuntimeError('terminal status immutable')
    old.update(status=status,updated_unix=time.time(),**counts(states(out)),**extra)
    pipeline.write_json(p,old);print(old,flush=True)


def prepare(out):
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
            summary=snap.read(rd+'/feedback_summary.json');accepted_source(state,summary)
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
    direction=snap.read(SOURCE+'/declaration.json')['direction'];reused.verify([direction])
    if not np.array_equal(t['finite_direction'],np.load(ROOT/direction['path'],allow_pickle=False)):raise RuntimeError('accepted direction changed')
    code=[pipeline.claim(f) for directory in ('operations','diagnostics') for f in sorted((ROOT/directory).iterdir()) if f.suffix in ('.py','.sbatch')]
    for label in vectors:
        for e,v in vectors[label].items():np.save(out/(label+'-source-'+e+'-residual.npy'),v,allow_pickle=False)
    plan={'environment':pipeline.environment(),'cases':cases,'code':code,'seeds':seeds,'limits':LIMITS,
          'pinned':list(snap.records.values())+code+list(seeds.values())+[direction],
          'maximum_maps':6,'maximum_pairs':3,'source_accepted':True,'changed_material':False,
          'changed_physical_dt':False,'changed_formal_denominator':False,'true_error_bound':False,
          'scope':'source replay, two-map control, fixed candidate +2 then +4 maps; no new outer step'}
    reused.immutable(p,plan);return plan


def run_case(out,name,label,seed,plan):
    folder,cfg,s=reused.child(out,name,label,seed,plan);path=folder/'state.json'
    budget(out);reused.checkpoint();reused.settle(folder,cfg,s,path,label)
    while len(s['history'])<2:
        budget(out);reused.checkpoint();mark(out,'mapping',current_case=name)
        if not driver.run_one_map(folder,cfg,s,path):raise reused.Stopped('partial map retained')
        budget(out)
    if not s.get('diagnostic',{}).get('rounds'):
        driver.start_round(folder,cfg,s,path);budget(out);mark(out,'feedback',current_case=name)
        reused.settle(folder,cfg,s,path,label)
    if label=='trial':round_review(out,name,s)
    reused.archive(out,name+'-complete');return s


def execute(out):
    if (out/'status.json').exists() and pipeline.read(out/'status.json')['status'] in TERMINAL:return
    reused.LIMITS=LIMITS;mark(out,'preparing');plan=prepare(out)
    if __import__('shutil').disk_usage(out).free<12*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained-state space')
    for name,s in states(out).items():
        if s.get('pending_feedback'):
            folder=out/name;reused.settle(folder,pipeline.read(folder/'config.json'),s,folder/'state.json','base' if name=='control' else 'trial')
    control=run_case(out,'control','base',plan['seeds']['base'],plan)
    check=control_check(out,control,pipeline.read(out/'control/feedback-round1/material_energy_ledger.json'))
    reused.immutable(out/'control-check.json',check)
    if not check['inner_and_feedback_stability_pass'] or not check['physical_response_pass']:
        mark(out,'baseline_unstable');reused.archive(out,'baseline-unstable');return
    seed=plan['seeds']['trial'];results={}
    for name in ('confirm2','confirm4'):
        s=run_case(out,name,'trial',seed,plan);rd=out/name/'feedback-round1'
        report=pipeline.read(rd/'feedback_summary.json')
        if report.get('material_response_failures'):
            mark(out,'physical_domain_rejected',current_case=name);reused.archive(out,'domain-rejected');return
        compared=pipeline.read(rd/'fresh_control_comparison.json')
        ratios=[v['candidate_over_base'] for cs in compared['comparisons'].values() for v in cs.values()]
        proto=pipeline.read(rd/'feedback_protocol.json')
        _,residual,context=reused.pair._material_response_residual(proto,load_arrays(rd/'final_feedback.npz'))
        source=np.load(out/'trial-source-final-residual.npy',allow_pickle=False)
        drift=asdict(encoded_residual_norms(residual-source,context['cell_mass']))
        results[name]={'all_original_gates':set(report['gate_checks'])==REQUIRED_GATES and all(report['gate_checks'].values())
                and report['decision']['finite_trial_accepted_as_one_nonlinear_step'] is True,
            'fresh_control_contraction':all(x<1 for r in ratios for x in r.values()),'formal_comparison':report['comparison'],
            'same_material_residual_drift_from_accepted_endpoint':drift,'drift_is_error_bound':False,
            'comparison':pipeline.claim(rd/'fresh_control_comparison.json')}
        seed={'path':s['slots'][s['current_slot']],'sha256':s['current_sha256'],'size_bytes':pipeline.STATE_BYTES}
    passed=all(r['all_original_gates'] and r['fresh_control_contraction'] for r in results.values())
    reused.immutable(out/'confirmation.json',{'source_accepted':True,'precision_confirmation_passed':passed,'cases':results,
        'true_error_bound':False,'independent_initial_history_test':False,'coupled_column_accepted':False})
    mark(out,'complete',precision_confirmation_passed=passed);reused.archive(out,'complete')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);a=p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out=pipeline.safe_path(ROOT,a.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=True)
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);signal.signal(signal.SIGUSR1,reused.stop);signal.signal(signal.SIGTERM,reused.stop)
        with relay_dispatch():
            try:execute(out)
            except reused.Stopped as exc:mark(out,'interrupted',reason=str(exc));reused.archive(out,'interrupted')
            except Exception as exc:
                pending=any(s.get('status')=='diagnosis_incomplete' and s.get('pending_feedback',{}).get('stage')=='ledger' for s in states(out).values())
                mark(out,'diagnosis_incomplete' if pending else 'failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':main()
