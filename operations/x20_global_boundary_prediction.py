"""One boundary-constrained global candidate; no new maps or feedback."""
import argparse,json,math,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_block_window_fields import measure_candidates


def require_candidate(candidate,audit,sha):
    from fractions import Fraction as F
    if (audit.get('source_job')!=82441 or audit.get('candidate_sha256')!=sha or audit.get('passed') is not True
        or audit.get('exact_cap_and_safety_checked') is not True or audit.get('raw_objective_independently_checked') is not True
        or len(audit.get('checks',{}))!=6 or not all(audit['checks'].values())):
        raise ValueError('independent global candidate audit required')
    if (candidate.get('source_job')!=82441 or candidate.get('solver_success') is not True
        or candidate.get('small_prediction_passed') is not True or candidate.get('step_safety')!=.9
        or candidate.get('basis_sha256')!=audit.get('basis_sha256')
        or candidate.get('selected_coefficients')!=audit.get('selected_coefficients')):
        raise ValueError('candidate identity')
    c=candidate['selected_coefficients'];raw=candidate['raw_coefficients']
    if len(c)!=3 or len(raw)!=3 or not all(math.isfinite(v) for v in c+raw):raise ValueError('coefficient shape or finite')
    if c!=[float(F(9,10)*F(v)) for v in raw]:raise ValueError('safety factor identity')
    if abs(1-sum(map(F,c)))+sum(abs(F(v)) for v in c)>17:raise ValueError('coefficient cap')
    for obj in (candidate,audit):
        if obj.get('candidate_written') is not False or obj.get('baseline_replaced') is not False or obj.get('global_optimality_claimed') is not False or any(obj.get(k)!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps')):
            raise ValueError('scope')
    return [list(c) for _ in range(76)]


def execute(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);start=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def checkpoint():
        if shared.STOP:raise InterruptedError('stop before next slab')
    mark('preflight')
    try:
        ev=Path('handoff/evidence');audit_path=ev/'20261001-x20-latest-basis-82441-review.json';a=shared.read(audit_path)
        if a['job_id']!=82441 or not a['independent_audit']:raise ValueError('basis audit required')
        source=Path('outputs/hpc/x20-latest-window-basis-20261001');d=shared.read(source/'declaration.json')
        receipt=a['receipt'];arc=Path(receipt['path'])
        if shared.digest(arc)!=receipt['sha256'] or arc.stat().st_size!=receipt['size_bytes']:raise ValueError('basis archive')
        # Bind live declaration and full small basis bytes to the independently audited receipt.
        index={c['path']:c for c in receipt['files']}
        for name in ('declaration.json','basis.json','summary.json','status.json'):
            if shared.digest(source/name)!=index[name]['sha256']:raise ValueError('live basis differs')
        cp=ev/'20261001-x20-global-boundary-candidate.json';ap=ev/'20261001-x20-global-boundary-candidate-review.json'
        c=shared.read(cp);ca=shared.read(ap);coefficients=require_candidate(c,ca,shared.digest(cp))
        if c['basis_sha256']!=shared.digest(source/'basis.json'):raise ValueError('candidate belongs to another basis')
        rejection_path=ev/'20261001-x20-boundary-validation-82503-review.json';rejection=shared.read(rejection_path)
        if rejection['job_id']!=82503 or not rejection['independent_small_statistic_reduction'] or rejection['true_maps_independently_validated']:
            raise ValueError('prior true-map rejection required')
        fields=d['fields']
        if fields!=a['fields'] or d['shape']!=[9632,32,4096]:raise ValueError('source fields')
        gp=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930/source-preflight/boundary_geometry.npz')
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(z).all() for z in geo.values()) and np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=d['small_claims']+[core.pipeline.claim(p) for p in (audit_path,arc,cp,ap,source/'declaration.json',source/'basis.json',gp)]
        small += [core.pipeline.claim(rejection_path)]
        small += [core.pipeline.claim(Path(p)) for p in ('handoff/audit_tools/select_x20_global_boundary_candidate.py','handoff/audit_tools/verify_x20_global_boundary_candidate.py','handoff/audit_tools/review_x20_block_window_prediction.py')]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_global_boundary_prediction.sbatch','tests/test_x20_global_boundary_prediction.py','tests/test_x20_window_fields.py','handoff/protocols/x20-global-boundary-prediction-v1.md')]
        core.reused.verify(small+d['code']+code)
        paths=[Path(c['path']) for c in fields];before=[p.stat() for p in paths]
        core.reused.verify(fields);checkpoint()
        shared.write(out/'declaration.json',dict(source_job=82441,source_claims=small,source_code=d['code'],code=code,fields=fields,
            shape=d['shape'],geometry=core.pipeline.claim(gp),job_id=os.environ['SLURM_JOB_ID'],
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            selected_coefficients=coefficients,global_coefficients=c['selected_coefficients'],coefficient_mode='one_global_triple_repeated',
            rejected_source_job=82503,candidate_sha256=shared.digest(cp),screening_sha256=shared.digest(ap),optimization_converged=True,
            maximum_full_field_reads=3,maximum_candidates=1,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark('prediction_scan')
        measured=measure_candidates(paths,d['shape'],coefficients,geo,checkpoint)
        shared.write(out/'prediction.json',measured);mark('post_hash_check')
        core.reused.verify(fields+small+d['code']+code)
        for p,s in zip(paths,before):
            now=p.stat()
            if (s.st_ino,s.st_size,s.st_mtime_ns)!=(now.st_ino,now.st_size,now.st_mtime_ns):raise RuntimeError('field changed')
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('parent RSS guard')
        status='prediction_passed_requires_review' if measured['passed'] else 'prediction_rejected_requires_review'
        shared.write(out/'summary.json',dict(status=status,passed=measured['passed'],checks=measured['checks'],candidate_written=False,
            new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,
            peak_rss_bytes=peak,wall_s=time.monotonic()-start))
        mark(status)
    except BaseException as exc:mark('stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc));raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);execute(p.parse_args().run)
