"""One globally halved historical direction; unchanged full-field science gates."""
import argparse, os, resource, signal, subprocess, time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import measure_candidates


def backtracked_coefficients(audit, original):
    if audit.get('job_id') != 82740 or not audit.get('integer_certificates_verified') or not audit.get('code_and_source_claims_verified'):
        raise ValueError('independently checked exact audit required')
    rows = audit['counts']
    if [(r['first_group'], r['kind']) for r in rows] != [(9440,'input'),(9440,'predicted_output'),(9472,'input'),(9472,'predicted_output')]:
        raise ValueError('wrong audit coverage')
    if sum(r['negative_count'] for r in rows) != 157782:
        raise ValueError('incomplete sign audit')
    for r in rows:
        n = r['negative_count']
        if r['full'] != {'-1':n,'0':0,'1':0} or r['half'] != {'-1':0,'0':0,'1':n}:
            raise ValueError('backtrack premise changed')
    if original != [-7.2,1.7918845939882053,0.]:
        raise ValueError('wrong original direction')
    # 全局沿同一方向回溯；不在频率或空间逐点裁剪。
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
        ap=Path('handoff/evidence/20261001-x20-subnormal-82740-review.json')
        op=Path('handoff/evidence/20261001-x20-historical-heating-prediction-82686-review.json')
        old=Path('outputs/hpc/x20-historical-heating-prediction-20261001')
        d=shared.read(old/'declaration.json');a=shared.read(op)
        ix={v['path']:v for v in a['receipt']['files']}
        for name in ('declaration.json','prediction.json','summary.json','status.json'):
            assert shared.digest(old/name)==ix[name]['sha256']
        assert a['result']['checks']=={'full_field_nonnegative':False}
        c=backtracked_coefficients(shared.read(ap),d['global_coefficients'])
        assert d['shape']==[9632,32,4096]
        core.reused.verify([d['geometry']])
        with np.load(d['geometry']['path'],allow_pickle=False) as z:
            geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values())
        assert np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=[core.pipeline.claim(p) for p in (ap,op,old/'declaration.json',old/'prediction.json',old/'summary.json',old/'status.json')]+[d['geometry']]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_historical_half_prediction.sbatch','tests/test_x20_historical_half_prediction.py','handoff/protocols/x20-historical-half-prediction-v1.md')]
        fields=d['fields'];paths=[Path(v['path']) for v in fields];before=[p.stat() for p in paths]
        core.reused.verify(small+code+fields);stop()
        shared.write(out/'declaration.json',dict(source_job=82686,sign_audit_job=82740,source_claims=small,code=code,fields=fields,shape=d['shape'],geometry=d['geometry'],
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
