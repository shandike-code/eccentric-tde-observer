"""One read-only radiation candidate selected by a frozen thermal sensitivity proxy."""
import argparse
import os
import resource
import signal
import sys
import time
import numpy as np
from operations import scan_step21_restarted_plane as restart

wide=restart.wide
ROOT,pipeline,fresh=restart.ROOT,restart.pipeline,restart.fresh
SOURCE=restart.SOURCE


def heating_projection(q,dt,rho,reference_energy,mass):
    q=np.asarray(q,float);rho=np.asarray(rho,float)
    reference_energy=np.asarray(reference_energy,float);mass=np.asarray(mass,float)
    if mass.ndim!=1 or q.shape!=(4,mass.size) or rho.shape!=mass.shape or reference_energy.shape!=mass.shape:
        raise ValueError('four endpoint heating arrays and matching matter cells required')
    if not np.isfinite(dt) or dt<=0 or not all(np.isfinite(x).all() for x in (q,rho,reference_energy,mass)):
        raise ValueError('finite physical data required')
    if any(np.any(x<=0) for x in (rho,reference_energy,mass)):
        raise ValueError('positive reference gas energy, density and mass required')
    w=mass/mass.sum();scale=dt/rho/reference_energy
    early=(q[1]-q[0])*scale;late=(q[3]-q[2])*scale;direction=early-late
    norm=lambda x:float(np.sqrt(np.sum(w*x*x)))
    denominator=float(np.sum(w*direction*direction))
    if denominator<=0 or norm(late)<=0:raise ValueError('unresolved heating direction')
    alpha=-float(np.sum(w*late*direction))/denominator
    result={'alpha':alpha,'proxy_ratio':norm(late+alpha*direction)/norm(late),
        'source_proxy_norm':norm(late),'predicted_proxy_norm':norm(late+alpha*direction),
        'reference_energy_min_erg_g':float(reference_energy.min())}
    if not np.isfinite(list(result.values())).all():raise ArithmeticError('nonfinite proxy')
    return result


def screening_gates(field,proxy):
    # Keep all earlier radiation guards, including >1% maximum-residual improvement.
    expected={'positive','coefficient_l1','coefficient_sum','strict_inner','maximum_improves',
              'boundary_l1','boundary_bolometric'}
    if set(field['gates'])!=expected:raise ValueError('incomplete radiation guards')
    return {**field['gates'],'heating_proxy_cost_pass':0<=proxy['proxy_ratio']<.8}


def prepare():
    cases,claims,latest=restart.prepare()  # audited 77371, real successors, fixed trial/old/r20
    source=ROOT/SOURCE
    names=[f'control/pair{n:02d}/{e}_{kind}.npz' for n in (3,11)
           for e in ('previous','final') for kind in ('feedback','energy_ledger')]
    names+=['control/pair11/feedback_protocol.json','control/trial_material.npz']
    claims+=restart.validation.audited_inputs(source,ROOT/'handoff/evidence/20260925-wide-validation-complete-review.json',
        ROOT/'handoff/evidence/20260925-wide-validation-77371-terminal.json',77371,names)
    q=[];reference=None;emitted=None
    for n in (3,11):
        for e in ('previous','final'):
            feedback=restart.validation.load_arrays(source/f'control/pair{n:02d}/{e}_feedback.npz')
            book=restart.validation.load_arrays(source/f'control/pair{n:02d}/{e}_energy_ledger.npz')
            if not np.array_equal(book['q'],feedback['half_atomic_rate_heating_erg_s_cm3']):
                raise RuntimeError('ledger uses different heating')
            if emitted is None:emitted=feedback['emitted_power_erg_s_cm3']
            elif not np.array_equal(emitted,feedback['emitted_power_erg_s_cm3']):
                raise RuntimeError('fixed thermal emissivity changed')
            q.append(book['q']);reference=book['remaining']
    protocol=pipeline.read(source/'control/pair11/feedback_protocol.json')
    old=restart.validation.load_arrays(ROOT/protocol['sources']['physical_old_time_level']['path'])
    trial=restart.validation.load_arrays(source/'control/trial_material.npz')
    proxy=heating_projection(q,float(trial['step_duration_s']),trial['density_g_cm3'],reference,old['cell_mass_g_cm2'])
    # Freeze against the previously saved exploratory result; do not retune after field inspection.
    evidence=ROOT/'handoff/evidence/20260926-feedback-drift-localization.json'
    registered=pipeline.read(evidence)['exploratory_heating_projection']
    if not np.isclose(proxy['alpha'],registered['alpha'],rtol=1e-13,atol=0) or not np.isclose(
            proxy['proxy_ratio'],registered['linear_heating_proxy_ratio'],rtol=1e-13,atol=0):
        raise RuntimeError('predeclared proxy changed')
    claims.append(pipeline.claim(evidence))
    basis=cases['x1-x9-x10']['basis']
    selected=[basis[i] for i in (0,1,1,3,4,4)]
    claims=list({(c['path'],c['sha256']):c for c in claims}.values())
    fresh.reused.verify(claims)
    return selected,claims,latest,proxy


def execute(out):
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('hugepage control required')
    out.relative_to(ROOT/'outputs/hpc');out.mkdir(exist_ok=False)
    def mark(status,**kw):
        pipeline.write_json(out/'status.json',dict(status=status,updated_unix=time.time(),accepted_outer_steps=20,
            new_material_steps=0,new_maps=0,candidate_written=False,**kw))
    mark('preparing')
    try:
        basis,claims,latest,proxy=prepare()
        code=fresh.code_claims()+[pipeline.claim(ROOT/p) for p in ('operations/probe_step21_heating_projection.sbatch',
            'tests/test_probe_step21_heating_projection.py','handoff/protocols/step21-heating-projection-v1.md')]
        fresh.reused.immutable(out/'declaration.json',dict(basis=basis,claims=claims,code=code,environment=pipeline.environment(),
            source=SOURCE,latest_actual_residual=latest,proxy=proxy,uv=[0.,proxy['alpha']],
            candidate_budget=1,field_pass_budget=1,candidate_write_budget=0,map_budget=0,feedback_budget=0,
            accepted_outer_steps=20,automatic_promotion=False))
        with np.load(ROOT/pipeline.MASTER,allow_pickle=False) as z:edges=z['active_edge_hz'].copy()
        with np.errstate(invalid='raise',divide='raise',over='raise'):
            field=wide.inspect_fields([ROOT/c['path'] for c in basis],pipeline.SHAPE,(0.,proxy['alpha']),edges,latest,
                lambda **kw:mark('scanning',**kw))
        gates=screening_gates(field,proxy)
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>=6*1024**3:raise RuntimeError('memory guard')
        report=dict(proxy=proxy,field=field,gates=gates,eligible_for_independent_review=all(gates.values()),
            peak_rss_bytes=peak,actual_map_performed=False,actual_candidate_heating_computed=False,
            accepted_material_step=False,old_l2_cost_gate_reclassified=False)
        pipeline.write_json(out/'prediction.json',report)
        fresh.reused.verify(claims+code);mark('complete_requires_review');fresh.reused.archive(out,'complete')
    except BaseException as exc:
        mark('failed',error=repr(exc));fresh.reused.archive(out,'failed');raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    def stop(*_):raise InterruptedError('bounded heating projection stopped')
    for sig in (signal.SIGUSR1,signal.SIGTERM):signal.signal(sig,stop)
    execute(pipeline.safe_path(ROOT,args.run))
