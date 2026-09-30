"""Bounded prediction along the audited A16/H16 chord; no field is written."""
import argparse,json,os,resource,signal,time,tarfile,subprocess,sys
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as scan


def require_scan(a,d,s,t):
    if (a.get('job_id')!=82039 or not a.get('independent_slab_reduction')
        or not a.get('source_code_and_field_claims_verified') or a.get('source_job')!=81769
        or d.get('job_id')!='82039' or s.get('status')!='scan_complete_requires_review'
        or t.get('job_id')!=82039 or t.get('state')!='COMPLETED' or 'ExitCode=0:0' not in t.get('scontrol','')
        or a.get('new_maps')!=0 or a.get('new_material_steps')!=0 or a.get('baseline_replaced') is not False):
        raise ValueError('audited completed read-only 82039 required')
    if set(a['results'])!={'8','16'} or d['shape']!=[9632,32,4096]:raise ValueError('source scope')
    if s['results']!={k:v['total'] for k,v in a['results'].items()}:
        # Independent Decimal final rounding may differ by a few ulps.
        for k in ('8','16'):
            for key in ('dd','de','ee','rayleigh_action','mapped_difference_l2_ratio'):
                if not np.isclose(s['results'][k][key],a['results'][k]['total'][key],rtol=3e-12,atol=0):raise ValueError('source moments changed')


def execute(out):
    if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))!=4:raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('outputs/hpc run required')
    out.mkdir(exist_ok=False);start=time.monotonic()
    def mark(status,**kw):scan.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def checkpoint():
        if scan.STOP:raise InterruptedError('signal: no new slab dispatched')
    mark('preflight')
    try:
        ap=Path('handoff/evidence/20260930-x20-82039-review.json');a=scan.read(ap);receipt=a['receipt']
        archive=Path(receipt['path']);assert archive.stat().st_size==receipt['size_bytes'] and scan.digest(archive)==receipt['sha256']
        source=Path('outputs/hpc/x20-cross-seed-chord-20260930');watch=Path('outputs/review-20260925/x20-cross-seed-chord-watch-82039')
        with tarfile.open(archive) as tar:
            archived={name:json.load(tar.extractfile(name)) for name in ('declaration.json','summary.json','scheduler-terminal.json')}
        d=scan.read(source/'declaration.json');s=scan.read(source/'summary.json');t=scan.read(watch/'scheduler-terminal.json')
        assert d==archived['declaration.json'] and s==archived['summary.json'] and t==archived['scheduler-terminal.json']
        require_scan(a,d,s,t)
        fields=d['fields']['16'];physical=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930')
        review=scan.read('handoff/evidence/20260930-x20-81769-final-review.json')
        assert review['archive']==d['archive'] and review['reference_calibration_eligible'] is False
        original=Path(review['archive']['path']);assert scan.digest(original)==review['archive']['sha256']
        names=['source-preflight/boundary_geometry.npz']+[f'{n}/{f}' for n in ('accelerated','historical') for f in ('config.json','trial_material.npz','endpoints-map16/manifest.json')]
        with tarfile.open(original) as tar:
            for name in names:
                import hashlib
                assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==scan.digest(physical/name)
        cfgs=[scan.read(physical/n/'config.json') for n in ('accelerated','historical')];core.same_operator_config(*cfgs)
        assert scan.digest(physical/'accelerated/trial_material.npz')==scan.digest(physical/'historical/trial_material.npz')
        expected=[]
        for name in ('accelerated','historical'):
            m=scan.read(physical/name/'endpoints-map16/manifest.json');expected.extend(m['endpoints'][e] for e in ('final','mapped_final'))
        assert fields==expected
        gp=physical/'source-preflight/boundary_geometry.npz'
        with np.load(gp,allow_pickle=False) as z:geometry={k:z[k] for k in ('mu','weight','width')}
        assert geometry['mu'].shape==geometry['weight'].shape==(32,) and geometry['width'].shape==(9632,)
        assert all(np.isfinite(z).all() for z in geometry.values()) and np.all(geometry['weight']>0) and np.all(geometry['width']>0)
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_matched_chord_proposal.sbatch','tests/test_x20_matched_chord_proposal.py','tests/test_x20_history_operator.py','handoff/protocols/x20-matched-chord-proposal-v1.md')]
        claims=fields+[core.pipeline.claim(p) for p in (ap,archive,original,gp,source/'declaration.json',source/'summary.json',watch/'scheduler-terminal.json',Path('handoff/evidence/20260930-x20-81769-final-review.json'))]+[core.pipeline.claim(physical/name) for name in names]
        core.reused.verify(claims+code)
        scan.write(out/'declaration.json',dict(source_job=82039,source_maps_job=81769,fields=fields,claims=claims,code=code,shape=d['shape'],
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),python=sys.version,numpy=np.__version__,
            job_id=os.environ['SLURM_JOB_ID'],alpha_bounds=[-8.,8.],step_safety=.9,coefficient_l1_cap=17.,
            maximum_field_scans=2,maximum_candidates=1,maximum_new_maps=0,maximum_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        # 原有两遍扫描：先收完整Gram/正值区间，再重读全部单元验证唯一候选。
        mark('prediction_scan');report=core.collect_scan([core.ROOT/c['path'] for c in fields],d['shape'],geometry,checkpoint)
        scan.write(out/'prediction.json',report);core.reused.verify(claims+code);checkpoint()
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('parent RSS guard')
        status='prediction_complete_requires_review'
        scan.write(out/'summary.json',dict(status=status,feasible=report['feasible'],checks=report['checks'],source_job=82039,
            peak_rss_bytes=peak,wall_s=time.monotonic()-start,new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,strict_error_bound=False))
        mark(status)
    except BaseException as e:
        mark('stopped' if isinstance(e,InterruptedError) else 'failed',error=repr(e));raise


if __name__=='__main__':
    signal.signal(signal.SIGUSR1,scan.stop);signal.signal(signal.SIGTERM,scan.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);execute(p.parse_args().run)
