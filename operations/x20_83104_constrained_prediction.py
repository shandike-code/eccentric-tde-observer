"""One global constrained candidate; full original field screen, no map or dat write."""
import argparse,os,resource,signal,subprocess,time
from pathlib import Path
from fractions import Fraction as F
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import measure_candidates
from handoff.audit_tools.solve_x20_83104_constrained import inputs,verify,dot
from handoff.audit_tools.verify_x20_bounded_gram import rational


def live_path(p):
    lookup={'outputs/review-20260925/x20-constrained-basis-83104-received/basis.json':'outputs/hpc/x20-83080-constrained-basis-20261001/basis.json',
        'outputs/review-20260925/x20-subnormal-audit-83075-received/exact-signs.json':'outputs/hpc/x20-83063-subnormal-audit-20261001/exact-signs.json'}
    return Path(lookup.get(str(p),str(p)))


def require_candidate(candidate,g,gr,gh,faces):
    if (candidate.get('source_job')!=83104 or candidate.get('coefficient_l1_cap')!=17 or candidate.get('step_safety')!=.9
        or not candidate.get('exact_kkt_verified') or not candidate.get('selected_known_constraints_exactly_verified')
        or candidate.get('full_field_nonnegative_verified') is not False or candidate.get('true_map_verified') is not False
        or any(candidate.get(k)!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps'))
        or candidate.get('candidate_written') is not False or candidate.get('baseline_replaced') is not False):raise ValueError('wrong constrained screen scope')
    for name,mat in [('objective_gram',g),('radiation_gram',gr),('heating_gram',gh)]:
        if [[rational(v) for v in row] for row in candidate[name]]!=mat:raise ValueError('changed Gram source')
    if [([rational(v) for v in c['normal']],rational(c['limit'])) for c in candidate['constraints']]!=faces:raise ValueError('changed constraints')
    r=dict(coefficients=[rational(v) for v in candidate['coefficients_exact']],multipliers=[rational(v) for v in candidate['multipliers_exact']],active=candidate['active'],value=rational(candidate['objective_value']))
    verify(g,faces,r)
    c=candidate['selected_coefficients']
    if c!=[float(F(9,10)*v) for v in r['coefficients']]:raise ValueError('changed safety or rounding')
    if not all(dot(row,list(map(F,c)))<=limit for row,limit in faces):raise ValueError('rounded candidate violates known constraint')
    return c


def run(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);started=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def stop():
        if shared.STOP:raise InterruptedError('stop before next slab')
    mark('preflight')
    try:
        cp=Path('handoff/evidence/20261002-x20-83104-constrained-candidate.json');candidate=shared.read(cp)
        for claim in candidate['source_claims']:
            p=live_path(claim['path']);assert p.stat().st_size==claim['size_bytes'] and shared.digest(p)==claim['sha256']
        g,gr,gh,faces,tuples,claims=inputs(live_path)
        assert candidate['known_source_tuples']==[list(t) for t in tuples]
        c=require_candidate(candidate,g,gr,gh,faces)
        bp=Path('outputs/hpc/x20-83080-constrained-basis-20261001/declaration.json')
        audit=shared.read('handoff/evidence/20261002-x20-constrained-basis-83104-review.json');ix={v['path']:v for v in audit['receipt']['files']}
        assert shared.digest(bp)==ix['declaration.json']['sha256'];d=shared.read(bp)
        assert d['fields']==audit['fields'] and d['shape']==[9632,32,4096]
        gp=Path(d['geometry']['path']);core.reused.verify([d['geometry']])
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values())
        assert np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=claims+[core.pipeline.claim(p) for p in (cp,bp,gp)]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in (
            'operations/x20_83104_constrained_prediction.sbatch','tests/test_x20_83104_constrained.py','handoff/protocols/x20-83104-constrained-prediction-v1.md',
            'handoff/audit_tools/solve_x20_83104_constrained.py','handoff/audit_tools/bounded_window_gram.py','handoff/audit_tools/verify_x20_bounded_gram.py','handoff/audit_tools/analyze_x20_latest_gram.py')]
        fields=d['fields'];paths=[Path(v['path']) for v in fields];before=[p.stat() for p in paths]
        core.reused.verify(small+code+fields);stop()
        shared.write(out/'declaration.json',dict(job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_job=83104,sign_audit_job=83075,source_claims=small,code=code,fields=fields,geometry=d['geometry'],shape=d['shape'],global_coefficients=c,
            coefficient_l1_cap=17,step_safety=.9,objective=candidate['objective'],known_constraints=len(faces),known_source_tuples=len(tuples),
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
