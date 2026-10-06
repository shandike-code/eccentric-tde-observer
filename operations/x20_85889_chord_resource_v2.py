"""Whole-source authenticated resource probe; no map or full statistics entry."""
from contextlib import ExitStack
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
from operations import x20_85889_chord_scan as core
from operations import x20_85889_chord_resource as v1
from operations import x20_85889_chord_binding as binding

SECONDS = 1500
RSS_BYTES = 6*1024**3


def validate_claims(claims, shape):
    if (len(claims)!=6 or len(shape)!=3 or any(type(n)!=int or n<=0 for n in shape)
        or shape[0]<32 or len({str(Path(c['path']).resolve()) for c in claims})!=6
        or any(c['size_bytes']!=math.prod(shape)*8 for c in claims)
        or any(len(c['sha256'])!=64 or any(x not in '0123456789abcdef' for x in c['sha256']) for c in claims)):
        raise ValueError('six complete source claims required')


def authenticated_probe(claims, shape, guard, progress=lambda label, data: None):
    """先六个完整SHA，再固定一片，再六个完整SHA；阶段失败不推进。"""
    validate_claims(claims,shape)
    initial=[core.checked_stat(c) for c in claims]
    t=time.monotonic();before=core.hash_pass(claims,initial,guard)
    before_s=time.monotonic()-t
    progress('field-hash-before',dict(sha256=before,source_stats=initial,seconds=before_s))
    guard.check();probe=v1.probe(claims,shape,guard)
    if probe['source_stats_before']!=initial:raise ValueError('source changed between hash and probe')
    progress('probe',probe)
    t=time.monotonic();after=core.hash_pass(claims,initial,guard)
    after_s=time.monotonic()-t
    final=[core.checked_stat(c) for c in claims]
    if final!=initial or after!=before:raise ValueError('source changed after probe')
    progress('field-hash-after',dict(sha256=after,source_stats=final,seconds=after_s))
    guard.check()
    return dict(status='authenticated_resource_probe_complete_requires_review',version=2,
        probe=probe,source_claims=claims,source_stats_before=initial,source_stats_after=final,
        full_sha256_before=before,full_sha256_after=after,
        full_hash_seconds_before=before_s,full_hash_seconds_after=after_s,
        field_bytes_read=2*sum(c['size_bytes'] for c in claims)+probe['field_bytes_read'],
        full_field_sha_refreshed=True,full_field_statistics_complete=False,full_scan_authorized=False,
        physical_inference_authorized=False,strict_error_bound=False,new_maps=0,new_feedback=0,new_material=0)


def scheduler_allocation(job,text):
    tokens=dict(x.split('=',1) for x in text.split() if '=' in x)
    expected=dict(JobId=str(job),JobState='RUNNING',NumCPUs='4',NumTasks='1',NumNodes='1',
                  Partition='Students',QOS='qos_stu_default',TimeLimit='00:30:00')
    if any(tokens.get(k)!=v for k,v in expected.items()) or tokens.get('MinMemoryNode') not in ('16G','16384M'):
        raise ValueError('actual scheduler allocation differs from resource v2')
    return dict(job_id=str(job),observed_unix=time.time(),scontrol=text)


def execute(run,work):
    run=Path(run);run.mkdir(parents=False,exist_ok=False)
    started=time.monotonic();stopped=[];previous={}
    for sig in (signal.SIGUSR1,signal.SIGTERM,signal.SIGINT):
        previous[sig]=signal.signal(sig,lambda n,_frame:stopped.append(n))
    guard=core.Guard(seconds=SECONDS,rss_bytes=RSS_BYTES,stop=lambda:bool(stopped))
    try:
        v1.write_new(run/'started.json',dict(status='incomplete',version=2,started_unix=time.time(),pid=os.getpid(),
            program_seconds=SECONDS,rss_limit_bytes=RSS_BYTES))
        result=work(guard,run)
        guard.check();v1.write_new(run/'result.json',result);guard.check()
        v1.write_new(run/'finished.json',dict(status='authenticated_resource_probe_complete_requires_review',
            wall_s=time.monotonic()-started,peak_rss_bytes=core.peak_rss_bytes(),
            scheduler_terminal_verified=False,full_scan_authorized=False))
        return 0
    except BaseException as error:
        v1.write_new(run/'failure.json',dict(status='failed_or_interrupted',error_type=type(error).__name__,
            error=str(error),traceback=traceback.format_exc(),signals=stopped,wall_s=time.monotonic()-started,
            peak_rss_bytes=core.peak_rss_bytes(),scheduler_terminal_verified=False,full_scan_authorized=False))
        return 1
    finally:
        for sig,handler in previous.items():signal.signal(sig,handler)


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-commit',required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--source-review',type=Path,required=True);a=p.parse_args()
    repo=Path.cwd();v1.allocation(os.environ);v1.checkout(repo,a.expected_commit)
    run=a.run.resolve()
    if not run.is_relative_to(repo/'outputs/hpc') or run==repo/'outputs/hpc':raise ValueError('new outputs/hpc run required')
    def work(guard,out):
        from operations.x20_85889_chord_live import live_check
        raw=subprocess.check_output(['scontrol','show','job','-o',os.environ['SLURM_JOB_ID']],text=True,timeout=10)
        v1.write_new(out/'allocation.json',scheduler_allocation(os.environ['SLURM_JOB_ID'],raw))
        received=repo/binding.RUN
        protocol=json.loads((received/'accelerated/pair16/feedback_protocol.json').read_text())
        locations={k:repo/protocol['sources'][k]['path'] for k in binding.PHYSICAL_SHA}
        bound=binding.bind(repo,received,a.inventory,a.source_review,locations)
        guard.check();v1.write_new(out/'binding-before.json',bound)
        live=live_check(repo,bound,guard);v1.write_new(out/'live-before.json',live)
        claims=[dict(c,path=str(repo/c['path'])) for c in bound['field_claims']]
        result=authenticated_probe(claims,bound['shape'],guard,
            lambda name,data:v1.write_new(out/(name+'.json'),data))
        after=binding.bind(repo,received,a.inventory,a.source_review,locations)
        if after!=bound:raise ValueError('small sources changed')
        live_after=live_check(repo,after,guard)
        stable=lambda value:{k:v for k,v in value.items() if k!='environment_metadata_reads'}
        if stable(live_after)!=stable(live):raise ValueError('live dependencies changed')
        v1.write_new(out/'live-after.json',live_after)
        v1.checkout(repo,a.expected_commit);guard.check();v1.write_new(out/'binding-after.json',after)
        result.update(git_commit=a.expected_commit,git_clean_before_after=True,live_before=live,live_after=live_after,
            job_id=os.environ['SLURM_JOB_ID'],peak_rss_bytes=core.peak_rss_bytes())
        return result
    return execute(run,work)


if __name__=='__main__':raise SystemExit(main())
