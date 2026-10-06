"""Resource v2 bounded scheduler observation and explicit small-file archive, no submissions."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
NAMES={'started.json','allocation.json','binding-before.json','binding-after.json','result.json','finished.json','failure.json','live-before.json','live-after.json','field-hash-before.json','probe.json','field-hash-after.json'}


def parse_terminal(job,text):
    tokens=dict(x.split('=',1) for x in text.split() if '=' in x)
    if tokens.get('JobId')!=str(job):raise ValueError('wrong or missing scheduler job')
    state=tokens.get('JobState','').split('+')[0]
    return dict(job_id=str(job),state=state,terminal=state in TERMINAL,
                successful=state=='COMPLETED' and tokens.get('ExitCode')=='0:0',scontrol=text)


def write_new(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def archive(run,target,extra):
    """只收显式普通小文件；归档构造前全部拒绝dat、符号链接和目录。"""
    run=Path(run);target=Path(target)
    if target.exists() or target.with_suffix('.receipt.json').exists():raise FileExistsError(target)
    paths=sorted(p for p in run.iterdir() if p.name in NAMES)+list(map(Path,extra))
    blobs=[];names=set();total=0
    for p in paths:
        if p.name in names or p.is_symlink() or not p.is_file() or p.suffix not in ('.json','.out','.err','.log'):
            raise ValueError('invalid or repeated small archive member')
        n=p.stat().st_size;total+=n
        if n>32*1024**2 or total>64*1024**2:raise ValueError('small archive budget')
        with p.open('rb') as f:data=f.read(n+1)
        if len(data)!=n:raise ValueError('archive source changed')
        blobs.append((p.name,data));names.add(p.name)
    with target.open('xb') as f, tarfile.open(fileobj=f,mode='w:gz') as tar:
        for name,data in blobs:
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
            tar.addfile(info,io.BytesIO(data))
    data=target.read_bytes()
    receipt=dict(path=str(target),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
        files=[dict(path=n,size_bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in blobs],
        dat_files=0,scheduler_terminal_verified=False,
        meaning='archive integrity only; independently inspect included scheduler receipt')
    write_new(target.with_suffix('.receipt.json'),receipt)
    return receipt


def observe(job,out,seconds=2400,interval=10):
    if not str(job).isdigit() or not 0<seconds<=2400 or not 1<=interval<=30:
        raise ValueError('bounded scheduler observation parameters')
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic();i=0
    # 有限只读轮询，不调用sbatch/scancel，不恢复/追加工作。
    while time.monotonic()-start<seconds:
        stamp=time.time()
        try:
            proc=subprocess.run(['scontrol','show','job','-o',str(job)],capture_output=True,text=True,timeout=8)
            record=dict(observed_unix=stamp,returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr)
            parsed=parse_terminal(job,proc.stdout) if proc.returncode==0 else None
        except (subprocess.TimeoutExpired,ValueError) as error:
            record=dict(observed_unix=stamp,error=str(error));parsed=None
        write_new(out/f'observation-{i:04d}.json',record);i+=1
        if parsed and parsed['terminal']:
            write_new(out/'scheduler-terminal.json',dict(parsed,observed_unix=stamp));return parsed
        time.sleep(min(interval,max(0,seconds-(time.monotonic()-start))))
    write_new(out/'observation-ended.json',dict(scheduler_terminal_verified=False,status='bounded_observation_ended_unknown'))
    return None


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    w=sub.add_parser('observe');w.add_argument('job');w.add_argument('output',type=Path)
    a=sub.add_parser('archive');a.add_argument('run',type=Path);a.add_argument('target',type=Path);a.add_argument('extra',nargs='*',type=Path)
    args=p.parse_args()
    if args.command=='observe':observe(args.job,args.output)
    else:archive(args.run,args.target,args.extra)
