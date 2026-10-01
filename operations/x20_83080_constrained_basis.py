"""Read-only current historical field Gram; no coefficient choice or candidate."""
import argparse,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_basis import collect


def require_source(a,d):
    if (a.get('job_id')!=83080 or a.get('source_job')!=83063 or a.get('sign_audit_job')!=83075
        or not a.get('independent_slab_reduction') or not a.get('source_and_code_verified')
        or d.get('job_id')!='83080' or d.get('git_commit')!='4bfd4004e27c55bee43d702acbfd144a6096b8f7'
        or d.get('source_job')!=83063 or d.get('sign_audit_job')!=83075
        or d.get('shape')!=[9632,32,4096] or d.get('step_multiplier')!=.25
        or d.get('global_coefficients')!=[0.,-1.8,.9485574831263044]):
        raise ValueError('audited current quarter identity required')
    checks=a['result']['checks']
    if len(checks)!=11 or [k for k,v in checks.items() if not v]!=['full_l2_benefit']:
        raise ValueError('original L2-only rejection required')
    if len(d.get('fields',[]))!=8 or any(a.get(k)!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps')) or a.get('baseline_replaced') is not False:
        raise ValueError('read-only source scope required')


def run(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    mark('preflight')
    try:
        ap=Path('handoff/evidence/20261001-x20-quarter-prediction-83080-review.json');a=shared.read(ap)
        prior=Path('outputs/hpc/x20-83063-quarter-prediction-20261001');d=shared.read(prior/'declaration.json')
        require_source(a,d)
        ix={v['path']:v for v in a['receipt']['files']}
        for name in ('declaration.json','prediction.json','summary.json','status.json'):
            p=prior/name
            assert p.stat().st_size==ix[name]['size_bytes'] and shared.digest(p)==ix[name]['sha256']
        original=Path('outputs/hpc/x20-82989-heating-prediction-20261001/declaration.json')
        od=shared.read(original);assert d['fields']==od['fields'] and d['geometry']==od['geometry']
        # 同一previous->final四对，绝不换成final->mapped_final；不触动物质或r20。
        gp=Path(d['geometry']['path']);core.reused.verify([d['geometry']])
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values())
        assert np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=[core.pipeline.claim(p) for p in (ap,original,gp,*(prior/name for name in ('declaration.json','prediction.json','summary.json','status.json')))]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in (
            'operations/x20_83080_constrained_basis.sbatch','tests/test_x20_83080_constrained_basis.py',
            'tests/test_x20_window_basis.py','handoff/protocols/x20-83080-constrained-basis-v1.md')]
        fields=d['fields'];paths=[Path(c['path']) for c in fields];before=[p.stat() for p in paths]
        core.reused.verify(small+code+fields)
        if shared.STOP:raise InterruptedError('stop before scan')
        shared.write(out/'declaration.json',dict(job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_job=83080,original_direction_job=83063,sign_audit_job=83075,source_claims=small,code=code,fields=fields,geometry=d['geometry'],shape=d['shape'],
            field_order=['82989H16_previous','82989H16_final','82989H8_previous','82989H8_final','82518H16_previous','82518H16_final','82273H16_previous','82273H16_final'],
            basis_order=['r_82989H16','r_82989H8-r_82989H16','r_82518H16-r_82989H16','r_82273H16-r_82989H16'],
            numpy=np.__version__,longdouble_mantissa_bits=np.finfo(np.longdouble).nmant,
            maximum_statistic_scans=1,new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,strict_error_bound=False))
        mark('scanning',completed_groups=0)
        result=collect(fields,d['shape'],geo,lambda n:mark('scanning',completed_groups=n))
        shared.write(out/'basis.json',result);mark('post_hash_check');core.reused.verify(small+code+fields)
        for p,b in zip(paths,before):
            n=p.stat();assert (n.st_ino,n.st_size,n.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('RSS guard')
        shared.write(out/'summary.json',dict(status='basis_complete_requires_review',gram=result['gram'],slabs=len(result['slabs']),
            peak_rss_bytes=peak,wall_s=time.monotonic()-started,new_maps=0,new_feedback_pairs=0,new_material_steps=0,
            candidate_written=False,baseline_replaced=False,strict_error_bound=False))
        mark('basis_complete_requires_review')
    except BaseException as exc:
        mark('stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc));raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);run(p.parse_args().run)
