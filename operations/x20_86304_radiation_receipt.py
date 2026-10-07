"""86304 resource bounded scheduler observation and explicit small-file archive, no submissions."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import time

TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'}
NAMES={'identity-before.json','identity-after.json','started.json','allocation.json','source-before.json','source-after.json','result.json','finished.json','failure.json','field-hash-before.json','probe.json','field-hash-after.json','code-before.json','code-after.json','scheduler-terminal.json','batch-exit.json'} | {f'phase-{i:02d}.json' for i in range(1,26)}


def parse_terminal(job,text):
    from operations.x20_86304_radiation_contract import scheduler_tokens
    tokens=scheduler_tokens(text)
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
        from operations.x20_86304_radiation_contract import bounded_bytes
        data=bounded_bytes(p,32*1024**2)
        if p.suffix=='.json':
            from operations.x20_86304_radiation_contract import loads
            loads(data)
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


def receive(archive_path, receipt_path, target):
    """Verify the external receipt and all plain members before exclusive extraction."""
    from operations.x20_86304_radiation_contract import read, bounded_bytes
    claim = read(receipt_path); p = Path(archive_path); target = Path(target)
    if (p.is_symlink() or not p.is_file() or type(claim['size_bytes']) is not int or
        not 0 < claim['size_bytes'] <= 65*1024**2 or p.stat().st_size != claim['size_bytes']):
        raise ValueError('archive size/type')
    raw = bounded_bytes(p, 65*1024**2)
    if len(raw) != claim['size_bytes'] or hashlib.sha256(raw).hexdigest() != claim['sha256']:
        raise ValueError('archive SHA')
    expected = {}
    for row in claim['files']:
        name = row['path']
        if (name not in NAMES and Path(name).suffix not in ('.out','.err','.log')): raise ValueError('not whitelisted')
        if (name in expected or Path(name).name != name or '/' in name or name in ('.','..') or
            Path(name).suffix not in ('.json','.out','.err','.log') or
            type(row['size_bytes']) is not int or not 0 <= row['size_bytes'] <= 32*1024**2):
            raise ValueError('receipt member')
        expected[name] = row
    if sum(x['size_bytes'] for x in expected.values()) > 64*1024**2: raise ValueError('receipt total')
    blobs = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        for member in tar:
            if not member.isfile() or member.name in blobs or member.name not in expected:
                raise ValueError('unexpected/nonregular/repeated member')
            row = expected[member.name]
            if member.size != row['size_bytes']: raise ValueError('member size')
            data = tar.extractfile(member).read(member.size+1)
            if len(data) != member.size or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('member SHA')
            if Path(member.name).suffix=='.json':
                from operations.x20_86304_radiation_contract import loads
                loads(data)
            blobs[member.name] = data
    if blobs.keys() != expected.keys(): raise ValueError('missing member')
    target.mkdir(parents=False, exist_ok=False)
    for name, data in blobs.items():
        with (target/name).open('xb') as f: f.write(data)
    return dict(files=len(blobs), dat_files=0, scheduler_terminal_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    w=sub.add_parser('observe');w.add_argument('job');w.add_argument('output',type=Path)
    a=sub.add_parser('archive');a.add_argument('run',type=Path);a.add_argument('target',type=Path);a.add_argument('extra',nargs='*',type=Path)
    a=sub.add_parser('receive');a.add_argument('archive',type=Path);a.add_argument('receipt',type=Path);a.add_argument('target',type=Path)
    args=p.parse_args()
    if args.command=='observe':observe(args.job,args.output)
    elif args.command=='receive':receive(args.archive,args.receipt,args.target)
    else:archive(args.run,args.target,args.extra)
