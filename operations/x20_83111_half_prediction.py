"""One explicitly reviewed half direction; unchanged full-field science gates."""
import argparse, os, resource, signal, subprocess, time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import measure_candidates


def reviewed_half_coefficients(audit,original):
    if (audit.get('job_id')!=83111 or audit.get('source_job')!=83104 or audit.get('sign_audit_job')!=83075
        or not audit.get('independent_slab_reduction') or not audit.get('source_and_code_verified')
        or not audit.get('small_problem_kkt_reverified')):raise ValueError('current independent review required')
    z=audit['result'];checks=z['checks']
    if len(checks)!=11 or [k for k,v in checks.items() if not v]!=['full_boundary_l1','full_boundary_bolometric']:
        raise ValueError('wrong failure mechanism')
    if not 0 < z['l2_ratios'][2] <= .8 or not 0 < z['linf_ratios'][2] <= 1+1e-10:
        raise ValueError('old half cannot support a full candidate')
    if any(v<0 for v in z['minima']):raise ValueError('negative old half source')
    if z['boundary'][2]['residual']>=1e-4:raise ValueError('half radiation')
    for k in ('boundary_l1','boundary_bolometric'):
        if not 0<=z['boundary'][2][k]<1e-3 or z['boundary'][2][k]>z['boundary'][0][k]*(1+1e-10):raise ValueError('half boundary')
    if original!=audit['coefficients'] or original!=[-5.171447326928601,-2.028552673071399,.9]:raise ValueError('changed direction')
    # 显式审阅后缩放全域系数，不借用旧half的逐位结果或已通过标签。
    return [v/2 for v in original]


def run(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':
        raise RuntimeError('4CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):
        raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False); started=time.monotonic()
    def mark(status):shared.write(out/'status.json',dict(status=status,unix=time.time()))
    def stop():
        if shared.STOP:raise InterruptedError('stop before next slab')
    mark('preflight')
    try:
        op=Path('handoff/evidence/20261002-x20-constrained-prediction-83111-review.json')
        old=Path('outputs/hpc/x20-83104-constrained-prediction-20261002')
        d=shared.read(old/'declaration.json');a=shared.read(op)
        ix={v['path']:v for v in a['receipt']['files']}
        for name in ('declaration.json','prediction.json','summary.json','status.json'):
            assert shared.digest(old/name)==ix[name]['sha256']
        c=reviewed_half_coefficients(a,d['global_coefficients'])
        assert d['shape']==[9632,32,4096]
        core.reused.verify([d['geometry']])
        with np.load(d['geometry']['path'],allow_pickle=False) as z:
            geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values())
        assert np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=[core.pipeline.claim(p) for p in (op,old/'declaration.json',old/'prediction.json',old/'summary.json',old/'status.json')]+[d['geometry']]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_83111_half_prediction.sbatch','tests/test_x20_83111_half_prediction.py','handoff/protocols/x20-83111-half-prediction-v1.md')]
        fields=d['fields'];paths=[Path(v['path']) for v in fields];before=[p.stat() for p in paths]
        core.reused.verify(small+code+fields);stop()
        shared.write(out/'declaration.json',dict(source_job=83111,sign_audit_job=83075,source_claims=small,code=code,fields=fields,shape=d['shape'],geometry=d['geometry'],
            job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),global_coefficients=c,original_coefficients=d['global_coefficients'],step_multiplier=.5,
            new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,candidate_written=False,strict_error_bound=False,exact_full_domain_sign_certificate=False))
        mark('prediction_scan');measured=measure_candidates(paths,d['shape'],c,geo,stop)
        shared.write(out/'prediction.json',measured);mark('post_hash_check');core.reused.verify(small+code+fields)
        for p,b in zip(paths,before):
            n=p.stat();assert (n.st_ino,n.st_size,n.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('RSS guard')
        status='prediction_passed_requires_review' if measured['passed'] else 'prediction_rejected_requires_review'
        shared.write(out/'summary.json',dict(status=status,passed=measured['passed'],checks=measured['checks'],wall_s=time.monotonic()-started,peak_rss_bytes=peak,new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,exact_full_domain_sign_certificate=False))
        mark(status)
    except BaseException as exc:
        shared.write(out/'status.json',dict(status='stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc),unix=time.time()));raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);run(p.parse_args().run)
