"""One fixed 32-group resource probe, never a full-field scientific result."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import numpy as np
from operations import x20_85889_chord_scan as core
from operations import x20_85889_chord_binding as binding


def write_new(path,data):
    with Path(path).open('x') as f:
        json.dump(data,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def probe(claims,shape,guard):
    """只读首32组两遍：一次完整统计，随后仅核此段SHA；不刷新全场SHA。"""
    mode=core.rounding_mode()
    if (len(claims)!=6 or len(shape)!=3 or any(type(n)!=int or n<=0 for n in shape)
        or shape[0]<32 or len({str(Path(c['path']).resolve()) for c in claims})!=6
        or any(c['size_bytes']!=math.prod(shape)*8 for c in claims)):
        raise ValueError('probe source shape/identity')
    before=[core.checked_stat(c) for c in claims]
    nbytes=32*math.prod(shape[1:])*8;hashes=[];fields=[];read_s=[]
    with ExitStack() as stack:
        handles=[stack.enter_context(Path(c['path']).open('rb')) for c in claims]
        if [core.signature(os.fstat(f.fileno())) for f in handles]!=before:
            raise ValueError('probe opened different source')
        for f in handles:
            guard.check();started=time.monotonic();raw=f.read(nbytes)
            read_s.append(time.monotonic()-started)
            if len(raw)!=nbytes:raise ValueError('short probe read')
            hashes.append(hashlib.sha256(raw).hexdigest())
            fields.append(np.frombuffer(raw,dtype='<f8').reshape(32,*shape[1:]))
        started=time.monotonic();row=core.slab_statistics(fields,guard.check)
        calculation_s=time.monotonic()-started;guard.check()
        # 再读的是同一固定片，不是新片/完整scan；不得提升为全场校验。
        for f,sha in zip(handles,hashes):
            guard.check();f.seek(0);raw=f.read(nbytes)
            if len(raw)!=nbytes or hashlib.sha256(raw).hexdigest()!=sha:
                raise ValueError('probe slice changed')
        if [core.signature(os.fstat(f.fileno())) for f in handles]!=before:
            raise ValueError('probe handle changed')
    after=[core.checked_stat(c) for c in claims]
    if after!=before:raise ValueError('probe path changed')
    guard.check()
    return dict(status='resource_probe_complete_requires_review',shape=list(shape),first_group=0,group_count=32,
        source_claims=claims,source_stats_before=before,source_stats_after=after,slice_sha256=hashes,
        field_bytes_read=12*nbytes,read_seconds_first_pass=read_s,calculation_seconds=calculation_s,
        peak_rss_bytes=core.peak_rss_bytes(),slab=row,
        arithmetic=dict(rounding_mode_code=mode,nmant=np.finfo(np.longdouble).nmant,
                        maxexp=np.finfo(np.longdouble).maxexp,numpy=np.__version__),
        full_field_sha_refreshed=False,full_field_statistics_complete=False,
        physical_inference_authorized=False,full_scan_authorized=False,
        new_maps=0,new_feedback=0,new_material=0,strict_error_bound=False)


def allocation(env):
    if (not env.get('SLURM_JOB_ID','').isdigit() or env.get('SLURM_CPUS_PER_TASK')!='4'
        or env.get('SLURM_NTASKS')!='1' or env.get('SLURM_MEM_PER_NODE')!='16384'):
        raise ValueError('exact 4 CPU / 16 GiB / one-task Slurm allocation required')
    if any(env.get(k)!='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')):
        raise ValueError('single process/thread configuration required')


def checkout(repo,expected):
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=repo,text=True)
    if head!=expected or dirty:raise ValueError('expected clean source commit required')
    return head


def scheduler_allocation(job,text):
    tokens=dict(x.split('=',1) for x in text.split() if '=' in x)
    expected=dict(JobId=str(job),JobState='RUNNING',NumCPUs='4',NumTasks='1',
                  Partition='Students',QOS='qos_stu_default',TimeLimit='00:15:00')
    if any(tokens.get(k)!=v for k,v in expected.items()) or tokens.get('MinMemoryNode') not in ('16G','16384M'):
        raise ValueError('actual scheduler allocation differs from frozen resource protocol')
    return dict(job_id=str(job),observed_unix=time.time(),scontrol=text)


def execute(run,work):
    """独占目录和追加式终态；错误保留，不把部分结果标作完成。"""
    run=Path(run);run.mkdir(parents=False,exist_ok=False)
    started=time.monotonic();stopped=[]
    previous={}
    for sig in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):
        previous[sig]=signal.signal(sig,lambda n,_frame:stopped.append(n))
    guard=core.Guard(seconds=600,rss_bytes=6*1024**3,stop=lambda:bool(stopped))
    write_new(run/'started.json',dict(status='incomplete',started_unix=time.time(),pid=os.getpid()))
    try:
        result=work(guard,run)
        guard.check();write_new(run/'result.json',result);guard.check()
        write_new(run/'finished.json',dict(status='resource_probe_complete_requires_review',wall_s=time.monotonic()-started,
            scheduler_terminal_verified=False,full_scan_authorized=False))
        return 0
    except BaseException as error:
        write_new(run/'failure.json',dict(status='failed_or_interrupted',error_type=type(error).__name__,error=str(error),
            traceback=traceback.format_exc(),signals=stopped,wall_s=time.monotonic()-started,
            scheduler_terminal_verified=False,full_scan_authorized=False))
        return 1
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-commit',required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--source-review',type=Path,required=True)
    a=p.parse_args();repo=Path.cwd();allocation(os.environ);checkout(repo,a.expected_commit)
    run=a.run.resolve()
    if not run.is_relative_to(repo/'outputs/hpc') or run==repo/'outputs/hpc':
        raise ValueError('new run must be under outputs/hpc')
    def work(guard,out):
        raw=subprocess.check_output(['scontrol','show','job','-o',os.environ['SLURM_JOB_ID']],text=True,timeout=10)
        write_new(out/'allocation.json',scheduler_allocation(os.environ['SLURM_JOB_ID'],raw))
        received=repo/binding.RUN
        protocol=json.loads((received/'accelerated/pair16/feedback_protocol.json').read_text())
        locations={k:repo/protocol['sources'][k]['path'] for k in binding.PHYSICAL_SHA}
        bound=binding.bind(repo,received,a.inventory,a.source_review,locations)
        guard.check();write_new(out/'binding-before.json',bound)
        claims=[dict(c,path=str(repo/c['path'])) for c in bound['field_claims']]
        result=probe(claims,bound['shape'],guard)
        # 小来源及代码也须后核；同一声明闭合，不重跑旧完整归档审计。
        after=binding.bind(repo,received,a.inventory,a.source_review,locations)
        if after!=bound:raise ValueError('small sources changed')
        checkout(repo,a.expected_commit);guard.check();write_new(out/'binding-after.json',after)
        result.update(git_commit=a.expected_commit,git_clean_before_after=True,
            job_id=os.environ['SLURM_JOB_ID'],allocation={k:os.environ[k] for k in
            ('SLURM_CPUS_PER_TASK','SLURM_NTASKS','SLURM_MEM_PER_NODE')})
        return result
    return execute(run,work)


if __name__=='__main__':raise SystemExit(main())
