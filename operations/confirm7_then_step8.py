"""Confirm accepted step seven (1/128), then conditionally take one eighth step.

The preparation body retains numbered_confirmation_step's source replay and
lineage checks. Only the explicit accepted amplitude contract is specialized.
"""
from contextlib import contextmanager
from dataclasses import asdict
import argparse
import fcntl
import os
from pathlib import Path
import signal
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
import pipeline
from operations import numbered_confirmation_step as stage
from operations import accepted_step_confirmation as confirm
from operations import response_direction_batch as batch
from operations import composite_hybrid_batch as reused
from operations.prepare_encoded_backtrack import load_arrays
from operations.constrained_hybrid_batch import relay_dispatch
SOURCE='outputs/hpc/step7-amplitude-20260922'
ACCEPTED_INDEX=7
ACCEPTED_ALPHA=1/128
FORMAL_SOURCE=None
NEXT_ALPHAS={'full':1/128,'half':1/256}


def validate_accepted_material(base,trial):
    if (float(base['relaxation'])!=0 or float(trial['relaxation'])!=ACCEPTED_ALPHA
        or not np.array_equal(base['encoded_state'],base['base_encoded_state'])
        or not np.array_equal(base['encoded_state'],trial['base_encoded_state'])
        or not np.array_equal(trial['encoded_state'],trial['base_encoded_state']+ACCEPTED_ALPHA*trial['finite_direction'])):
        raise RuntimeError('wrong accepted material amplitude or displacement')


def prepare_confirmation(out):
    p=out/'declaration.json'
    if p.exists():
        plan=pipeline.read(p);reused.verify(plan['pinned'])
        if (plan['source']!=SOURCE or plan['accepted_outer_step_index']!=ACCEPTED_INDEX
            or plan['formal_source']!=FORMAL_SOURCE or plan['accepted_alpha']!=ACCEPTED_ALPHA):raise RuntimeError('confirmation source changed')
        return plan
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
    validate_accepted_material(b,t)
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
          'accepted_alpha':ACCEPTED_ALPHA,'accepted_outer_step_index':ACCEPTED_INDEX,'source':SOURCE,'formal_source':FORMAL_SOURCE,
          'scope':'source replay, two-map control, fixed candidate +2 then +4 maps; no new outer step'}
    reused.immutable(p,plan);return plan

@contextmanager
def adapters():
    previous=stage.prepare_confirmation,batch.ALPHAS
    stage.prepare_confirmation=prepare_confirmation
    batch.ALPHAS=dict(NEXT_ALPHAS)
    try:yield
    finally:stage.prepare_confirmation,batch.ALPHAS=previous


def execute(out):
    global FORMAL_SOURCE
    stage.configure(SOURCE,ACCEPTED_INDEX)
    FORMAL_SOURCE=stage.FORMAL_SOURCE
    d=pipeline.read(ROOT/SOURCE/'amplitude-probe-decision.json')
    if (d.get('outer_step_index')!=7 or d.get('alphas')!=NEXT_ALPHAS
        or d.get('formal_finite_step_accepted') is not True
        or d.get('fresh_control_corroborated') is not True):
        raise RuntimeError('source amplitude decision is not corroborated')
    with adapters():stage.execute(out)


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
                stage.mark(out,'interrupted',reason=str(exc));reused.archive(out,'interrupted')
            except Exception as exc:
                states=list(confirm.states(out/'confirmation').values())+list(batch.child_states(out/'next-step').values())
                pending=any(s.get('status')=='diagnosis_incomplete' and (s.get('pending_feedback') or {}).get('stage')=='ledger' for s in states)
                stage.mark(out,'diagnosis_incomplete' if pending else 'failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':main()
