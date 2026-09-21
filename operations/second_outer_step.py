"""One bounded nonlinear step from the precision-confirmed accepted material.

Rebase the nonlinear iterate, never the physical old time level. Preserve the
historical pipeline template and emit an explicit new denominator template.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import signal
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'scripts'), str(ROOT/'hpc')]
import pipeline
from operations import response_direction_batch as batch
from operations import composite_hybrid_batch as reused
from operations.constrained_hybrid_batch import relay_dispatch
from operations.prepare_encoded_backtrack import load_arrays
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from operations.radiation_history_diagnostic import identical_material

SOURCE = 'outputs/hpc/accepted-confirmation-20260921'
PHYSICAL_FIELDS = ('density_g_cm3', 'phase_index', 'step_duration_s')
DECODED_FIELDS = ('temperature_k', 'hydrogen_fraction', 'helium_fraction',
                  'specific_material_energy_erg_g')


def confirmed_source(parent, confirmation, state, summary):
    if (parent.get('status') != 'complete'
        or parent.get('precision_confirmation_passed') is not True
        or confirmation.get('precision_confirmation_passed') is not True
        or state['status'] != 'one_material_trial_accepted'
        or len(state['history']) != 2 or state.get('active_map') or state.get('pending_feedback')
        or set(summary['gate_checks']) != REQUIRED_GATES
        or not all(v is True for v in summary['gate_checks'].values())
        or summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] is not True):
        raise RuntimeError('source precision confirmation is not settled and accepted')
    if set(confirmation['cases']) != {'confirm2', 'confirm4'} or not all(
        c['all_original_gates'] is True and c['fresh_control_contraction'] is True
        for c in confirmation['cases'].values()):
        raise RuntimeError('incomplete precision confirmation evidence')


def rebase_trial(accepted, residual, old):
    """x1 is the accepted trial, not its unaccepted material-response target."""
    x = np.asarray(accepted['encoded_state']); r = np.asarray(residual)
    if x.shape != r.shape or not np.isfinite(x).all() or not np.isfinite(r).all() or not np.any(r):
        raise ValueError('invalid new baseline residual')
    phase = int(accepted['phase_index'])
    if (float(accepted['step_duration_s']) != float(old['step_duration_s'][phase])
        or not np.array_equal(accepted['density_g_cm3'], old['density_g_cm3'][phase])):
        raise ValueError('physical old time level changed')
    decoded = batch.GroundStateLogSimplexCodec(len(accepted['temperature_k'])).decode(x)
    for k in DECODED_FIELDS:
        if not np.array_equal(accepted[k], getattr(decoded, k)):
            raise ValueError('accepted trial differs from exact decode: '+k)
    result = {k: np.array(v, copy=True) for k, v in accepted.items()}
    result.update(base_encoded_state=x.copy(), base_residual=r.copy(),
                  finite_direction=r.copy(), relaxation=np.array(0.))
    return result


def validate_trial(trial, base, residual):
    alpha = float(trial['relaxation'])
    if alpha not in (0., *batch.ALPHAS.values()):
        raise ValueError('undeclared outer amplitude')
    if float(base['relaxation']) != 0 or not np.array_equal(base['encoded_state'], base['base_encoded_state']):
        raise ValueError('new base is not a zero control')
    for k in PHYSICAL_FIELDS:
        if not np.array_equal(trial[k], base[k]):
            raise ValueError('physical lineage mismatch: '+k)
    for k, expected in [('base_encoded_state', base['encoded_state']),
                        ('base_residual', residual), ('finite_direction', residual),
                        ('encoded_state', base['encoded_state']+alpha*residual)]:
        if not np.array_equal(trial[k], expected):
            raise ValueError('outer baseline/direction mismatch: '+k)
    if not np.array_equal(base['base_residual'], residual):
        raise ValueError('zero-control denominator mismatch')
    decoded = batch.GroundStateLogSimplexCodec(len(trial['temperature_k'])).decode(trial['encoded_state'])
    for k in DECODED_FIELDS:
        if not np.array_equal(trial[k], getattr(decoded, k)):
            raise ValueError('trial physical field differs from decode: '+k)


def rebase_payload(payload, cfg):
    """Replace only the declared nonlinear baseline, retaining original gates."""
    claims = cfg['outer_baseline']
    reused.verify(list(claims.values()))
    base = load_arrays(ROOT/claims['material']['path'])
    residual = np.load(ROOT/claims['residual']['path'], allow_pickle=False)
    trial_claim = payload['sources']['trial_material']; reused.verify([trial_claim])
    validate_trial(load_arrays(ROOT/trial_claim['path']), base, residual)
    if payload['sources']['physical_old_time_level'] != claims['physical_old_time_level']:
        raise RuntimeError('protocol physical old time level changed')
    result = deepcopy(payload)
    result['sources']['base_residual'] = claims['residual']
    result['sources']['outer_base_material'] = claims['material']
    result['outer_iteration'] = {
        'index': 2, 'source': SOURCE+'/confirm4',
        'base_is_accepted_trial': True, 'physical_time_advanced': False,
        'replaced_historical_denominator': payload['sources']['base_residual'],
        'direction_is_frozen_response_at_new_base': True,
    }
    return result


@contextmanager
def rebased_protocols():
    original = pipeline.feedback_protocol
    def build(cfg, state):
        legacy = original(cfg, state)
        payload = rebase_payload(pipeline.read(legacy), cfg)
        target = legacy.with_name('rebased_feedback_template.json')
        reused.immutable(target, payload)
        return target
    pipeline.feedback_protocol = build
    try:
        yield
    finally:
        pipeline.feedback_protocol = original


def prepare(out):
    path = out/'declaration.json'
    if path.exists():
        plan = pipeline.read(path); reused.verify(plan['pinned'])
        if plan['limits'] != batch.LIMITS or plan['alphas'] != batch.ALPHAS:
            raise RuntimeError('declared budget or amplitude changed')
        return plan
    snap = reused.Snapshot(out)
    parent = snap.read(SOURCE+'/status.json'); confirmation = snap.read(SOURCE+'/confirmation.json')
    folder = SOURCE+'/confirm4'; rd = folder+'/feedback-round1'
    state = snap.read(folder+'/state.json'); summary = snap.read(rd+'/feedback_summary.json')
    confirmed_source(parent, confirmation, state, summary)
    cfg = snap.read(folder+'/config.json', state['config_sha256']); reused.verify(cfg['sources'])
    accepted = load_arrays(snap.save(folder+'/trial_material.npz', state['trial_sha256']))
    rec = snap.read(rd+'/round_summary.json')
    proto = snap.read(rd+'/feedback_protocol.json', rec['protocol_sha256'])
    if summary['protocol_sha256'] != rec['protocol_sha256'] or proto['sources']['trial_material']['sha256'] != state['trial_sha256']:
        raise RuntimeError('source protocol or material mismatch')
    for c in proto['sources'].values():
        if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
    feedbacks = {}; vectors = {}
    for e, row in zip(('previous', 'final'), state['history'], strict=True):
        m = snap.read(rd+'/feedback/'+e+'_manifest.json'); c = proto['sources'][e+'_radiation']
        if (m['status'] != 'complete' or not m['state_gate_passed']
            or m['protocol_sha256'] != rec['protocol_sha256']
            or m['state_path'] != c['path'] or m['state_sha256'] != c['sha256']
            or row['input_path'] != c['path'] or row['input_sha256'] != c['sha256']
            or sorted(v['block_index'] for v in m['completed_blocks']) != list(range(76))):
            raise RuntimeError('confirmed feedback lineage failed')
        for b in m['completed_blocks']: snap.save(b['partial_path'], b['partial_sha256'])
        fb = load_arrays(snap.save(m['feedback_artifact_path'], m['feedback_artifact_sha256']))
        _, r, context = reused.pair._material_response_residual(proto, fb)
        feedbacks[e] = fb; vectors[e] = r
    stored = np.load(snap.save(summary['encoded_residual_path'], summary['encoded_residual_sha256']), allow_pickle=False)
    if not np.array_equal(stored, vectors['final']): raise RuntimeError('confirmed residual failed bitwise replay')
    old_baseline = np.load(ROOT/proto['sources']['base_residual']['path'], allow_pickle=False)
    if not np.array_equal(accepted['base_residual'], old_baseline): raise RuntimeError('source denominator mismatch')
    diag = reused.pair.trial_feedback_pair_diagnostics(
        previous_feedback=feedbacks['previous'], final_feedback=feedbacks['final'],
        previous_encoded_residual=vectors['previous'], final_encoded_residual=stored,
        base_encoded_residual=old_baseline, cell_width=feedbacks['final']['subcell_width_cm'],
        cell_mass=context['cell_mass'])
    checks = reused.pair.trial_feedback_pair_gate_checks(diag, proto['acceptance_gates'])
    if not all(checks.values()) or any(summary['gate_checks'][k] != v for k,v in checks.items()):
        raise RuntimeError('confirmed scientific gate failed replay')
    reused.immutable(out/'source-gate-replay.json', {'checks': checks,
        'residual_bitwise_equal': True, 'new_base_residual_norms': asdict(diag.candidate_norms),
        'physical_time_advanced': False})
    old = load_arrays(ROOT/proto['sources']['physical_old_time_level']['path'])
    base = rebase_trial(accepted, stored, old)
    residual_path = out/'base_residual.npy'
    if residual_path.exists():
        if not np.array_equal(np.load(residual_path, allow_pickle=False), stored): raise RuntimeError('base residual changed')
    else: np.save(residual_path, stored, allow_pickle=False)
    basefolder = out/'proposal-base'; basefolder.mkdir(exist_ok=True)
    basepath = basefolder/'trial_material.npz'
    if basepath.exists(): identical_material(base, load_arrays(basepath))
    else: np.savez(basepath, **base)
    claims = {'material': pipeline.claim(basepath), 'residual': pipeline.claim(residual_path),
              'physical_old_time_level': proto['sources']['physical_old_time_level']}
    cases = {}
    for label, alpha in [('base', 0.), *batch.ALPHAS.items()]:
        trial = base if label == 'base' else batch.make_trial(base, stored, alpha)
        validate_trial(trial, base, stored)
        dest = out/('proposal-'+label); dest.mkdir(exist_ok=True); tp = dest/'trial_material.npz'
        if tp.exists(): identical_material(trial, load_arrays(tp))
        else: np.savez(tp, **trial)
        identical_material(trial, load_arrays(tp))
        newcfg = deepcopy(cfg)
        newcfg.update(candidate_relaxation=alpha, outer_baseline=claims,
            physics_scope='second nonlinear material step; confirmed trial as base; unchanged physical old time')
        newcfg['sources'] = list(cfg['sources']) + list(claims.values())
        reused.immutable(dest/'config.json', newcfg)
        cases[label] = {'trial': pipeline.claim(tp), 'config': pipeline.claim(dest/'config.json')}
    row = state['history'][-1]
    if state['slots'][state['current_slot']] != row['output_path'] or state['current_sha256'] != row['output_sha256']:
        raise RuntimeError('seed is not latest confirmed-material output')
    seed = {'path': row['output_path'], 'sha256': row['output_sha256'], 'size_bytes': pipeline.STATE_BYTES}
    reused.verify([seed])
    code = [pipeline.claim(p) for folder in ('operations', 'diagnostics')
            for p in sorted((ROOT/folder).iterdir()) if p.suffix in ('.py', '.sbatch')]
    plan = {'environment': pipeline.environment(), 'cases': cases, 'code': code,
        'pinned': list(snap.records.values())+cfg['sources']+code+[seed]+list(claims.values())
            +[v for c in cases.values() for v in c.values()],
        'seed': seed, 'outer_baseline': claims, 'alphas': batch.ALPHAS, 'limits': batch.LIMITS,
        'maximum_maps': 18, 'maximum_pairs': 5, 'outer_step_index': 2,
        'physical_dt_changed': False, 'physical_time_advanced': False,
        'formal_baseline_changed': True, 'gates_relaxed': False,
        'automatic_resubmit': False, 'accepted_column': False}
    reused.immutable(path, plan)
    return plan


def execute(out):
    # Only this process adapts preparation/protocols; old modules on disk remain frozen.
    original = batch.prepare
    batch.prepare = prepare
    try:
        with rebased_protocols(): batch.execute(out)
    finally:
        batch.prepare = original


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run', required=True); a = p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0': raise RuntimeError('hugepage control required')
    out = pipeline.safe_path(ROOT, a.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=True)
    with (out/'batch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        signal.signal(signal.SIGUSR1, reused.stop); signal.signal(signal.SIGTERM, reused.stop)
        with relay_dispatch():
            try: execute(out)
            except reused.Stopped as exc:
                batch.mark(out, 'interrupted', reason=str(exc)); reused.archive(out, 'interrupted')
            except Exception as exc:
                pending = any(s.get('status') == 'diagnosis_incomplete' and s.get('pending_feedback', {}).get('stage') == 'ledger'
                              for s in batch.child_states(out).values())
                batch.mark(out, 'diagnosis_incomplete' if pending else 'failed', error=repr(exc))
                reused.archive(out, 'failed'); raise


if __name__ == '__main__': main()
