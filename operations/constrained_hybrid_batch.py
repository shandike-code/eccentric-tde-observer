"""Global Linf-constrained radiation steps; seven maps and two pairs at most."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from diagnostics import interval_diagnostic as driver
from operations import composite_hybrid_batch as reused
from operations import constrained_hybrid_fields as fields
from operations.composite_hybrid_audit import checks as original_checks

SOURCE='outputs/hpc/composite-hybrid-20260921'
LIMITS={'B-base':2,'A-base-half':1,'P-trial':1,'B-trial':2,'A-trial-half':1}
TERMINAL={'complete','science_rejected','failed'}


class RelayProcesses:
    def __init__(self,original):self.original=original
    def __getattr__(self,name):return getattr(self.original,name)
    def Popen(self,command,*args,**kwargs):
        if isinstance(command,(list,tuple)):
            flags=[flag for flag in ('--report','--worker-report') if flag in command]
            if flags:
                report=Path(command[command.index(flags[0])+1])
                receipt=report.with_suffix(f'.process-{time.time_ns()}.json')
                command=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),
                    '--receipt',str(receipt),'--',*command]
        return self.original.Popen(command,*args,**kwargs)


@contextmanager
def relay_dispatch():
    original_pipeline=pipeline.subprocess;original_pair=reused.pair.subprocess
    pipeline.subprocess=RelayProcesses(original_pipeline)
    reused.pair.subprocess=RelayProcesses(original_pair)
    try:yield
    finally:pipeline.subprocess=original_pipeline;reused.pair.subprocess=original_pair


def counts(states):
    """Count even failed work; fault validation must not erase accounting."""
    completed=sum(len(s['history']) for s in states.values())
    active=sum(s.get('active_map') is not None for s in states.values())
    pairs=sum(len(s.get('diagnostic',{}).get('rounds',[])) for s in states.values())
    pending=sum(bool(s.get('pending_feedback')) for s in states.values())
    return {'completed_maps':completed,'active_maps':active,'completed_pairs':pairs,'pending_pairs':pending}


def validate_budget(states):
    used=counts(states)
    if used['completed_maps']+used['active_maps']>7 or used['completed_pairs']+used['pending_pairs']>2:
        raise RuntimeError('batch total budget exceeded')
    for name,state in states.items():
        if name not in LIMITS:raise RuntimeError('undeclared child')
        if len(state['history'])+int(state.get('active_map') is not None)>LIMITS[name]:raise RuntimeError('child map budget exceeded')
        pair_count=len(state.get('diagnostic',{}).get('rounds',[]))+int(bool(state.get('pending_feedback')))
        if pair_count>int(name in ('B-base','B-trial')):raise RuntimeError('child pair budget exceeded')
        if state['status'] in driver.FAULT_STATUSES:raise RuntimeError('child resource/program fault: '+name)
    return used


def states(out):
    return {name:pipeline.read(out/name/'state.json') for name in LIMITS if (out/name/'state.json').exists()}


def mark(out,status,**extra):
    path=out/'status.json';old=pipeline.read(path) if path.exists() else {}
    if old.get('status') in TERMINAL and old['status']!=status:raise RuntimeError('terminal status immutable')
    old.update(status=status,updated_unix=time.time(),**counts(states(out)),**extra)
    pipeline.write_json(path,old);print(old,flush=True)


def setup(out):
    reused.LIMITS=LIMITS
    resuming=(out/'declaration.json').exists()
    plan=reused.prepare(out)
    if resuming:
        for case in plan['cases'].values():
            reused.verify(pipeline.read(ROOT/case['config']['path'])['sources'])
    source_plan=pipeline.read(ROOT/SOURCE/'declaration.json')
    if source_plan['cases']!=plan['cases']:raise RuntimeError('correction basis differs')
    corrections={}
    for label in ('base','trial'):
        corrections[label]={}
        for block in fields.BLOCKS:
            receipt=ROOT/SOURCE/f'{label}-block{block:02d}-receipt.json'
            r=pipeline.read(receipt);reused.verify([pipeline.claim(receipt),r['report'],*r['arrays'].values()])
            if not r['passed']:raise RuntimeError('old local correction not eligible')
            corrections[label][str(block)]={'receipt':pipeline.claim(receipt),**r}
    source=ROOT/SOURCE/'A-base-full/state.json';s=pipeline.read(source)
    if s['status']!='resource_gate_failed' or len(s['history'])!=1 or s.get('active_map'):
        raise RuntimeError('base diagnostic source no longer matches failed settled map')
    if s['trial_sha256']!=plan['cases']['base']['trial']['sha256']:
        raise RuntimeError('base diagnostic map uses a different material')
    reused.verify([{'path':SOURCE+'/A-base-full/config.json','sha256':s['config_sha256'],
                    'size_bytes':(ROOT/SOURCE/'A-base-full/config.json').stat().st_size},
                   {'path':SOURCE+'/A-base-full/trial_material.npz','sha256':s['trial_sha256'],
                    'size_bytes':(ROOT/SOURCE/'A-base-full/trial_material.npz').stat().st_size}])
    row=s['history'][0]
    base_pair={k:{'path':row[k+'_path'],'sha256':row[k+'_sha256'],'size_bytes':pipeline.STATE_BYTES} for k in ('input','output')}
    reused.verify(list(base_pair.values()))
    declaration={'controls':fields.CONTROL,'child_limits':LIMITS,'maximum_maps':7,'maximum_pairs':2,
        'inherited_maximum_maps_cap':plan['maximum_maps'],
        'source_declaration':pipeline.claim(ROOT/SOURCE/'declaration.json'),
        'corrections':corrections,'base_diagnostic_pair':base_pair,'base_source_state':pipeline.claim(source),
        'base_trial_sha256':s['trial_sha256'],'root_declaration':pipeline.claim(out/'declaration.json'),
        'base_failed_map_is_diagnostic_only':True,'feedback_input_policy':'selected original-map input plus its once-mapped output, each explicitly measured',
        'worker_launch':'native_worker_relay; unchanged native resource guard plus independent proc samples'}
    reused.immutable(out/'constrained_declaration.json',declaration)
    plan=deepcopy(plan);plan['code'].append(pipeline.claim(out/'constrained_declaration.json'))
    return plan,declaration


def persist_claim(path,writer):
    receipt=Path(str(path)+'.json')
    if receipt.exists():
        claim=pipeline.read(receipt);reused.verify([claim]);return claim
    if path.exists():raise RuntimeError('field exists without committed receipt; preserve for recovery audit')
    writer();claim=pipeline.claim(path);reused.immutable(receipt,claim);return claim


def raw_pair(out,label,plan,decl):
    if label=='base':return decl['base_diagnostic_pair']
    path=out/'trial-original-full.dat';case=plan['cases'][label]
    replacements={i:ROOT/decl['corrections'][label][str(i)]['arrays']['candidate']['path'] for i in fields.BLOCKS}
    seed=persist_claim(path,lambda:fields.full_endpoint(ROOT/case['input']['path'],replacements,path,pipeline.SHAPE))
    folder,cfg,state=run_maps(out,'P-trial',label,seed,plan,1)
    row=state['history'][0]
    return {k:{'path':row[k+'_path'],'sha256':row[k+'_sha256'],'size_bytes':pipeline.STATE_BYTES} for k in ('input','output')}


def run_maps(out,name,label,seed,plan,target):
    if not 0<=target<=LIMITS[name]:raise RuntimeError('invalid per-call budget')
    validate_budget(states(out));reused.checkpoint()
    folder,cfg,state=reused.child(out,name,label,seed,plan);path=folder/'state.json'
    reused.settle(folder,cfg,state,path,label)
    while len(state['history'])<target:
        validate_budget(states(out));reused.checkpoint()
        completed=driver.run_one_map(folder,cfg,state,path)
        # 即使map完成后资源门失败，也先刷新真实工作量再抛异常。
        current=pipeline.read(out/'status.json')['status'];mark(out,current)
        validate_budget(states(out))
        if not completed:raise reused.Stopped('partial map committed')
    return folder,cfg,state


def selection(out,label,plan,pair):
    case=plan['cases'][label]
    claims=[case['input'],case['output'],pair['input'],pair['output']]
    receipt=out/(label+'-selection.json')
    if receipt.exists():
        report=pipeline.read(receipt)
        if report['sources']!=claims:raise RuntimeError('selection basis changed')
        reused.verify(claims);return report
    native,_,_,context=pipeline.configure_native(pipeline.read(ROOT/case['config']['path']),ROOT/case['input']['path'])
    edges=context['stencil'].active_lab_edge_hz;mu=context['mu'];weight=context['weight']
    widths=np.diff(edges)
    def flux(a,start):return native.base._block_flux(a,mu,weight,widths[start:start+len(a)])
    original=pipeline.read(ROOT/case['state']['path'])['history'][-1]
    result=fields.scan([ROOT/c['path'] for c in claims],pipeline.SHAPE,flux,original)
    reused.verify(claims);result['sources']=claims
    reused.immutable(receipt,result);return result


def selected_fields(out,label,case,pair,choice):
    path=out/(label+'-selected.dat');fraction=choice['fraction']
    full=persist_claim(path,lambda:fields.write_convex(ROOT/case['input']['path'],ROOT/pair['input']['path'],path,fraction,pipeline.SHAPE))
    half_path=out/(label+'-half.dat')
    half=persist_claim(half_path,lambda:fields.write_convex(ROOT/case['input']['path'],ROOT/full['path'],half_path,.5,pipeline.SHAPE))
    return full,half


def validate_selected(out,label,plan,pair,choice):
    case=plan['cases'][label];full,half=selected_fields(out,label,case,pair,choice)
    a=run_maps(out,'B-'+label,label,full,plan,1)[2]['history'][0]
    b=run_maps(out,'A-'+label+'-half',label,half,plan,1)[2]['history'][0]
    report_path=out/(label+'-validated.json')
    claims=[case['input'],case['output']]
    for row in (a,b):
        claims.extend({'path':row[k+'_path'],'sha256':row[k+'_sha256'],'size_bytes':pipeline.STATE_BYTES} for k in ('input','output'))
    reused.verify(claims)
    if report_path.exists():
        report=pipeline.read(report_path)
        if report['sources']!=claims:raise RuntimeError('validation basis changed')
        return report
    field=fields.validate([ROOT/c['path'] for c in claims],pipeline.SHAPE)
    original=pipeline.read(ROOT/case['state']['path'])['history'][-1]
    gate=original_checks(field,original,a,b)
    result={'selection':choice,'sources':claims,'full_field':field,'checks':gate,
            'passed':all(gate.values()),'full_seed':full,'half_seed':half,'rows':[a,b]}
    reused.verify(claims);reused.immutable(report_path,result);reused.archive(out,label+'-validated')
    return result


def settle_all(out):
    for label in ('base','trial'):
        path=out/('B-'+label)/'state.json'
        if path.exists():
            state=pipeline.read(path)
            if state.get('pending_feedback'):
                reused.settle(path.parent,pipeline.read(path.parent/'config.json'),state,path,label)


def continue_feedback(out,plan,validated):
    for label in ('base','trial'):
        folder,cfg,state=run_maps(out,'B-'+label,label,validated[label]['full_seed'],plan,2)
        if state.get('diagnostic',{}).get('rounds'):continue
        if not pipeline.pair_ready(state['history'],1e-4):return False
        reused.checkpoint();driver.start_round(folder,cfg,state,folder/'state.json')
        mark(out,'feedback');validate_budget(states(out))
        reused.settle(folder,cfg,state,folder/'state.json',label)
        mark(out,'feedback');reused.archive(out,label+'-feedback')
    return True


def execute(out):
    if (out/'status.json').exists() and pipeline.read(out/'status.json')['status'] in TERMINAL:return
    mark(out,'preparing');plan,decl=setup(out);settle_all(out);validate_budget(states(out))
    if __import__('shutil').disk_usage(out).free<24*pipeline.STATE_BYTES:raise RuntimeError('insufficient retained-state disk space')
    validated={}
    for label in ('base','trial'):
        mark(out,'selecting-'+label);reused.checkpoint();pair=raw_pair(out,label,plan,decl)
        choice=selection(out,label,plan,pair);reused.archive(out,label+'-selection')
        if not choice['feasible']:
            mark(out,'science_rejected',reason=label+' has no declared admissible predicted step');reused.archive(out,'rejected');return
        mark(out,'validating-'+label);validated[label]=validate_selected(out,label,plan,pair,choice)
        if not validated[label]['passed']:
            mark(out,'science_rejected',reason=label+' fresh full/half original-map validation failed');reused.archive(out,'rejected');return
    mark(out,'continuation-and-feedback')
    if not continue_feedback(out,plan,validated):
        mark(out,'science_rejected',reason='two consecutive original inner/boundary gates failed');reused.archive(out,'rejected');return
    mark(out,'ledger-comparison')
    try:reused.stage_c(out,plan)
    except reused.pair.PhysicalDomainError as exc:
        reused.immutable(out/'C-domain-rejection.json',{'error':str(exc),
            'accepted_material_step':False,'ledgers_retained':True,'residual_comparison_complete':False})
        mark(out,'science_rejected',reason='original material response outside physical domain')
        reused.archive(out,'response-domain-rejected');return
    mark(out,'complete',accepted_material_step=pipeline.read(out/'B-trial/state.json')['status']=='one_material_trial_accepted')
    reused.archive(out,'complete')


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
                pending=any(s.get('status')=='diagnosis_incomplete' and s.get('pending_feedback',{}).get('stage')=='ledger' for s in states(out).values())
                mark(out,'diagnosis_incomplete' if pending else 'failed',error=repr(exc));reused.archive(out,'failed');raise


if __name__=='__main__':main()
