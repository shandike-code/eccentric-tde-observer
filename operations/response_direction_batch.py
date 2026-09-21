"""Fixed fresh Picard direction: zero control then two bounded material probes."""
from __future__ import annotations
import argparse
from copy import deepcopy
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
from operations.prepare_encoded_backtrack import load_arrays
from operations.audit_outer_contraction import decomposition
from operations.radiation_history_diagnostic import identical_material
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec, ground_state_material_trial_within_trust_region)

SOURCE='outputs/hpc/constrained-hybrid-20260921'
AUDIT='outputs/hpc/constrained-feedback-audit-20260921'
LIMITS={'control':2,'full':8,'half':8}
ALPHAS={'full':1/256,'half':1/512}
TERMINAL={'complete','formal_acceptance_requires_review','baseline_unstable','failed'}


def make_trial(source, direction, alpha):
    """Only direction and candidate displacement change; frozen base/dt remain."""
    if alpha not in ALPHAS.values(): raise ValueError('undeclared material amplitude')
    b=np.asarray(source['base_encoded_state']);d=np.asarray(direction)
    if b.shape!=d.shape or not np.isfinite(d).all() or not np.any(d): raise ValueError('invalid response direction')
    if float(source['relaxation'])!=0 or not np.array_equal(source['encoded_state'],b): raise ValueError('requires zero control material')
    codec=GroundStateLogSimplexCodec(len(source['temperature_k']));x=b+alpha*d;decoded=codec.decode(x)
    if not ground_state_material_trial_within_trust_region(codec,b,x,
        maximum_relative_temperature_change=.5,maximum_absolute_material_energy_increment_fraction=.25,
        maximum_population_fraction_change=.05): raise ValueError('new direction exceeds original trust region')
    result={k:np.array(v,copy=True) for k,v in source.items()}
    for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        v=np.asarray(getattr(decoded,k))
        if not np.isfinite(v).all() or np.any(v<0): raise ValueError('invalid decoded material')
        result[k]=v.copy()
    if np.any(result['temperature_k']<=0) or np.any(result['specific_material_energy_erg_g']<=0): raise ValueError('nonpositive material')
    result.update(encoded_state=x,finite_direction=d.copy(),relaxation=np.array(alpha))
    return result


def child_states(out):
    return {k:pipeline.read(out/k/'state.json') for k in LIMITS if (out/k/'state.json').exists()}


def check_budget(states):
    for name,s in states.items():
        if name not in LIMITS: raise RuntimeError('undeclared child')
        if s['status'] in driver.FAULT_STATUSES: raise RuntimeError('child fault: '+name)
        n=len(s['history'])+int(s.get('active_map') is not None)
        pairs=len(s.get('diagnostic',{}).get('rounds',[]))+int(bool(s.get('pending_feedback')))
        if n>LIMITS[name] or pairs>(1 if name=='control' else 2): raise RuntimeError('declared budget exceeded')
    return counts(states)


def mark(out,status,**extra):
    path=out/'status.json';old=pipeline.read(path) if path.exists() else {}
    if old.get('status') in TERMINAL and old['status']!=status: raise RuntimeError('terminal status immutable')
    old.update(status=status,updated_unix=time.time(),**counts(child_states(out)),**extra)
    pipeline.write_json(path,old);print(old,flush=True)


def prepare(out):
    path=out/'declaration.json'
    if path.exists():
        plan=pipeline.read(path);reused.verify(plan['pinned']);return plan
    snap=reused.Snapshot(out)
    if snap.read(SOURCE+'/status.json')['status']!='complete' or snap.read(AUDIT+'/status.json')['status']!='complete':
        raise RuntimeError('prerequisite run incomplete')
    audit=snap.read(AUDIT+'/audit.json');state=snap.read(SOURCE+'/B-base/state.json')
    cfg=snap.read(SOURCE+'/B-base/config.json',state['config_sha256'])
    source=load_arrays(snap.save(SOURCE+'/B-base/trial_material.npz',state['trial_sha256']))
    direction_path=snap.save(AUDIT+'/base-final-residual.npy');direction=np.load(direction_path,allow_pickle=False)
    rd=SOURCE+'/B-base/feedback-round1'
    record=snap.read(rd+'/round_summary.json');proto=snap.read(rd+'/baseline_control_protocol.json',record['protocol_sha256'])
    manifest=snap.read(rd+'/feedback/final_manifest.json')
    fb=load_arrays(snap.save(manifest['feedback_artifact_path'],manifest['feedback_artifact_sha256']))
    _,actual,_=reused.pair._material_response_residual(proto,fb)
    if not np.array_equal(actual,direction): raise RuntimeError('direction differs from audited physical response')
    if audit['pairs']['base']['final']['feedback_sha256']!=manifest['feedback_artifact_sha256']: raise RuntimeError('audit source mismatch')
    seed={'path':state['slots'][state['current_slot']],'sha256':state['current_sha256'],'size_bytes':pipeline.STATE_BYTES}
    reused.verify([seed]+cfg['sources'])
    cases={'base':{'trial':pipeline.claim(ROOT/SOURCE/'B-base/trial_material.npz'),
                   'config':pipeline.claim(ROOT/SOURCE/'B-base/config.json')}}
    for name,alpha in ALPHAS.items():
        folder=out/('proposal-'+name);folder.mkdir(exist_ok=False)
        trial=make_trial(source,direction,alpha);np.savez(folder/'trial_material.npz',**trial)
        identical_material(trial,load_arrays(folder/'trial_material.npz'))
        newcfg=deepcopy(cfg);newcfg.update(candidate_relaxation=alpha,
            physics_scope='fresh audited Picard direction; fixed physical base/dt and original acceptance denominator')
        pipeline.write_json(folder/'config.json',newcfg)
        cases[name]={'trial':pipeline.claim(folder/'trial_material.npz'),'config':pipeline.claim(folder/'config.json')}
    code=[pipeline.claim(p) for folder in ('operations','diagnostics') for p in sorted((ROOT/folder).iterdir()) if p.suffix in ('.py','.sbatch')]
    pinned=list(snap.records.values())+cfg['sources']+code+[seed]+[v for c in cases.values() for v in c.values()]
    plan={'environment':pipeline.environment(),'cases':cases,'code':code,'pinned':pinned,'seed':seed,
        'direction':pipeline.claim(ROOT/AUDIT/'base-final-residual.npy'),'alphas':ALPHAS,'limits':LIMITS,
        'maximum_maps':18,'maximum_pairs':5,'feedback_cadence':{'control':2,'full':4,'half':4},
        'scientific_change':'new Picard direction from audited zero-control final response; not backtracking the old direction',
        'physical_dt_changed':False,'formal_baseline_changed':False,'gates_relaxed':False,
        'automatic_resubmit':False,'accepted_column':False}
    reused.immutable(path,plan);return plan


def round_review(out,name,state):
    """Compare every completed candidate pair with both new zero-control endpoints."""
    record=state['diagnostic']['rounds'][-1];rd=ROOT/Path(record['ledger']).parent
    report=rd/'fresh_control_comparison.json'
    if report.exists(): return pipeline.read(report)
    controls={};mass=None
    for endpoint in ('previous','final'):
        folder=out/'control/feedback-round1';proto=pipeline.read(folder/'baseline_control_protocol.json')
        _,r,ctx=reused.pair._material_response_residual(proto,load_arrays(folder/(endpoint+'_feedback.npz')))
        controls[endpoint]=r;mass=ctx['cell_mass']
    proto=pipeline.read(rd/'feedback_protocol.json');comparison={}
    for endpoint in ('previous','final'):
        try:_,r,ctx=reused.pair._material_response_residual(proto,load_arrays(rd/(endpoint+'_feedback.npz')))
        except reused.pair.PhysicalDomainError as exc:
            comparison[endpoint]={'physical_domain_error':str(exc)};continue
        if not np.array_equal(ctx['cell_mass'],mass): raise RuntimeError('mass measure changed')
        comparison[endpoint]={c:decomposition(b,r,mass) for c,b in controls.items()}
    result={'name':name,'round':record['round'],'formal_accepted':record['accepted'],
            'comparisons':comparison,'formal_denominator_replaced':False,'true_inner_error_bound':False}
    reused.immutable(report,result);return result


def control_check(out,control,book):
    result={'inner_and_feedback_stability_pass':pipeline.pair_ready(control['history'],1e-4)
        and all(v['ratio']<1e-3 for v in book['heating_stability']['metrics'].values()),
        'physical_response_pass':True,'true_error_bound':False,'response_failures':{}}
    folder=out/'control/feedback-round1';proto=pipeline.read(folder/'baseline_control_protocol.json')
    for endpoint in ('previous','final'):
        try:reused.pair._material_response_residual(proto,load_arrays(folder/(endpoint+'_feedback.npz')))
        except reused.pair.PhysicalDomainError as exc:
            result['physical_response_pass']=False;result['response_failures'][endpoint]=str(exc)
    return result


def process_case(out,name,label,plan):
    folder,cfg,state=reused.child(out,name,label,plan['seed'],plan);path=folder/'state.json'
    cadence=2 if name=='control' else 4
    while True:
        check_budget(child_states(out));reused.checkpoint()
        if state.get('pending_feedback'):
            reused.settle(folder,cfg,state,path,label);mark(out,'feedback',current_case=name)
            if name!='control': round_review(out,name,state)
            reused.archive(out,name+'-round'+str(len(state['diagnostic']['rounds'])))
        rounds=state.get('diagnostic',{}).get('rounds',[])
        if name!='control' and rounds: round_review(out,name,state)
        if state['status']=='one_material_trial_accepted': return 'accepted'
        if name!='control' and rounds:
            rd=ROOT/Path(rounds[-1]['ledger']).parent
            summary=pipeline.read(rd/'feedback_summary.json')
            if summary.get('material_response_failures'): return 'physical_domain_rejected'
        n=len(state['history'])
        if n and n%cadence==0 and len(rounds)<n//cadence:
            # A pair evaluates exactly the last two measured input states. Failed
            # inner gates remain visible in its formal verdict; no endpoint substitution.
            driver.start_round(folder,cfg,state,path);continue
        if n>=LIMITS[name]: return 'budget_complete'
        mark(out,'mapping',current_case=name)
        if not driver.run_one_map(folder,cfg,state,path): raise reused.Stopped('partial map retained')
        check_budget(child_states(out))


def execute(out):
    if (out/'status.json').exists() and pipeline.read(out/'status.json')['status'] in TERMINAL:return
    reused.LIMITS=LIMITS
    mark(out,'preparing');plan=prepare(out)
    if __import__('shutil').disk_usage(out).free<12*pipeline.STATE_BYTES: raise RuntimeError('insufficient space for retained runs')
    # Pending rounds always precede any new case or map, also after interruption.
    for name,state in child_states(out).items():
        if state.get('pending_feedback'):
            folder=out/name;reused.settle(folder,pipeline.read(folder/'config.json'),state,folder/'state.json','base' if name=='control' else name)
    process_case(out,'control','base',plan)
    control=pipeline.read(out/'control/state.json')
    book=pipeline.read(out/'control/feedback-round1/material_energy_ledger.json')
    check=control_check(out,control,book)
    # This is a necessary precision screen, not a claim of a solved baseline.
    reused.immutable(out/'control-check.json',check)
    if not check['inner_and_feedback_stability_pass'] or not check['physical_response_pass']:
        mark(out,'baseline_unstable');reused.archive(out,'baseline-unstable');return
    for name in ALPHAS:
        result=process_case(out,name,name,plan)
        if result=='accepted':
            mark(out,'formal_acceptance_requires_review',candidate=name);reused.archive(out,'accepted-review');return
    mark(out,'complete',accepted_material_step=False);reused.archive(out,'complete')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);args=p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=True)
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        signal.signal(signal.SIGUSR1,reused.stop);signal.signal(signal.SIGTERM,reused.stop)
        with relay_dispatch():
            try:execute(out)
            except reused.Stopped as exc:mark(out,'interrupted',reason=str(exc));reused.archive(out,'interrupted')
            except Exception as exc:
                pending=any(s.get('status')=='diagnosis_incomplete' and s.get('pending_feedback',{}).get('stage')=='ledger' for s in child_states(out).values())
                mark(out,'diagnosis_incomplete' if pending else 'failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':main()
