"""One audited three-direction candidate, full-field prediction only."""
import argparse,json,math,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_block_window_fields import measure_candidates


def require_candidate(candidate,audit,sha):
    from fractions import Fraction as F
    def value(x):return F(int(x['numerator']),int(x['denominator']))
    if (audit.get('source_job')!=82441 or audit.get('analysis_sha256')!=sha
        or not audit.get('exact_principal_determinants_checked')
        or not audit.get('exact_supporting_plane_certificates_checked')
        or not audit.get('all_76_blocks_retained') or not audit.get('unresolved_coefficients_zero')
        or not audit.get('selected_coefficients_exactly_nine_tenths')
        or audit.get('basis_sha256')!=candidate.get('basis_sha256')):
        raise ValueError('independent exact certificate required')
    if candidate.get('source_job')!=82441 or candidate.get('baseline_replaced') is not False or candidate.get('coefficient_l1_cap')!=17 or candidate.get('step_safety')!=.9 or len(candidate.get('blocks',[]))!=76:
        raise ValueError('wrong coefficient scope')
    rows=[]
    for i,row in enumerate(candidate['blocks']):
        raw=[value(v) for v in row['coefficients_exact']];selected=[value(v) for v in row['selected_coefficients_exact']]
        if row['block']!=i or len(raw)!=3 or selected!=[F(9,10)*v for v in raw] or abs(1-sum(raw))+sum(map(abs,raw))>17:
            raise ValueError('coefficient identity or cap')
        if i in audit['unresolved_blocks'] and any(raw):raise ValueError('unresolved block changed')
        if row['selected_coefficients_float']!=list(map(float,selected)):raise ValueError('rounded coefficient identity')
        rows.append(list(map(float,selected)))
    if candidate['candidate_written'] or any(candidate[k]!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps')):
        raise ValueError('wrong budget')
    return rows


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
        cp=ev/'20261001-x20-82441-bounded-gram-analysis.json';ap=ev/'20261001-x20-82441-bounded-gram-verification.json'
        c=shared.read(cp);ca=shared.read(ap);coefficients=require_candidate(c,ca,shared.digest(cp))
        if c['audit_sha256']!=shared.digest(audit_path) or c['basis_sha256']!=shared.digest(source/'basis.json'):raise ValueError('candidate belongs to another basis')
        fields=d['fields']
        if fields!=a['fields'] or d['shape']!=[9632,32,4096]:raise ValueError('source fields')
        gp=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930/source-preflight/boundary_geometry.npz')
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(z).all() for z in geo.values()) and np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=d['small_claims']+[core.pipeline.claim(p) for p in (audit_path,arc,cp,ap,source/'declaration.json',source/'basis.json',gp)]
        small += [core.pipeline.claim(Path(p)) for p in ('handoff/audit_tools/bounded_window_gram.py','handoff/audit_tools/analyze_x20_latest_gram.py','handoff/audit_tools/verify_x20_bounded_gram.py','tests/test_bounded_window_gram.py')]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_block_window_prediction.sbatch','tests/test_x20_block_window_prediction.py','tests/test_x20_window_fields.py','handoff/protocols/x20-block-window-prediction-v1.md')]
        core.reused.verify(small+d['code']+code)
        paths=[Path(c['path']) for c in fields];before=[p.stat() for p in paths]
        core.reused.verify(fields);checkpoint()
        shared.write(out/'declaration.json',dict(source_job=82441,source_claims=small,source_code=d['code'],code=code,fields=fields,
            shape=d['shape'],geometry=core.pipeline.claim(gp),job_id=os.environ['SLURM_JOB_ID'],
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            selected_coefficients=coefficients,unresolved_blocks=ca['unresolved_blocks'],full_fraction=.9,half_fraction=.45,coefficient_mode='per_natural_block',
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
