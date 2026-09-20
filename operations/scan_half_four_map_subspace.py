"""Read-only four explicit map-pair scan for the identical half-step material.

No field is written and no physical map is evaluated. Prediction requires a
separate original-operator validation before it can seed formal feedback.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.radiation_history_diagnostic import identical_material
from operations.half_history_basis import last_actual_map
from operations.material_direction_diagnostic import latest_pair
from operations.scan_cross_history_direction import chunks, algebra
from operations.scan_multihistory_subspace import solve_direction, target_weights
from operations.scan_positive_subspace import solve_constrained

SOURCES = (
    ('outputs/hpc/half-step-base-seeded-20260920', '8018c8cccfc19c18e504fc6427e6d93a28d8475f85ebe580ca00bb40fd245efc'),
    ('outputs/hpc/half-step-precision-20260920', '29fef06e447124a94ea5972ee7aa7bb7a45356ec4ee60c9fec3aaac72c16ffbd'),
    ('outputs/hpc/half-history-feedback-20260920', '802cb30501090c91eabd0cccaf85a71732a24bedc980dcfc60f06fb36d87b89c'),
)
AUDIT = 'outputs/hpc/mixture-material-residual-audit-20260920/audit.json'
AUDIT_SHA = '48082cef1c1148b57b657084337759dd42c193084d628b58e66fee6b24cf415f'
MAX_PASSES, MAX_CUTS, L1_CAP = 6, 4096, 32.
ANCHOR = np.array([0., 0., 0., 1.])


def explicit_pairs(states):
    """Do not splice unrelated histories into a fictitious consecutive chain."""
    if len(states) != 3:
        raise ValueError('three declared source histories required')
    pairs = [last_actual_map(s) for s in states[:2]]
    last_actual_map(states[2])
    for row in states[2]['history'][-2:]:
        pairs.append([{'path': row[k+'_path'], 'sha256': row[k+'_sha256']} for k in ('input', 'output')])
    return pairs


def fields(arrays, weights):
    if len(arrays) != 8 or np.shape(weights) != (4,):
        raise ValueError('four explicit input/output pairs required')
    # 中文：系数和为1保留常数源；每一对都来自一次真实原算子映射。
    return tuple(sum(weights[i]*arrays[2*i+j] for i in range(4)) for j in (0, 1))


def residual_system(paths, shape):
    gram = np.zeros((3, 3)); rhs = np.zeros(3); anchor2 = 0.
    for _, a in chunks(paths, shape):
        r = np.stack([a[2*i+1]-a[2*i] for i in range(4)]).reshape(4, -1)
        d = r[[0, 2, 3]]-r[1]
        ra = ANCHOR @ r
        gram += d @ d.T; rhs -= d @ ra; anchor2 += float(ra @ ra)
    direction, info = solve_direction(gram, rhs)
    return target_weights(ANCHOR, direction), dict(info, gram=gram.tolist(), rhs=rhs.tolist(), anchor_residual_squared_l2=anchor2)


def collect_cuts(paths, shape, target):
    cuts = []; counts = [0, 0]; minima = [np.inf, np.inf]
    for start, a in chunks(paths, shape):
        for field, x in enumerate(fields(a, target)):
            if not np.isfinite(x).all():
                raise ArithmeticError('nonfinite predicted field')
            minima[field] = min(minima[field], float(x.min()))
            ids = np.flatnonzero(x < 0); counts[field] += len(ids)
            if not len(ids):
                continue
            values = np.stack([a[2*i+field].ravel()[ids] for i in range(4)], axis=1)
            scale = np.max(abs(values), axis=1)
            if np.any(scale <= 0):
                raise ArithmeticError('negative combination of zero basis')
            values /= scale[:, None]
            score = x.ravel()[ids]/scale
            # 中文：每块保留两个最强归一化约束，全场负值仍全部计数，最终重新扫全场。
            n = min(2, len(ids)); worst = np.argpartition(score, n-1)[:n]
            for j in worst:
                f, mu, z = np.unravel_index(ids[j], x.shape)
                v = values[j]
                cuts.append({'field': field, 'index': [int(start+f), int(mu), int(z)],
                             'row': (v[[0, 2, 3]]-v[1]).tolist(), 'lower': -float(v@ANCHOR)})
    return cuts, {'negative_counts': counts, 'minimum_fields': minima}


def coefficient_step(target):
    """One global coefficient step; never clip a grid element."""
    if np.sum(abs(target)) <= L1_CAP:
        return 1.
    lo, hi = 0., 1.
    for _ in range(64):
        mid = (lo+hi)/2
        if np.sum(abs(ANCHOR+mid*(target-ANCHOR))) <= L1_CAP:
            lo = mid
        else:
            hi = mid
    return float(np.nextafter(lo, 0.))


def prediction_metrics(paths, shape, weights, edges):
    mu, mw = algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    width = np.diff(edges)
    if width.shape != (shape[0],) or not np.isfinite(width).all() or np.any(width <= 0):
        raise ValueError('invalid frequency measure')
    maximum = scale = norm2 = num = fxscale = fyscale = bx = by = 0.
    negative = [0, 0]; minima = [np.inf, np.inf]
    for start, a in chunks(paths, shape):
        x, y = fields(a, weights)
        for j, v in enumerate((x, y)):
            if not np.isfinite(v).all():
                raise ArithmeticError('nonfinite full-field prediction')
            negative[j] += int(np.count_nonzero(v < 0)); minima[j] = min(minima[j], float(v.min()))
        residual = y-x
        maximum = max(maximum, float(np.max(abs(residual))))
        scale = max(scale, float(np.max(abs(x))), float(np.max(abs(y))))
        norm2 += float(np.sum(residual*residual))
        fx = algebra._block_flux(x, mu, mw, width[start:start+len(x)])
        fy = algebra._block_flux(y, mu, mw, width[start:start+len(y)])
        num += float(np.sum(abs(fy-fx))); fxscale += float(np.sum(abs(fx))); fyscale += float(np.sum(abs(fy)))
        bx += float(np.sum(fx)); by += float(np.sum(fy))
    if not np.isfinite([maximum, scale, norm2, num, fxscale, fyscale, bx, by]).all():
        raise ArithmeticError('nonfinite accumulated prediction metric')
    return {'predicted_residual': maximum/scale if scale > 0 else None,
            'predicted_residual_squared_l2': norm2,
            'predicted_boundary_l1': num/max(fxscale, fyscale) if max(fxscale, fyscale) > 0 else None,
            'predicted_boundary_bolometric': abs(by-bx)/max(abs(bx), abs(by)) if max(abs(bx), abs(by)) > 0 else None,
            'negative_counts': negative, 'minimum_fields': minima}


def checks(weights, metrics, best, rank, budget_resolved):
    finite = bool(np.isfinite(weights).all())
    return {'resolved_rank': rank == 3, 'constraint_budget_resolved': budget_resolved,
            'finite_coefficients': finite, 'coefficient_sum': finite and abs(float(np.sum(weights))-1) < 1e-12,
            'coefficient_cap': finite and float(np.sum(abs(weights))) <= L1_CAP,
            'full_field_nonnegative': metrics['negative_counts'] == [0, 0],
            'maximum_norm_improves_best': metrics['predicted_residual'] is not None and metrics['predicted_residual'] < .99*best,
            'boundary_l1': metrics['predicted_boundary_l1'] is not None and metrics['predicted_boundary_l1'] < 1e-3,
            'boundary_bolometric': metrics['predicted_boundary_bolometric'] is not None and metrics['predicted_boundary_bolometric'] < 1e-3}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running', 'new_maps': 0})
    try:
        audit = snap.read(AUDIT, AUDIT_SHA)
        if audit['mixture_final_replay_exact'] is not True or audit['new_maps'] != 0:
            raise RuntimeError('prior mixture audit not verified')
        states = []; trials = []; core = []; physical = []
        for source, digest in SOURCES:
            state = snap.read(source+'/state.json', digest); states.append(state)
            cfg = snap.read(source+'/config.json', state['config_sha256'])
            trial = load_arrays(snap.save(source+'/trial_material.npz', state['trial_sha256'])); trials.append(trial)
            audit_native_trial(cfg, trial)
            if cfg['shape'] != list(pipeline.SHAPE): raise RuntimeError('radiation grid differs')
            core.append({c['path']: c['sha256'] for c in cfg['sources'] if c['path'].startswith(('src/', 'scripts/', 'hpc/'))})
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
            pair = latest_pair(state)
            protocol = snap.read(str(Path(pair['ledger']).parent/'feedback_protocol.json'), pair['protocol_sha256'])
            physical.append({k: protocol['sources'][k] for k in ('physical_old_time_level', 'base_residual')})
        for trial in trials[1:]: identical_material(trials[0], trial)
        if not core[0] or not all(c == core[0] for c in core[1:]) or not all(c == physical[0] for c in physical[1:]):
            raise RuntimeError('frozen operator or old time level differs')
        pairs = explicit_pairs(states); basis = [c for pair in pairs for c in pair]
        for path in {c['path'] for c in basis}:
            if len({c['sha256'] for c in basis if c['path'] == path}) != 1:
                raise RuntimeError('conflicting hashes for one retained basis path')
        def verify_basis():
            for c in {c['path']: c for c in basis}.values():
                q = ROOT/c['path']
                if q.stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(q) != c['sha256']:
                    raise RuntimeError('basis bytes differ: '+c['path'])
        verify_basis()
        for name in ('scan_half_four_map_subspace.py', 'scan_half_four_map_subspace.sbatch', 'scan_positive_subspace.py',
                     'scan_multihistory_subspace.py', 'scan_cross_history_direction.py', 'half_history_basis.py',
                     'material_direction_diagnostic.py', 'radiation_history_diagnostic.py', 'prepare_encoded_backtrack.py', 'review_small_step_evidence.py'):
            snap.save('operations/'+name)
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        best = min(float(row['residual']) for s in states for row in s['history'][-2:])
        pipeline.write_json(out/'declaration.json', {'environment': pipeline.environment(), 'pairs': pairs,
            'pair_order': ['73929_last', '73888_last', '74057_previous', '74057_last'], 'anchor_weights': ANCHOR.tolist(),
            'maximum_cut_passes': MAX_PASSES, 'maximum_cuts': MAX_CUTS, 'coefficient_l1_cap': L1_CAP,
            'rank_requirement': 3, 'relative_rank_cutoff': 1e-12, 'rank_failure_action': 'stop; no rank or tolerance changes',
            'best_measured_residual': best, 'new_maps': 0, 'candidate_write_budget': 0, 'same_material_all_fields': True,
            'same_operator_and_old_time_level': True, 'objective': 'full-field radiation defect squared L2; independent maximum/boundary/positivity gates',
            'formula': 'X=sum(w_i X_i), Ypred=sum(w_i Y_i), sum(w_i)=1; original map required', 'source_audit_sha256': AUDIT_SHA})
        paths = [ROOT/c['path'] for c in basis]; cuts = {}; rounds = []; resolved = False
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            target, system = residual_system(paths, pipeline.SHAPE)
            pipeline.write_json(out/'residual_system.json', system)
            if system['retained_rank'] != 3:
                verify_basis()
                pipeline.write_json(out/'prediction.json', {'algebraic_feasibility': False, 'reason': 'unresolved_rank', 'system': system,
                    'candidate_written': False, 'actual_map_performed': False, 'accepted_material_step': False})
                pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0, 'outcome': 'no_resolved_candidate'})
                return
            for iteration in range(MAX_PASSES):
                additions, stats = collect_cuts(paths, pipeline.SHAPE, target)
                row = {'iteration': iteration, 'weights': target.tolist(), 'statistics': stats}; rounds.append(row)
                for c in additions: cuts.setdefault((c['field'], *c['index']), c)
                pipeline.write_json(out/'cut_progress.json', {'rounds': rounds, 'cuts': list(cuts.values())})
                if len(cuts) > MAX_CUTS: raise RuntimeError('declared cut budget exhausted')
                if not additions: resolved = True; break
                if iteration+1 < MAX_PASSES:
                    target, row['next_solve'] = solve_constrained(system['gram'], system['rhs'], ANCHOR,
                        [c['row'] for c in cuts.values()], [c['lower'] for c in cuts.values()])
            step = coefficient_step(target); weights = ANCHOR+step*(target-ANCHOR)
            metrics = prediction_metrics(paths, pipeline.SHAPE, weights, edges)
        gate = checks(weights, metrics, best, system['retained_rank'], resolved)
        verify_basis()
        pipeline.write_json(out/'prediction.json', {'system': system, 'raw_weights': target.tolist(), 'effective_weights': weights.tolist(),
            'anchor_weights': ANCHOR.tolist(), 'coefficient_step': step, 'prediction': metrics, 'checks': gate, 'rounds': rounds,
            'best_measured_residual': best, 'algebraic_feasibility': all(gate.values()), 'candidate_written': False,
            'actual_map_performed': False, 'accepted_material_step': False, 'full_constrained_optimum_proven': False})
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0, 'outcome': 'prediction_feasible' if all(gate.values()) else 'no_feasible_candidate'})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)}); raise


if __name__ == '__main__': main()
