"""Collect current endpoint residual inner products before choosing blockwise acceleration."""
import argparse,hashlib,json,os,resource,signal,subprocess,time,tarfile
from pathlib import Path
import numpy as np
from operations import x20_cross_seed_chord as shared
from operations.x20_window_basis import collect


def require_scan(a,d,t):
    if (a.get('job_id')!=82396 or a.get('source_job')!=82273
        or not a.get('independent_slab_reduction') or not a.get('source_code_and_field_claims_verified')
        or a.get('new_maps')!=0 or a.get('new_material_steps')!=0 or a.get('baseline_replaced') is not False
        or d.get('job_id')!='82396' or d.get('source_job')!=82273 or d.get('shape')!=[9632,32,4096]
        or set(d.get('fields',{}))!={'8','16'} or set(a.get('results',{}))!={'8','16'}
        or t.get('job_id')!=82396 or t.get('state')!='COMPLETED' or 'ExitCode=0:0' not in t.get('scontrol','')):
        raise ValueError('independently audited complete 82396 required')


def execute(out):
    from operations import x20_history_operator as core
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=4:raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    mark('preflight')
    try:
        ap=Path('handoff/evidence/20260930-x20-window-difference-82396-review.json');audit=shared.read(ap)
        arc=Path(audit['receipt']['path']);assert shared.digest(arc)==audit['receipt']['sha256'] and arc.stat().st_size==audit['receipt']['size_bytes']
        with tarfile.open(arc) as tar:
            term=json.load(tar.extractfile('scheduler-terminal.json'));decl=json.load(tar.extractfile('declaration.json'))
        require_scan(audit,decl,term)
        previous=Path('outputs/hpc/x20-window-difference-20260930');assert shared.read(previous/'declaration.json')==decl
        oldaudit=shared.read('handoff/evidence/20260930-x20-82273-final-review.json');original=Path(oldaudit['archive']['path'])
        assert shared.digest(original)==oldaudit['archive']['sha256']
        assert oldaudit['job_id']==82273 and oldaudit['completed_experiment'] and oldaudit['all_original_zero_gates_passed'] and oldaudit['reference_calibration_eligible'] is False
        assert decl['archive']==oldaudit['archive']
        source=Path('outputs/hpc/x20-window-feedback-20260930');names=['declaration.json']
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
        assert fields[:4]==decl['fields']['16'] and fields[4:]==decl['fields']['8']
        geometry_claims=[c for c in shared.read(source/'declaration.json')['claims'] if c['path'].endswith('/boundary_geometry.npz')]
        assert len(geometry_claims)==1
        core.reused.verify(geometry_claims)
        gp=Path(geometry_claims[0]['path'])
        with np.load(gp,allow_pickle=False) as z:geometry={k:z[k] for k in ('mu','weight','width')}
        assert geometry['mu'].shape==geometry['weight'].shape==(32,) and geometry['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geometry.values())
        assert np.all(abs(geometry['mu'])<=1) and np.all(geometry['weight']>0) and np.all(geometry['width']>0)
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_latest_window_basis.sbatch','tests/test_x20_window_basis.py','tests/test_x20_latest_window_basis.py','handoff/protocols/x20-latest-window-basis-v1.md')]
        small=[core.pipeline.claim(p) for p in (ap,arc,original,previous/'declaration.json',gp,Path('handoff/evidence/20260930-x20-82273-final-review.json'))]+[core.pipeline.claim(source/n) for n in names]
        core.reused.verify(small+code)
        shared.write(out/'declaration.json',dict(source_jobs=[82273,82396],source_audit=core.pipeline.claim(ap),fields=fields,small_claims=small,code=code,
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
