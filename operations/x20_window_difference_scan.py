"""Read-only difference transport of audited 82273 endpoints; no new map."""
import argparse
import hashlib
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import time
from operations.x20_cross_seed_chord import digest, read, write, scan, stop


def require_review(audit, terminal):
    if (audit.get('job_id') != 82273 or not audit.get('completed_experiment')
            or not audit.get('all_original_zero_gates_passed')
            or audit.get('map_counts') != dict(accelerated=16,historical=16)
            or audit.get('reference_calibration_eligible') is not False
            or audit.get('accepted_outer_steps') != 20
            or audit.get('new_material_steps') != 0
            or audit.get('baseline_replaced') is not False
            or terminal.get('job_id') != 82273
            or terminal.get('state') != 'COMPLETED'
            or 'ExitCode=0:0' not in terminal.get('scontrol','')):
        raise ValueError('complete independently audited failed calibration of 82273 required')


def execute(out):
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=4:raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('run must be within outputs/hpc')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(s,**kw):write(out/'status.json',dict(status=s,unix=time.time(),**kw))
    mark('preflight')
    try:
        source=Path('outputs/hpc/x20-window-feedback-20260930')
        auditpath=Path('handoff/evidence/20260930-x20-82273-final-review.json');audit=read(auditpath)
        terminal=read('handoff/evidence/20260930-x20-82273-terminal.json')
        require_review(audit,terminal)
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
        code={p:digest(p) for p in ('operations/x20_window_difference_scan.py','operations/x20_window_difference_scan.sbatch','operations/x20_cross_seed_chord.py','tests/test_x20_cross_seed_chord.py','tests/test_x20_window_difference_scan.py','handoff/protocols/x20-window-difference-scan-v1.md')}
        write(out/'declaration.json',dict(source_job=82273,audit_sha256=digest(auditpath),archive=audit['archive'],fields=claims,code=code,shape=shapes[0],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),job_id=os.environ['SLURM_JOB_ID'],maximum_field_scans=2,maximum_new_maps=0,maximum_feedback_pairs=0,new_material_steps=0,baseline_replaced=False))
        results={}
        for n in (8,16):
            mark('scanning',checkpoint=n,completed_groups=0)
            results[str(n)]=scan(claims[str(n)],shapes[0],lambda g:mark('scanning',checkpoint=n,completed_groups=g))
            write(out/f'checkpoint{n:02d}.json',results[str(n)])
        assert all(digest(p)==sha for p,sha in code.items())
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('memory guard')
        write(out/'summary.json',dict(status='scan_complete_requires_review',source_job=82273,results={k:v['total'] for k,v in results.items()},wall_s=time.monotonic()-started,peak_rss_bytes=peak,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark('scan_complete_requires_review')
    except BaseException as e:
        mark('stopped' if isinstance(e,InterruptedError) else 'failed',error=repr(e));raise


if __name__=='__main__':
    signal.signal(signal.SIGUSR1,stop);signal.signal(signal.SIGTERM,stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);execute(p.parse_args().run)
