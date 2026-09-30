"""Collect three matched-window directions; one read-only scan, no candidate."""
import argparse,hashlib,json,math,os,resource,signal,subprocess,time,tarfile
from contextlib import ExitStack
from pathlib import Path
import numpy as np
from operations import x20_cross_seed_chord as shared


def basis_moments(fields):
    if len(fields)!=8 or any(v.shape!=fields[0].shape or not np.isfinite(v).all() or np.any(v<0) for v in fields):raise ValueError('eight finite nonnegative fields required')
    residuals=[fields[2*j+1]-fields[2*j] for j in range(4)]
    # 基准为A16原缺陷；三个方向保留H16、A8、H8各自相对A16的缺陷差。
    basis=[residuals[0]]+[r-residuals[0] for r in residuals[1:]]
    wide=[v.astype(np.longdouble) for v in basis];g=np.empty((4,4))
    for i in range(4):
        for j in range(i,4):g[i,j]=g[j,i]=float(np.sum(wide[i]*wide[j],dtype=np.longdouble))
    return dict(gram=g.tolist(),basis_linf=[float(np.max(abs(v))) for v in basis],field_minima=[float(v.min()) for v in fields])


def collect(claims,shape,geometry,progress=lambda _:None):
    from operations.x20_history_operator import boundary_spectrum
    rows=[];hashes=[hashlib.sha256() for _ in claims]
    if len(claims)!=8:raise ValueError('four map pairs required')
    with ExitStack() as stack:
        files=[stack.enter_context(Path(c['path']).open('rb')) for c in claims];before=[os.fstat(f.fileno()) for f in files]
        assert all(s.st_size==c['size_bytes']==math.prod(shape)*8 for s,c in zip(before,claims))
        for first in range(0,shape[0],32):
            if shared.STOP:raise InterruptedError('stop before next slab')
            n=min(32,shape[0]-first);size=n*math.prod(shape[1:])*8;fields=[]
            for f,h in zip(files,hashes):
                b=f.read(size)
                if len(b)!=size:raise ValueError('truncated field')
                h.update(b);fields.append(np.frombuffer(b,dtype='<f8').reshape(n,*shape[1:]))
            row=basis_moments(fields);row.update(first_group=first,group_count=n,block=first//128,
                boundary_spectra=[boundary_spectrum(v,geometry['mu'],geometry['weight'],geometry['width'][first:first+n]).tolist() for v in fields])
            rows.append(row)
            if len(rows)%16==0:progress(first+n)
        for f,s,c,h in zip(files,before,claims,hashes):
            after=os.fstat(f.fileno());live=Path(c['path']).stat()
            if f.read(1) or h.hexdigest()!=c['sha256']:raise ValueError('SHA or tail mismatch')
            for t in (after,live):
                if (s.st_ino,s.st_size,s.st_mtime_ns)!=(t.st_ino,t.st_size,t.st_mtime_ns):raise ValueError('field identity changed')
    gram=[[math.fsum(r['gram'][i][j] for r in rows) for j in range(4)] for i in range(4)]
    return dict(slabs=rows,gram=gram,basis_linf=[max(r['basis_linf'][i] for r in rows) for i in range(4)],
                field_minima=[min(r['field_minima'][i] for r in rows) for i in range(8)],all_eight_sha256_verified=True,
                field_weighting='unweighted array Euclidean; not radiation energy',candidate_written=False)


def execute(out):
    from operations import x20_history_operator as core
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=4:raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    mark('preflight')
    try:
        ap=Path('handoff/evidence/20260930-x20-82083-review.json');audit=shared.read(ap)
        assert audit['job_id']==82083 and audit['independent_reduction'] and not audit['feasible'] and audit['line_minimum']['all_real_alpha_cannot_reach_0_8']
        arc=Path(audit['receipt']['path']);assert shared.digest(arc)==audit['receipt']['sha256'] and arc.stat().st_size==audit['receipt']['size_bytes']
        with tarfile.open(arc) as tar:
            term=json.load(tar.extractfile('scheduler-terminal.json'));decl=json.load(tar.extractfile('declaration.json'))
        assert term['job_id']==82083 and term['state']=='COMPLETED' and 'ExitCode=0:0' in term['scontrol']
        previous=Path('outputs/hpc/x20-matched-chord-proposal-20260930');assert shared.read(previous/'declaration.json')==decl
        oldaudit=shared.read('handoff/evidence/20260930-x20-81769-final-review.json');original=Path(oldaudit['archive']['path'])
        assert shared.digest(original)==oldaudit['archive']['sha256']
        source=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930');names=['source-preflight/boundary_geometry.npz']
        order=[('accelerated',16),('historical',16),('accelerated',8),('historical',8)]
        names += [f'{name}/endpoints-map{n:02d}/manifest.json' for name,n in order]
        names += [f'{name}/{f}' for name in ('accelerated','historical') for f in ('trial_material.npz','config.json')]
        with tarfile.open(original) as tar:
            for name in names:assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==shared.digest(source/name)
        assert shared.digest(source/'accelerated/trial_material.npz')==shared.digest(source/'historical/trial_material.npz')
        cfgs=[shared.read(source/n/'config.json') for n in ('accelerated','historical')];core.same_operator_config(*cfgs)
        assert cfgs[0]['shape']==[9632,32,4096]
        fields=[]
        for name,n in order:
            m=shared.read(source/name/f'endpoints-map{n:02d}/manifest.json');r=m['history_rows'][-1]
            assert r['iteration']==n and m['endpoints']['final']['sha256']==r['input_sha256'] and m['endpoints']['mapped_final']['sha256']==r['output_sha256']
            fields.extend(m['endpoints'][e] for e in ('final','mapped_final'))
        assert fields[:4]==audit['fields']
        gp=source/'source-preflight/boundary_geometry.npz'
        with np.load(gp,allow_pickle=False) as z:geometry={k:z[k] for k in ('mu','weight','width')}
        assert geometry['mu'].shape==geometry['weight'].shape==(32,) and geometry['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geometry.values())
        assert np.all(abs(geometry['mu'])<=1) and np.all(geometry['weight']>0) and np.all(geometry['width']>0)
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_window_basis.sbatch','tests/test_x20_window_basis.py','handoff/protocols/x20-window-basis-v1.md')]
        small=[core.pipeline.claim(p) for p in (ap,arc,original,previous/'declaration.json')]+[core.pipeline.claim(source/n) for n in names]
        core.reused.verify(small+code)
        shared.write(out/'declaration.json',dict(source_jobs=[81769,82039,82083],source_audit=core.pipeline.claim(ap),fields=fields,small_claims=small,code=code,
            field_order=['A16','T_A16','H16','T_H16','A8','T_A8','H8','T_H8'],basis_order=['r_A16','r_H16-r_A16','r_A8-r_A16','r_H8-r_A16'],
            shape=cfgs[0]['shape'],job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            numpy=np.__version__,longdouble_mantissa_bits=np.finfo(np.longdouble).nmant,maximum_field_scans=1,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark('scanning',completed_groups=0)
        result=collect(fields,cfgs[0]['shape'],geometry,lambda n:mark('scanning',completed_groups=n))
        shared.write(out/'basis.json',result);core.reused.verify(small+code)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('RSS guard')
        shared.write(out/'summary.json',dict(status='basis_complete_requires_review',gram=result['gram'],slabs=len(result['slabs']),peak_rss_bytes=peak,wall_s=time.monotonic()-started,new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,strict_error_bound=False))
        mark('basis_complete_requires_review')
    except BaseException as exc:mark('stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc));raise


if __name__=='__main__':
    signal.signal(signal.SIGUSR1,shared.stop);signal.signal(signal.SIGTERM,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);execute(p.parse_args().run)
