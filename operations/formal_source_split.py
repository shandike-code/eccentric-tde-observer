"""Bounded read-only source decomposition on a retained failed feedback state.

Replays the original formal diagnostic, splits its linear collision source,
and evaluates a beta=0 diagnostic control. No map or material step is advanced.
"""
from contextlib import contextmanager
import argparse
import fcntl
import gc
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'hpc')]
import pipeline
from operations import composite_hybrid_batch as reused
from operations.prepare_encoded_backtrack import load_arrays
from scripts import phase7b9_formal_feedback_pair_adapter as pair
from scripts import phase7b7j_second_assembled_feedback as native
from scripts.phase7b5p_isolated_resource_profile import ru_maxrss_to_bytes
SOURCE='outputs/hpc/step16-backtrack-20260923/full/feedback-round1'
FIELDS={'absorption':'true_absorption','emission':'thermal_emissivity','scattering':'scattering'}
KEYS={'rate':'rate_material_heating_erg_s_cm3','direct':'direct_comoving_material_heating_erg_s_cm3','formal':'inverse_lab_four_force_material_heating_erg_s_cm3'}
STORED={'rate':'source_rate_heating_erg_s_cm3','direct':'source_direct_heating_erg_s_cm3','formal':'source_formal_heating_erg_s_cm3'}
STOP=False


def component_fields(fields, component):
    if component not in FIELDS:raise ValueError('undeclared source component')
    result=dict(fields)
    for key in FIELDS.values():
        if key!=FIELDS[component]:result[key]=np.zeros_like(fields[key])
    return result


@contextmanager
def component_operator(component):
    module=native.phase7b7f.phase7b7e;original=module._local_fields
    module._local_fields=lambda *args:component_fields(original(*args),component)
    try:yield
    finally:module._local_fields=original


def stop(*args):
    global STOP
    STOP=True


def worker(plan_path, block, out):
    started=time.monotonic();plan=pipeline.read(plan_path)
    # Parent hashes the 9.41GiB source once inside its allocation. Workers verify
    # small immutable inputs and reproduce the original block output exactly.
    reused.verify([c for c in plan['claims'] if not c['path'].endswith('.dat')])
    protocol=pipeline.read(ROOT/SOURCE/'feedback_protocol.json')
    template=pair._validate_worker_template_sources(protocol)
    adapted=pair.adapt_phase7b7j_worker_protocol(protocol,template,'final')
    context=native.phase7b7f.phase7b7e.phase7b5x._context(adapted)
    updated=native.phase7b7i._second_full_material(adapted)
    shape=native.phase7b7i._shape(adapted)
    mapped=np.memmap(ROOT/adapted['sources']['mapped_radiation_state']['path'],mode='r',dtype=np.float64,shape=shape)
    original=native.phase7b7f.assembled_block_diagnostics(adapted,context,updated,mapped,block)
    row=plan['blocks'][str(block)];stored=load_arrays(ROOT/row['partial_path'])
    for k,key in KEYS.items():
        if not np.array_equal(original[key],stored[STORED[k]]):raise RuntimeError('original source did not replay bitwise: '+k)
    result={'original_'+k:np.array(original[key]) for k,key in KEYS.items()}
    for component in FIELDS:
        with component_operator(component):
            part=native.phase7b7f.assembled_block_diagnostics(adapted,context,updated,mapped,block)
        for k,key in KEYS.items():result[component+'_'+k]=np.array(part[key])
        del part;gc.collect()
    closure={}
    for k in KEYS:
        pieces=[result[c+'_'+k] for c in FIELDS];scale=max(float(np.max(sum(np.abs(v) for v in pieces))),float(np.max(np.abs(result['original_'+k]))))
        error=float(np.max(np.abs(sum(pieces)-result['original_'+k])))
        closure[k]=error/scale if scale>0 else error
        if closure[k]>1e-12:raise RuntimeError('linear source split failed roundoff check')
    zero=dict(context);zero['beta']=np.zeros_like(context['beta']);zero['parent_beta']=np.zeros_like(context['parent_beta'])
    control=native.phase7b7f.assembled_block_diagnostics(adapted,zero,updated,mapped,block)
    for k,key in KEYS.items():result['beta0_'+k]=np.array(control[key])
    if not all(np.all(np.isfinite(v)) for v in result.values()):raise RuntimeError('nonfinite source diagnostic')
    rss=ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,sys.platform)/1024**2
    if rss>=6144:raise RuntimeError('native memory gate failed')
    file=out/f'block{block:02d}.npz';np.savez(file,**result)
    report={'block':block,'original_source_bitwise_replayed':True,'linear_closure_error':closure,'native_peak_mib':rss,'wall_s':time.monotonic()-started,'arrays':pipeline.claim(file)}
    reused.immutable(out/f'block{block:02d}.json',report)


def aggregate(out,plan):
    fb=load_arrays(ROOT/plan['feedback']['path']);width=fb['subcell_width_cm'];combined={};rows=[];reports=[]
    for block in plan['selected_blocks']:
        report=pipeline.read(out/f'block{block:02d}.json');reused.verify([report['arrays']]);a=load_arrays(ROOT/report['arrays']['path']);reports.append(report)
        if not combined:combined={k:np.zeros_like(v) for k,v in a.items()}
        for k,v in a.items():combined[k]+=v
        rows.append({'block':block,**{c+'_signed_rate_minus_formal':float(np.sum(width*(a[c+'_rate']-a[c+'_formal']))) for c in ('original',*FIELDS,'beta0')}})
    all_blocks=plan['selected_blocks']==list(range(76))
    if all_blocks:
        for k in KEYS:
            if not np.array_equal(combined['original_'+k],fb[STORED[k]]):raise RuntimeError('full replay differs from original assembly')
    data=out/'combined.npz';np.savez(data,**combined,subcell_width_cm=width)
    metrics={}
    for c in ('original',*FIELDS,'beta0'):
        rate,formal=combined[c+'_rate'],combined[c+'_formal'];r,f=float(np.sum(width*rate)),float(np.sum(width*formal));scale=max(abs(r),abs(f))
        metrics[c]={'rate_integral':r,'formal_integral':f,'signed_difference':r-f,'difference_volume_l1':float(np.sum(width*np.abs(rate-formal))),'net_relative_difference':abs(r-f)/scale if scale>0 else None}
    receipts=[pipeline.read(out/f'block{i:02d}.process.json') for i in plan['selected_blocks']]
    if not all(r['returncode']==0 and r['memory_guard_passed'] for r in receipts):raise RuntimeError('independent worker memory/return gate failed')
    summary={'status':'complete','all_76_blocks':all_blocks,'selected_blocks':plan['selected_blocks'],'metrics':metrics,'block_contributions':rows,'sources':plan['claims'],'arrays':pipeline.claim(data),'original_source_bitwise_replayed':True,'max_native_mib':max(r['native_peak_mib'] for r in reports),'max_proc_kib':max(r['native_observed_peak_kib'] for r in receipts),'max_linearity_error':max(v for r in reports for v in r['linear_closure_error'].values()),'beta0_is_diagnostic_counterfactual':True,'physical_time_advanced':False,'formal_gates_changed':False,'material_step_accepted':False}
    reused.immutable(out/'summary.json',summary)
    return summary


def run(out,workers,pilot):
    pipeline.require_allocation(workers)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    if workers not in (1,16) or (pilot and workers!=1):raise ValueError('undeclared resource mode')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for s in (signal.SIGUSR1,signal.SIGTERM):signal.signal(s,stop)
        pipeline.write_json(out/'status.json',{'status':'preparing'})
        try:
            path=ROOT/SOURCE/'feedback_protocol.json';proto=pipeline.read(path);manifest=pipeline.read(ROOT/SOURCE/'feedback/final_manifest.json')
            state=pipeline.read(ROOT/'outputs/hpc/step16-backtrack-20260923/full/state.json')
            pending=state['pending_feedback']
            if manifest['status']!='gate_failed' or manifest['protocol_sha256']!=pipeline.sha256(path) or pending['protocol_sha256']!=manifest['protocol_sha256']:raise RuntimeError('failed source lineage changed')
            if manifest['state_sha256']!=proto['sources']['final_radiation']['sha256'] or manifest['state_path']!=proto['sources']['final_radiation']['path']:raise RuntimeError('radiation endpoint changed')
            rows=manifest['completed_blocks']
            if [r['block_index'] for r in rows]!=list(range(76)):raise RuntimeError('incomplete source frequency ownership')
            cfg_path=ROOT/'outputs/hpc/step16-backtrack-20260923/full/config.json'
            cfg=pipeline.read(cfg_path)
            if pipeline.sha256(cfg_path)!=state['config_sha256']:raise RuntimeError('source configuration changed')
            claims=list(proto['sources'].values())+[pipeline.claim(path),pipeline.claim(ROOT/SOURCE/'feedback/final_manifest.json'),pipeline.claim(cfg_path)]+cfg['sources']
            claims += [pipeline.claim(ROOT/r['partial_path']) for r in rows]
            for c,r in zip(claims[-76:],rows):
                if c['sha256']!=r['partial_sha256']:raise RuntimeError('partial source changed')
            feedback=pipeline.claim(ROOT/manifest['feedback_artifact_path'])
            if feedback['sha256']!=manifest['feedback_artifact_sha256']:raise RuntimeError('feedback changed')
            claims.append(feedback)
            claims += [pipeline.claim(f) for d in ('operations','diagnostics') for f in sorted((ROOT/d).iterdir()) if f.suffix in ('.py','.sbatch')]
            reused.verify(claims);pair._validate_worker_template_sources(proto)
            selected=[24] if pilot else list(range(76))
            if not pilot:
                prior=ROOT/'outputs/hpc/formal-source-split-pilot-20260923/summary.json';r=pipeline.read(prior)
                if r['status']!='complete' or r['selected_blocks']!=[24] or not r['original_source_bitwise_replayed']:raise RuntimeError('native pilot not passed')
                reused.verify(r['sources']);claims.append(pipeline.claim(prior))
            plan={'environment':pipeline.environment(),'claims':claims,'feedback':feedback,'selected_blocks':selected,'blocks':{str(r['block_index']):r for r in rows},'workers':workers,'maximum_block_diagnostics':len(selected),'source_calls_per_block':5,'new_maps':0,'new_material_steps':0}
            reused.immutable(out/'declaration.json',plan)
            for offset in range(0,len(selected),workers):
                if STOP:
                    pipeline.write_json(out/'status.json',{'status':'interrupted','completed_blocks':offset});return
                processes=[]
                for block in selected[offset:offset+workers]:
                    command=[sys.executable,str(ROOT/'operations/native_worker_relay.py'),'--receipt',str(out/f'block{block:02d}.process.json'),'--',sys.executable,str(Path(__file__).resolve()),'--worker',str(block),'--run',str(out.relative_to(ROOT))]
                    processes.append(subprocess.Popen(command,cwd=ROOT))
                codes=[p.wait() for p in processes]
                if any(codes):raise RuntimeError('diagnostic worker failed: '+str(codes))
                pipeline.write_json(out/'status.json',{'status':'running','completed_blocks':min(offset+workers,len(selected))})
            reused.verify(claims);aggregate(out,plan);pipeline.write_json(out/'status.json',{'status':'complete','completed_blocks':len(selected),'new_maps':0,'material_step_accepted':False})
        except Exception as exc:
            pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)});raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--workers',type=int,default=16);p.add_argument('--pilot',action='store_true');p.add_argument('--worker',type=int);a=p.parse_args();out=pipeline.safe_path(ROOT,a.run)
    if a.worker is not None:worker(out/'declaration.json',a.worker,out)
    else:run(out,a.workers,a.pilot)

if __name__=='__main__':main()
