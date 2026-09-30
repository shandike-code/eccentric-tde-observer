"""One audited three-direction candidate, full-field prediction only."""
import argparse,json,math,os,resource,signal,subprocess,time
from pathlib import Path
import numpy as np
from operations import x20_history_operator as core
from operations import x20_cross_seed_chord as shared
from operations.x20_window_fields import measure_candidates


def require_candidate(candidate,audit,sha):
    if not audit.get('independent_70digit_spectral_witness') or audit.get('source_job')!=82166 or audit.get('result_sha256')!=sha:
        raise ValueError('independently audited candidate required')
    if not candidate.get('available_gates_passed') or not all(candidate['checks'].values()) or not candidate.get('search_limits_pass'):
        raise ValueError('small gates failed')
    raw=np.asarray(candidate['raw_coefficients']);selected=np.asarray(candidate['selected_coefficients'])
    if raw.shape!=(3,) or not np.isfinite(raw).all() or not np.array_equal(selected,.9*raw):raise ValueError('coefficient identity')
    if candidate['full_fraction']!=.9 or candidate['half_fraction']!=.45 or math.fsum(abs(np.r_[raw[0],1-math.fsum(raw),raw[1:]]))>17:
        raise ValueError('fractions or cap')
    if candidate['raw_coefficients']!=audit['raw_coefficients'] or candidate['selected_coefficients']!=audit['selected_coefficients']:raise ValueError('audit coefficient mismatch')
    if candidate['candidate_written'] or candidate['true_maps_evaluated'] or candidate['original_science_gates_changed']:raise ValueError('wrong scope')
    if any(candidate[k]!=0 for k in ('new_maps','new_feedback_pairs','new_material_steps')):raise ValueError('wrong budget')


def execute(out):
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('SLURM_CPUS_PER_TASK')!='4':raise RuntimeError('4 CPU allocation required')
    if out.is_absolute() or '..' in out.parts or out.parts[:2]!=('outputs','hpc'):raise ValueError('relative outputs/hpc required')
    out.mkdir(exist_ok=False);start=time.monotonic()
    def mark(status,**kw):shared.write(out/'status.json',dict(status=status,unix=time.time(),**kw))
    def checkpoint():
        if shared.STOP:raise InterruptedError('stop before next slab')
    mark('preflight')
    try:
        ev=Path('handoff/evidence');audit_path=ev/'20260930-x20-82166-review.json';a=shared.read(audit_path)
        if a['job_id']!=82166 or not a['independent_audit']:raise ValueError('basis audit required')
        source=Path('outputs/hpc/x20-window-basis-20260930');d=shared.read(source/'declaration.json')
        receipt=a['receipt'];arc=Path(receipt['path'])
        if shared.digest(arc)!=receipt['sha256'] or arc.stat().st_size!=receipt['size_bytes']:raise ValueError('basis archive')
        # Bind live declaration and full small basis bytes to the independently audited receipt.
        index={c['path']:c for c in receipt['files']}
        for name in ('declaration.json','basis.json','summary.json','status.json'):
            if shared.digest(source/name)!=index[name]['sha256']:raise ValueError('live basis differs')
        cp=ev/'20260930-x20-window-candidate-result.json';ap=ev/'20260930-x20-window-candidate-review.json'
        c=shared.read(cp);ca=shared.read(ap);require_candidate(c,ca,shared.digest(cp))
        fields=d['fields']
        if fields!=a['fields'] or d['shape']!=[9632,32,4096]:raise ValueError('source fields')
        gp=Path('outputs/hpc/x20-accelerated-feedback-windows-20260930/source-preflight/boundary_geometry.npz')
        with np.load(gp,allow_pickle=False) as z:geo={k:z[k] for k in ('mu','weight','width')}
        assert geo['mu'].shape==geo['weight'].shape==(32,) and geo['width'].shape==(9632,)
        assert all(np.isfinite(z).all() for z in geo.values()) and np.all(abs(geo['mu'])<=1) and np.all(geo['weight']>0) and np.all(geo['width']>0)
        small=d['small_claims']+[core.pipeline.claim(p) for p in (audit_path,arc,cp,ap,source/'declaration.json',source/'basis.json',gp)]
        code=core.fresh.code_claims()+[core.pipeline.claim(core.ROOT/p) for p in ('operations/x20_window_prediction.sbatch','tests/test_x20_window_fields.py','handoff/protocols/x20-window-prediction-v1.md')]
        core.reused.verify(small+d['code']+code)
        paths=[Path(c['path']) for c in fields];before=[p.stat() for p in paths]
        core.reused.verify(fields);checkpoint()
        shared.write(out/'declaration.json',dict(source_job=82166,source_claims=small,source_code=d['code'],code=code,fields=fields,
            shape=d['shape'],geometry=core.pipeline.claim(gp),job_id=os.environ['SLURM_JOB_ID'],
            git_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            raw_coefficients=c['raw_coefficients'],selected_coefficients=c['selected_coefficients'],full_fraction=.9,half_fraction=.45,
            maximum_full_field_reads=3,maximum_candidates=1,new_maps=0,new_feedback_pairs=0,new_material_steps=0,baseline_replaced=False,strict_error_bound=False))
        mark('prediction_scan')
        measured=measure_candidates(paths,d['shape'],c['selected_coefficients'],geo,checkpoint)
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
