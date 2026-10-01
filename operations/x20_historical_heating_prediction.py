"""One read-only field screen of a historical-only, heating-selected direction."""
import argparse,hashlib,json,os,resource,signal,subprocess,tarfile,time
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import measure_candidates
from handoff.audit_tools.verify_x20_bounded_gram import check


RUNS={81769:'x20-accelerated-feedback-windows-20260930',82273:'x20-window-feedback-20260930',82518:'x20-global-window-feedback-20261001'}
LOCAL={81769:'x20-feedback-81769-complete-received',82273:'x20-feedback-82273-complete-received',82518:'x20-global-feedback-82518-complete-received'}


def live_path(path):
    for job,folder in LOCAL.items():
        prefix='outputs/review-20260925/'+folder+'/'
        if path.startswith(prefix):return Path('outputs/hpc')/RUNS[job]/path[len(prefix):]
    return Path(path)


def require_screen(s):
    if (not s.get('screening_only') or not s.get('independent_supporting_plane_check')
            or s.get('coefficient_l1_cap')!=17 or s.get('step_safety')!=.9
            or s.get('field_order')!=['82518-H16-previous/final','82273-H16-previous/final','81769-H16-previous/final','82518-H8-previous/final']
            or any(s.get(k)!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps'))
            or any(s.get(k) is not False for k in ('candidate_written','true_map_evaluated','baseline_replaced','full_field_positivity_checked','field_l2_benefit_checked','boundary_checked'))):
        raise ValueError('wrong screen identity or scope')
    gram=[[F(int(v['numerator']),int(v['denominator'])) for v in row] for row in s['exact_stored_vector_gram']]
    check(gram,s['bounded_solution'])
    raw=[F(int(v['numerator']),int(v['denominator'])) for v in s['bounded_solution']['coefficients_exact']]
    c=s['selected_coefficients']
    if c!=[float(F(9,10)*v) for v in raw]:raise ValueError('changed coefficient or safety')
    if abs(1-sum(map(F,c)))+sum(abs(F(v)) for v in c)>17:raise ValueError('cap')
    return c


def execute(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);start=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def checkpoint():
        if shared.STOP:raise InterruptedError('stop before next slab')
    mark('preflight')
    try:
        sp=Path('handoff/evidence/20261001-x20-historical-heating-screen-v2.json');s=shared.read(sp);c=require_screen(s)
        small=[]
        for claim in s['source_claims']:
            p=live_path(claim['path'])
            if shared.digest(p)!=claim['sha256']:raise ValueError('changed screen source '+str(p))
            small.append(core.pipeline.claim(p))
        fields=[];configs=[];trials=[]
        for job,n in [(82518,16),(82273,16),(81769,16),(82518,8)]:
            ap=Path(f'handoff/evidence/{"20261001" if job==82518 else "20260930"}-x20-{job}-final-review.json')
            audit=shared.read(ap);arc=Path(audit['archive']['path'])
            if not audit['completed_experiment'] or not audit['all_original_zero_gates_passed'] or audit['job_id']!=job:raise ValueError('complete source required')
            if arc.stat().st_size!=audit['archive']['size_bytes'] or shared.digest(arc)!=audit['archive']['sha256']:raise ValueError('source archive')
            root=Path('outputs/hpc')/RUNS[job]/'historical';mp=root/f'endpoints-map{n:02d}/manifest.json';m=shared.read(mp)
            r0,r1=m['history_rows']
            if (r0['iteration'],r1['iteration'])!=(n-1,n) or r0['output_sha256']!=r1['input_sha256']:raise ValueError('adjacent pair')
            if m['endpoints']['previous']['sha256']!=r0['input_sha256'] or m['endpoints']['final']['sha256']!=r1['input_sha256']:raise ValueError('endpoint identity')
            fields.extend(m['endpoints'][e] for e in ('previous','final'))
            configs.append(shared.read(root/'config.json'));trials.append(shared.digest(root/'trial_material.npz'))
            small += [core.pipeline.claim(p) for p in (ap,arc,mp,root/'config.json',root/'trial_material.npz')]
        if fields!=s['fields'] or len(set(trials))!=1:raise ValueError('field or material identity')
        for cfg in configs:core.same_operator_config(configs[0],cfg)
        if configs[0]['shape']!=[9632,32,4096]:raise ValueError('full domain required')
        gp=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930/source-preflight/boundary_geometry.npz')
        declaration=Path('outputs/hpc')/RUNS[82273]/'declaration.json'
        source_audit=shared.read('handoff/evidence/20260930-x20-82273-final-review.json')
        with tarfile.open(source_audit['archive']['path']) as archive:
            if hashlib.sha256(archive.extractfile('declaration.json').read()).hexdigest()!=shared.digest(declaration):raise ValueError('geometry declaration provenance')
        original=shared.read(declaration);small.append(core.pipeline.claim(declaration))
        gc=[v for v in original['claims'] if v['path']==str(gp)]
        if len(gc)!=1:raise ValueError('geometry source claim')
        core.reused.verify(gc)
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(v).all() for v in geo.values()) and np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_historical_heating_prediction.sbatch','tests/test_x20_historical_heating_prediction.py','tests/test_x20_window_fields.py','handoff/audit_tools/verify_x20_bounded_gram.py','handoff/protocols/x20-historical-heating-prediction-v1.md')]
        small += [core.pipeline.claim(p) for p in (sp,gp)]
        core.reused.verify(small+code+fields);checkpoint()
        paths=[Path(v['path']) for v in fields];before=[p.stat() for p in paths]
        shared.write(out/'declaration.json',dict(source_jobs=[81769,82273,82518],source_claims=small,code=code,fields=fields,shape=configs[0]['shape'],geometry=core.pipeline.claim(gp),job_id=os.environ['SLURM_JOB_ID'],git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),global_coefficients=c,coefficient_mode='one_global_historical_triple',screen_sha256=shared.digest(sp),maximum_full_field_reads=3,maximum_candidates=1,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark('prediction_scan');measured=measure_candidates(paths,configs[0]['shape'],c,geo,checkpoint)
        shared.write(out/'prediction.json',measured);mark('post_hash_check');core.reused.verify(fields+small+code)
        for p,b in zip(paths,before):
            now=p.stat()
            if (b.st_ino,b.st_size,b.st_mtime_ns)!=(now.st_ino,now.st_size,now.st_mtime_ns):raise RuntimeError('field changed')
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        if peak>=6*1024**3:raise RuntimeError('parent RSS guard')
        status='prediction_passed_requires_review' if measured['passed'] else 'prediction_rejected_requires_review'
        shared.write(out/'summary.json',dict(status=status,passed=measured['passed'],checks=measured['checks'],candidate_written=False,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,peak_rss_bytes=peak,wall_s=time.monotonic()-start));mark(status)
    except BaseException as exc:mark('stopped' if isinstance(exc,InterruptedError) else 'failed',error=repr(exc));raise


if __name__=='__main__':
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,shared.stop)
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);execute(p.parse_args().run)
