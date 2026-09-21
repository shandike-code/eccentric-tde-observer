"""Read-only global defect/halo audit and Linux RSS inheritance experiment."""
from __future__ import annotations
import argparse
import gc
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot

SOURCE='outputs/hpc/composite-hybrid-20260921'


def stream_defects(paths,shape):
    """Read bounded slabs, avoiding full-file mappings in the controlling process."""
    streams=[Path(p).open('rb') for p in paths];rows=[]
    try:
        for start in range(0,shape[0],128):
            groups=min(128,shape[0]-start);n=groups*int(np.prod(shape[1:]))
            arrays=[np.fromfile(f,dtype='<f8',count=n).reshape(groups,*shape[1:]) for f in streams]
            if any(not np.isfinite(v).all() or np.any(v<0) for v in arrays):raise ValueError('invalid intensity')
            x,y,u,v=arrays;block=start//128
            if block not in (14,47) and not np.array_equal(x,u):raise ValueError('unselected input changed')
            r0=y-x;r1=v-u;change=r1-r0
            per_group=np.sum(change*change,axis=(1,2))
            rows.append({'block':block,'groups':[start,start+groups],
                'raw_squared_l2':float(np.sum(r0*r0)),'fresh_squared_l2':float(np.sum(r1*r1)),
                'raw_linf':float(np.max(abs(r0))),'fresh_linf':float(np.max(abs(r1))),
                'change_squared_l2':float(np.sum(change*change)),
                'raw_dot_change':float(np.sum(r0*change)),
                'input_change_linf':float(np.max(abs(u-x))),
                'output_change_linf':float(np.max(abs(v-y))),
                'defect_change_squared_l2_by_group':per_group.tolist(),
                'largest_change_group':start+int(np.argmax(per_group)),
                'edge_8_groups_change_share':float((per_group[:8].sum()+per_group[-8:].sum())/per_group.sum()) if groups>=16 and per_group.sum()>0 else None})
    finally:
        for f in streams:f.close()
    return summarize(rows)


def summarize(rows):
    s0=sum(x['raw_squared_l2'] for x in rows);s1=sum(x['fresh_squared_l2'] for x in rows)
    dd=sum(x['change_squared_l2'] for x in rows);rd=sum(x['raw_dot_change'] for x in rows)
    if s0<=0 or dd<=0:raise ValueError('zero norm cannot define prediction')
    unconstrained=-rd/dd
    # 有界一维二次最小化只用于预测，不写强度，也不修改正式接受门。
    choices=(0.,1.,unconstrained) if 0<unconstrained<1 else (0.,1.)
    fraction=min(choices,key=lambda t:s0+2*t*rd+t*t*dd)
    predicted=s0+2*fraction*rd+fraction*fraction*dd
    if predicted<0:raise ArithmeticError('negative squared norm from cancellation')
    return {'blocks':rows,'full_l2_ratio':float(np.sqrt(s1/s0)),
        'full_linf_ratio':max(x['fresh_linf'] for x in rows)/max(x['raw_linf'] for x in rows),
        'predicted_fraction':fraction,'unconstrained_fraction':unconstrained,
        'predicted_l2_ratio':float(np.sqrt(predicted/s0)),
        'prediction_has_fresh_map':False,'candidate_written':False,
        'sum_original_squared_l2':s0,'sum_full_squared_l2':s1,
        'sum_change_squared_l2':dd,'sum_raw_dot_change':rd}


def process_memory():
    fields={}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:','VmHWM:')):
            key,value,*_=line.split();fields[key[:-1]+'_kib']=int(value)
    fields['ru_maxrss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    fields['pid']=os.getpid();return fields


PROBE_CODE='''import json,os,resource,pathlib
fields={"pid":os.getpid(),"ru_maxrss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
for line in pathlib.Path("/proc/self/status").read_text().splitlines():
 if line.startswith(("VmRSS:","VmHWM:")):
  k,v,*_=line.split();fields[k[:-1]+"_kib"]=int(v)
print(json.dumps(fields))
'''


def child_probe(relay=False):
    code=PROBE_CODE
    if relay:code='import subprocess,sys; subprocess.run([sys.executable,"-c",'+repr(PROBE_CODE)+'],check=True)'
    return json.loads(subprocess.check_output([sys.executable,'-c',code],text=True))


def resource_probe():
    baseline={'parent':process_memory(),'child':child_probe()}
    allocation=bytearray(512*1024**2)
    for i in range(0,len(allocation),4096):allocation[i]=1
    live={'parent':process_memory(),'child':child_probe(),'relay_grandchild':child_probe(True)}
    del allocation;gc.collect()
    released={'parent':process_memory(),'child':child_probe(),'relay_grandchild':child_probe(True)}
    return {'allocated_bytes':512*1024**2,'baseline':baseline,'live':live,'released':released,
        'scope':'Synthetic memory-counter experiment; does not reclassify the old worker resource gate.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    pipeline.require_allocation(1)
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'status.json',{'status':'preparing'})
    try:
        for name in ('operations/review_composite_failure.py','operations/review_composite_failure.sbatch'):
            snap.save(name)
        plan=snap.read(SOURCE+'/declaration.json');case=plan['cases']['base']
        status=snap.read(SOURCE+'/status.json');state=snap.read(SOURCE+'/A-base-full/state.json')
        if status['status']!='failed' or len(state['history'])!=1 or state.get('active_map'):
            raise RuntimeError('expected settled failed one-map batch')
        snap.save(SOURCE+'/A-base-full/config.json',state['config_sha256'])
        snap.save(SOURCE+'/A-base-full/trial_material.npz',state['trial_sha256'])
        if state['trial_sha256']!=case['trial']['sha256']:raise RuntimeError('wrong material')
        for c in (case['config'],case['state'],case['trial']):snap.save(c['path'],c['sha256'])
        row=state['history'][0]
        claims=[case['input'],case['output']]+[{'path':row[k+'_path'],'sha256':row[k+'_sha256'],'size_bytes':pipeline.STATE_BYTES} for k in ('input','output')]
        for c in claims:
            if pipeline.verify_claims(ROOT,[c],hash_files=True):raise RuntimeError('large field SHA changed')
        blocks=[snap.read(SOURCE+f'/A-base-full/map0001/block{i:02d}.json') for i in range(76)]
        metrics=pipeline.aggregate(blocks)
        if any(metrics[k]!=row[k] for k in metrics):raise RuntimeError('aggregate differs from history')
        declaration={'environment':pipeline.environment(),'sources':claims,'shape':list(pipeline.SHAPE),
            'new_maps':0,'new_feedback_pairs':0,'source_gate_changes':False,
            'purpose':'read-only full defect localization and independent Linux resource-counter probe'}
        pipeline.write_json(out/'declaration.json',declaration)
        pipeline.write_json(out/'status.json',{'status':'resource_probe'})
        probe=resource_probe();pipeline.write_json(out/'resource_probe.json',probe)
        pipeline.write_json(out/'status.json',{'status':'streaming_full_fields'})
        result=stream_defects([ROOT/c['path'] for c in claims],pipeline.SHAPE)
        for c in claims:
            if pipeline.verify_claims(ROOT,[c],hash_files=True):raise RuntimeError('source changed during read-only audit')
        result.update(original_history=pipeline.read(ROOT/case['state']['path'])['history'][-1],
            new_history=row,reported_worker_rss_mib_values=sorted(set(x['peak_process_rss_mib'] for x in blocks)),
            actual_completed_maps=1,parent_counter_is_stale=True,resource_probe=probe,
            original_batch_accepted=False)
        pipeline.write_json(out/'result.json',result)
        import matplotlib.pyplot as plt
        x=[r['block'] for r in result['blocks']]
        maximum_original=max(r['raw_linf'] for r in result['blocks'])
        fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
        for key,label in [('raw_linf','Original defect'),('fresh_linf','Hybrid defect')]:
            axes[0].plot(x,[r[key]/maximum_original if r[key]>0 else np.nan for r in result['blocks']],'.-',label=label)
        axes[0].set_yscale('log');axes[0].set_ylabel('Block Linf / original global Linf');axes[0].legend()
        axes[1].bar(x,[(r['fresh_squared_l2']-r['raw_squared_l2'])/result['sum_original_squared_l2'] for r in result['blocks']])
        axes[1].axhline(0,color='black',linewidth=.5);axes[1].set_ylabel('Squared L2 change / original total');axes[1].set_xlabel('Frequency block (all 76 retained)')
        for ax in axes:
            for i in (14,47):ax.axvline(i,color='red',alpha=.3)
        fig.suptitle('74437: full hybrid map audit; zero defects omitted only on log axis')
        fig.tight_layout();fig.savefig(out/'defect_blocks.png',dpi=150);plt.close(fig)
        pipeline.write_json(out/'status.json',{'status':'complete','new_maps':0,'new_feedback_pairs':0})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)});raise


if __name__=='__main__':main()
