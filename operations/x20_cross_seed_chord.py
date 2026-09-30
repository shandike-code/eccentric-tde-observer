"""Read-only, bounded full-field difference transport scan after audited 81769.

No map, proposal, material update, clipping, or spectral-radius claim.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
import numpy as np

STOP=False


def stop(*_):
    global STOP
    STOP=True


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()


def read(p):return json.loads(Path(p).read_text())


def write(p,x):
    p=Path(p);tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');tmp.replace(p)


def moments(a,ta,h,th):
    if any(x.shape!=a.shape or not np.isfinite(x).all() or np.any(x<0) for x in (a,ta,h,th)):
        raise ValueError('incompatible or nonphysical intensity inputs')
    d=(h-a).astype(np.longdouble)
    e=((th-h)-(ta-a)).astype(np.longdouble)
    return dict(dd=float(np.sum(d*d,dtype=np.longdouble)),de=float(np.sum(d*e,dtype=np.longdouble)),
                ee=float(np.sum(e*e,dtype=np.longdouble)),difference_linf=float(np.max(abs(d))),
                change_linf=float(np.max(abs(e))))


def reduce_rows(rows):
    dd,de,ee=(math.fsum(r[k] for r in rows) for k in ('dd','de','ee'))
    if dd<=0: return dict(dd=dd,de=de,ee=ee,relative_change_l2=None,rayleigh_action=None,zero_difference=True)
    return dict(dd=dd,de=de,ee=ee,relative_change_l2=math.sqrt(ee/dd),rayleigh_action=1+de/dd,
                mapped_difference_l2_ratio=math.sqrt((dd+2*de+ee)/dd),zero_difference=False,
                difference_linf=max(r['difference_linf'] for r in rows),change_linf=max(r['change_linf'] for r in rows),
                spectral_radius_established=False,strict_error_bound=False)


def scan(claims,shape,progress):
    rows=[];hashes=[hashlib.sha256() for _ in claims]
    with ExitStack() as stack:
        files=[stack.enter_context(Path(c['path']).open('rb')) for c in claims]
        before=[os.fstat(f.fileno()) for f in files]
        if any(s.st_size!=c['size_bytes'] for s,c in zip(before,claims)):raise ValueError('field size')
        for start in range(0,shape[0],32):
            if STOP:raise InterruptedError('signal: no new slab dispatched')
            n=min(32,shape[0]-start);size=n*math.prod(shape[1:])*8;aa=[]
            for f,h in zip(files,hashes):
                raw=f.read(size)
                if len(raw)!=size:raise ValueError('truncated field')
                h.update(raw);aa.append(np.frombuffer(raw,dtype='<f8').reshape(n,*shape[1:]))
            row=moments(*aa);row.update(first_group=start,group_count=n,block=start//128);rows.append(row)
            if len(rows)%16==0:progress(start+n)
        for f,s,c,h in zip(files,before,claims,hashes):
            after=os.fstat(f.fileno());live=Path(c['path']).stat()
            if f.read(1) or h.hexdigest()!=c['sha256']:raise ValueError('field SHA or tail mismatch')
            if (s.st_ino,s.st_size,s.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns) or (s.st_ino,s.st_size,s.st_mtime_ns)!=(live.st_ino,live.st_size,live.st_mtime_ns):raise ValueError('field changed during scan')
    return dict(slabs=rows,total=reduce_rows(rows),blocks={str(i):reduce_rows([r for r in rows if r['block']==i]) for i in range((shape[0]+127)//128)},all_field_sha256_verified=True)


def execute(out):
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=4:raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('run must be within outputs/hpc')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(s,**kw):write(out/'status.json',dict(status=s,unix=time.time(),**kw))
    mark('preflight')
    try:
        source=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930')
        auditpath=Path('handoff/evidence/20260930-x20-81769-final-review.json');audit=read(auditpath)
        terminal=read('handoff/evidence/20260930-x20-81769-terminal.json')
        assert audit['completed_experiment'] and audit['all_original_zero_gates_passed'] and audit['map_counts']=={'accelerated':16,'historical':16}
        assert terminal['job_id']==81769 and terminal['state']=='COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
        archive=Path(audit['archive']['path']);assert archive.stat().st_size==audit['archive']['size_bytes'] and digest(archive)==audit['archive']['sha256']
        # Inventory identity is bound to the source audit via its copied archive.
        import tarfile
        # Bind each needed sibling-inventory entry to its actual archive member.
        sibling=read(archive.with_suffix('').with_suffix('.json'))
        bypath={c['path']:c for c in sibling['files']}
        needed=['summary.json','declaration.json']+[f'{name}/{f}' for name in ('accelerated','historical') for f in ('config.json','state.json','trial_material.npz','endpoints-map08/manifest.json','endpoints-map16/manifest.json')]
        with tarfile.open(archive) as tar:
            for rel in needed:
                c=bypath[rel];p=source/rel
                assert p.stat().st_size==c['size_bytes'] and digest(p)==c['sha256']
                assert hashlib.sha256(tar.extractfile(rel).read()).hexdigest()==c['sha256']
        assert digest(source/'accelerated/trial_material.npz')==digest(source/'historical/trial_material.npz')
        shapes=[read(source/name/'config.json')['shape'] for name in ('accelerated','historical')]
        assert shapes[0]==shapes[1]==[9632,32,4096]
        claims={}
        for n in (8,16):
            fields=[]
            for name in ('accelerated','historical'):
                m=read(source/name/f'endpoints-map{n:02d}/manifest.json');row=m['history_rows'][-1]
                assert row['iteration']==n and m['endpoints']['final']['sha256']==row['input_sha256'] and m['endpoints']['mapped_final']['sha256']==row['output_sha256']
                fields.extend(m['endpoints'][e] for e in ('final','mapped_final'))
            assert all(c['size_bytes']==math.prod(shapes[0])*8 for c in fields);claims[str(n)]=fields
        code={p:digest(p) for p in ('operations/x20_cross_seed_chord.py','operations/x20_cross_seed_chord.sbatch','tests/test_x20_cross_seed_chord.py','handoff/protocols/x20-cross-seed-chord-v1.md')}
        write(out/'declaration.json',dict(source_job=81769,audit_sha256=digest(auditpath),archive=audit['archive'],fields=claims,code=code,shape=shapes[0],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),job_id=os.environ['SLURM_JOB_ID'],maximum_field_scans=2,maximum_new_maps=0,maximum_feedback_pairs=0,new_material_steps=0,baseline_replaced=False))
        results={}
        for n in (8,16):
            mark('scanning',checkpoint=n,completed_groups=0)
            results[str(n)]=scan(claims[str(n)],shapes[0],lambda g:mark('scanning',checkpoint=n,completed_groups=g))
            write(out/f'checkpoint{n:02d}.json',results[str(n)])
        assert all(digest(p)==sha for p,sha in code.items())
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('memory guard')
        write(out/'summary.json',dict(status='scan_complete_requires_review',source_job=81769,results={k:v['total'] for k,v in results.items()},wall_s=time.monotonic()-started,peak_rss_bytes=peak,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark('scan_complete_requires_review')
    except BaseException as e:
        mark('stopped' if isinstance(e,InterruptedError) else 'failed',error=repr(e));raise


if __name__=='__main__':
    signal.signal(signal.SIGUSR1,stop);signal.signal(signal.SIGTERM,stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);execute(p.parse_args().run)
