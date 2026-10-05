"""Read-only current historical field Gram; no coefficient choice or candidate."""
import argparse,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_basis import collect


SOURCES={
    84026:('x20-83514-seed-feedback-20261002','20261005-x20-84026-final-review.json'),
    82989:('x20-historical-seed-feedback-20261001','20261001-x20-82989-final-review.json'),
    82518:('x20-global-window-feedback-20261001','20261001-x20-82518-final-review.json')}
ORDER=((84026,16),(84026,8),(82989,16),(82518,16))


def require_source(a,job):
    if (a.get('job_id')!=job or not a.get('completed_experiment')
        or not a.get('independent_vector_reduction') or not a.get('all_original_zero_gates_passed')
        or a.get('new_material_steps')!=0 or a.get('accepted_outer_steps')!=20
        or a.get('baseline_replaced') is not False or a.get('reference_calibration_eligible') is not False):
        raise ValueError('audited fixed-x20 numerical artifacts required')
    if job==84026 and (a.get('numerical_artifacts_complete') is not True
        or a.get('scheduler_terminal_verified') is not False or a.get('scheduler_terminal_state') is not None):
        raise ValueError('84026 missing scheduler evidence must remain explicit')


def pair_fields(manifest,n):
    # 缺陷必须绑定previous到final，不能误取后续final到mapped_final。
    rows=manifest['history_rows'];e=manifest['endpoints']
    if (len(rows)!=2 or [r['iteration'] for r in rows]!=[n-1,n]
        or rows[0]['input_sha256']!=e['previous']['sha256']
        or rows[0]['output_sha256']!=rows[1]['input_sha256'] or rows[1]['input_sha256']!=e['final']['sha256']):
        raise ValueError('previous-to-final pair identity mismatch')
    return [e[k] for k in ('previous','final')]


def source_plan():
    import json,tarfile
    claims=[];configs=[];trials=[];roots={}
    for job,(run,audit_name) in SOURCES.items():
        ap=Path('handoff/evidence')/audit_name;a=shared.read(ap);require_source(a,job)
        root=Path('outputs/hpc')/run;roots[job]=root
        arc=Path(a['archive']['path']);core.reused.verify([a['archive']])
        names=['declaration.json','summary.json','historical/config.json','historical/trial_material.npz']
        for j,n in ORDER:
            if j==job:names += [f'historical/endpoints-map{n:02d}/manifest.json']+[f'historical/pair{n:02d}/{e}_feedback.npz' for e in ('previous','final')]
        with tarfile.open(arc) as tar:
            ix={c['path']:c for c in json.load(tar.extractfile('ARCHIVE_MANIFEST.json'))['files']}
            for name in names:
                p=root/name;c=core.pipeline.claim(p)
                if any(c[k]!=ix[name][k] for k in ('size_bytes','sha256')):raise ValueError('source archive mismatch '+name)
                claims.append(c)
        d=shared.read(root/'declaration.json');core.reused.verify(d['code']);claims+=d['code']
        claims += [core.pipeline.claim(ap),a['archive']]
        configs.append(shared.read(root/'historical/config.json'))
        with np.load(root/'historical/trial_material.npz',allow_pickle=False) as z:trials.append({k:z[k] for k in z.files})
    for cfg in configs:
        core.same_operator_config(configs[0],cfg)
        if cfg['shape']!=[9632,32,4096]:raise ValueError('shape changed')
    for t in trials:
        if set(t)!=set(trials[0]) or any(not np.array_equal(t[k],trials[0][k]) for k in t):raise ValueError('trial identity changed')
    if int(trials[0]['phase_index'])!=1367 or float(trials[0]['step_duration_s'])!=889.419892762322:raise ValueError('physical phase/dt changed')
    fields=[]
    for job,n in ORDER:fields+=pair_fields(shared.read(roots[job]/f'historical/endpoints-map{n:02d}/manifest.json'),n)
    gpdecl=Path('outputs/hpc/x20-83111-half-prediction-20261002/declaration.json')
    vp=Path('outputs/hpc/x20-83131-true-validation-20261002/declaration.json')
    source_claims=shared.read(roots[84026]/'declaration.json')['claims']
    if core.pipeline.claim(vp) not in source_claims:raise ValueError('83514 declaration changed from84026 archived source')
    geometry=shared.read(gpdecl)['geometry'];validated=shared.read(vp)
    known={c['path']:c for c in validated['claims']}
    c=core.pipeline.claim(gpdecl)
    if c!=known.get(c['path']) or geometry!=known.get(geometry['path']):raise ValueError('geometry not bound to audited83514 source')
    claims += [c,core.pipeline.claim(Path('outputs/hpc/x20-83131-true-validation-20261002/declaration.json')),geometry]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    return fields,geometry,claims


def run(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    mark('preflight')
    try:
        fields,geometry,small=source_plan()
        gp=Path(geometry['path']);core.reused.verify([geometry])
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values())
        assert np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in (
            'operations/x20_84026_basis.sbatch','tests/test_x20_84026_basis.py',
            'tests/test_x20_window_basis.py','handoff/protocols/x20-84026-basis-v1.md')]
        paths=[Path(c['path']) for c in fields];before=[p.stat() for p in paths]
        core.reused.verify(small+code+fields)
        if shared.STOP:raise InterruptedError('stop before scan')
        shared.write(out/'declaration.json',dict(job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_job=84026,source_jobs=[84026,82989,82518],source_scheduler_terminal_verified=False,source_claims=small,code=code,fields=fields,geometry=geometry,shape=[9632,32,4096],
            field_order=[f'{j}H{n}_{e}' for j,n in ORDER for e in ('previous','final')],
            basis_order=['r_84026H16','r_84026H8-r_84026H16','r_82989H16-r_84026H16','r_82518H16-r_84026H16'],
            numpy=np.__version__,longdouble_mantissa_bits=np.finfo(np.longdouble).nmant,
            maximum_statistic_scans=1,new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,strict_error_bound=False))
        mark('scanning',completed_groups=0)
        result=collect(fields,[9632,32,4096],geo,lambda n:mark('scanning',completed_groups=n))
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
