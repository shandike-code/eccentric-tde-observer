"""One global constrained candidate; full original field screen, no map or dat write."""
import argparse,os,resource,signal,subprocess,time,sys
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import measure_candidates
from handoff.audit_tools.solve_x20_85744_joint import inputs,OLD
from handoff.audit_tools.solve_x20_85744_boundary import verify_candidate


def live_path(p):
    if Path(p)==OLD:return Path('outputs/hpc/common-feedback-bridge-v2-20260923/inputs/physical_old_time_level.npz')
    return Path(p)


def run(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def stop():
        if shared.STOP:raise InterruptedError('stop before next slab')
    mark('preflight')
    try:
        cp=Path('handoff/evidence/20261005-x20-85744-boundary-candidate.json');candidate=shared.read(cp)
        for claim in candidate['source_claims']:
            p=live_path(claim['path']);assert p.stat().st_size==claim['size_bytes'] and shared.digest(p)==claim['sha256']
        g,gr,gh,faces,claims,basis,d0=inputs(live_path)
        c=verify_candidate(candidate,g,gr,gh,faces,basis)
        assert candidate['fields']==d0['fields']
        bp=Path('outputs/hpc/x20-84026-basis-20261005/declaration.json')
        audit=shared.read('handoff/evidence/20261005-x20-current-basis-85744-review.json');ix={v['path']:v for v in audit['receipt']['files']}
        assert shared.digest(bp)==ix['declaration.json']['sha256'];d=shared.read(bp)
        assert d['fields']==audit['fields']==candidate['fields'] and d['shape']==[9632,32,4096]
        assert audit['scheduler_terminal_verified'] and audit['source_84026_scheduler_terminal_verified'] is False
        gp=Path(d['geometry']['path']);core.reused.verify([d['geometry']])
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values())
        assert np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=[core.pipeline.claim(live_path(v['path'])) for v in claims]+[core.pipeline.claim(p) for p in (cp,bp,gp)]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in (
            'operations/x20_85744_boundary_prediction.sbatch','tests/test_x20_85744_boundary.py','handoff/protocols/x20-85744-boundary-prediction-v1.md',
            'handoff/audit_tools/solve_x20_85744_boundary.py','handoff/audit_tools/solve_x20_85744_joint.py',
            'handoff/audit_tools/solve_x20_83104_constrained.py','handoff/audit_tools/bounded_window_gram.py',
            'handoff/audit_tools/verify_x20_bounded_gram.py','handoff/audit_tools/analyze_x20_latest_gram.py',
            'handoff/audit_tools/review_x20_85744_basis.py','handoff/audit_tools/review_x20_window_basis.py',
            'handoff/audit_tools/review_x20_matched_proposal.py','handoff/audit_tools/review_x20_83080_quarter.py')]
        # 固定本进程实际已加载的审计辅助依赖，避免只锁入口而遗漏导入核。
        for module in list(sys.modules.values()):
            filename=getattr(module,'__file__',None)
            if not filename:continue
            path=Path(filename).resolve()
            if path.suffix=='.py' and path.is_relative_to(core.ROOT/'handoff/audit_tools'):
                code.append(core.pipeline.claim(path))
        code=list({(c['path'],c['sha256']):c for c in code}.values())
        fields=d['fields'];paths=[Path(v['path']) for v in fields];before=[p.stat() for p in paths]
        core.reused.verify(small+code+fields);stop()
        shared.write(out/'declaration.json',dict(job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_job=85744,source_feedback_jobs=[84026,82989,82518],source_claims=small,code=code,fields=fields,geometry=d['geometry'],shape=d['shape'],global_coefficients=c,
            coefficient_l1_cap=17,step_safety=.9,objective=candidate['objective'],known_constraints=len(candidate['constraints']),known_sign_constraints=0,surface_denominator_branch=candidate['surface_denominator_branch'],
            new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,strict_error_bound=False,exact_full_domain_sign_certificate=False))
        mark('prediction_scan');p=measure_candidates(paths,d['shape'],c,geo,stop)
        shared.write(out/'prediction.json',p);mark('post_hash_check');core.reused.verify(small+code+fields)
        for path,b in zip(paths,before):
            n=path.stat();assert (n.st_ino,n.st_size,n.st_mtime_ns)==(b.st_ino,b.st_size,b.st_mtime_ns)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('RSS guard')
        status='prediction_passed_requires_review' if p['passed'] else 'prediction_rejected_requires_review'
        shared.write(out/'summary.json',dict(status=status,passed=p['passed'],checks=p['checks'],wall_s=time.monotonic()-started,peak_rss_bytes=peak,
            new_maps=0,new_feedback_pairs=0,new_material_steps=0,candidate_written=False,baseline_replaced=False,strict_error_bound=False,exact_full_domain_sign_certificate=False));mark(status)
    except BaseException as exc:mark('stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc));raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);run(p.parse_args().run)
