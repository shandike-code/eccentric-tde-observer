"""Predict a bounded four-map residual-subspace step; never write a candidate."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_common_seed_precision import same_material
from operations.scan_cross_history_direction import chunks, latest_pair, BASE, OLD, algebra

VALIDATION = 'outputs/hpc/cross-history-map-validation-20260919'
RCOND = 1e-12
L1_CAP = 32.


def solve_direction(gram, rhs):
    """Solve only resolved PSD modes; report discarded algebraic directions."""
    gram, rhs = np.asarray(gram), np.asarray(rhs)
    if gram.shape != (3, 3) or rhs.shape != (3,) or not np.all(np.isfinite(gram)) or not np.all(np.isfinite(rhs)):
        raise ValueError('invalid small least-squares system')
    if not np.allclose(gram, gram.T, rtol=1e-12, atol=0): raise ValueError('Gram matrix is not symmetric')
    values, vectors = np.linalg.eigh(gram)
    scale = float(np.max(abs(values)))
    if values[0] < -RCOND*scale: raise ArithmeticError('Gram matrix is not positive semidefinite')
    keep = values > RCOND*scale
    c = vectors[:, keep] @ ((vectors[:, keep].T @ rhs)/values[keep]) if np.any(keep) else np.zeros(3)
    return c, {'eigenvalues': values.tolist(), 'retained_rank': int(keep.sum()), 'relative_cutoff': RCOND}


def target_weights(anchor, direction):
    """Parameterize sum(weights)=1 without renormalizing an intensity field."""
    w = np.array(anchor, dtype=float)
    w[[0, 2, 3]] += direction
    w[1] = 1.-(w[0]+w[2]+w[3])
    return w


def fields(arrays, weights):
    b0, b1, b2, o0, o1, o2 = arrays
    return (weights[0]*b0+weights[1]*b1+weights[2]*o0+weights[3]*o1,
            weights[0]*b1+weights[1]*b2+weights[2]*o1+weights[3]*o2)


def residual_system(paths, shape, anchor):
    gram = np.zeros((3, 3)); rhs = np.zeros(3); anchor2 = 0.
    for _, (b0, b1, b2, o0, o1, o2) in chunks(paths, shape):
        residuals = np.stack((b1-b0, b2-b1, o1-o0, o2-o1)).reshape(4, -1)
        # 中文：直接累加三个差残差，避免先做近等Gram大项相减。
        differences = residuals[[0, 2, 3]]-residuals[1]
        ra = anchor @ residuals
        gram += differences @ differences.T; rhs -= differences @ ra
        anchor2 += float(ra @ ra)
    direction, info = solve_direction(gram, rhs)
    return target_weights(anchor, direction), dict(info, gram=gram.tolist(), rhs=rhs.tolist(), anchor_residual_squared_l2=anchor2)


def bounded_step(paths, shape, anchor, target):
    upper = 1.; raw_negative = [0, 0]
    for _, arrays in chunks(paths, shape):
        for i, (a, b) in enumerate(zip(fields(arrays, anchor), fields(arrays, target))):
            if np.any(a < 0) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
                raise ArithmeticError('invalid subspace field')
            raw_negative[i] += int(np.count_nonzero(b < 0))
            delta = b-a; decreasing = delta < 0
            if np.any(decreasing): upper = min(upper, float(np.min(-a[decreasing]/delta[decreasing])))
    if not 0 <= upper <= 1: raise ArithmeticError('invalid global positivity step')
    # 中文：先沿一条全局方向取最大可行步，不截断单元；再限制仿射系数总幅度。
    cap = upper
    if np.sum(abs(anchor+cap*(target-anchor))) > L1_CAP:
        lo, hi = 0., cap
        for _ in range(64):
            mid = (lo+hi)/2
            if np.sum(abs(anchor+mid*(target-anchor))) <= L1_CAP: lo = mid
            else: hi = mid
        cap = lo
    if 0 < cap < 1: cap = float(np.nextafter(cap, 0.))
    return cap, {'positivity_step_upper': upper, 'selected_step': cap,
                 'raw_candidate_negative_count': raw_negative[0], 'raw_map_negative_count': raw_negative[1],
                 'raw_coefficient_l1': float(np.sum(abs(target))),
                 'effective_coefficient_l1': float(np.sum(abs(anchor+cap*(target-anchor))))}


def prediction_metrics(paths, shape, anchor, target, step, edges):
    mu, weight = algebra.gauss_legendre_split_mu_weights(shape[1], 0.); width = np.diff(edges)
    if width.shape != (shape[0],) or not np.all(np.isfinite(width)) or np.any(width <= 0):
        raise ValueError('invalid frequency measure')
    maximum = scale = norm2 = num = fxscale = fyscale = bx = by = 0.
    negative_x = negative_y = 0; minx = miny = np.inf
    for start, arrays in chunks(paths, shape):
        ax, ay = fields(arrays, anchor); tx, ty = fields(arrays, target)
        x, y = ax+step*(tx-ax), ay+step*(ty-ay)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)): raise ArithmeticError('nonfinite prediction')
        residual = y-x; maximum = max(maximum, float(np.max(abs(residual))))
        scale = max(scale, float(np.max(abs(x))), float(np.max(abs(y))))
        norm2 += float(np.sum(residual*residual)); negative_x += int(np.count_nonzero(x < 0)); negative_y += int(np.count_nonzero(y < 0))
        minx = min(minx, float(np.min(x))); miny = min(miny, float(np.min(y)))
        fx = algebra._block_flux(x, mu, weight, width[start:start+len(x)])
        fy = algebra._block_flux(y, mu, weight, width[start:start+len(y)])
        num += float(np.sum(abs(fy-fx))); fxscale += float(np.sum(abs(fx))); fyscale += float(np.sum(abs(fy)))
        bx += float(np.sum(fx)); by += float(np.sum(fy))
    return {'predicted_residual': maximum/scale if scale > 0 else None, 'predicted_residual_squared_l2': norm2,
            'predicted_boundary_l1': num/max(fxscale, fyscale) if max(fxscale, fyscale) > 0 else None,
            'predicted_boundary_bolometric': abs(by-bx)/max(abs(bx), abs(by)) if max(abs(bx), abs(by)) > 0 else None,
            'minimum_candidate': minx, 'minimum_map': miny, 'candidate_negative_count': negative_x, 'map_negative_count': negative_y}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        status = snap.read(VALIDATION+'/validation_status.json'); result = snap.read(VALIDATION+'/validation_result.json')
        if status['status'] != 'complete' or not result['extrapolation_validated'] or not result['full_field_error']['prediction_error_resolved']:
            raise RuntimeError('cross-history full-field validation must pass first')
        plan = snap.read(VALIDATION+'/validation_declaration.json'); g = float(plan['fraction'])
        anchor = np.array([0., 1+g, 0., -g])
        if np.any(anchor < 0) or abs(anchor.sum()-1) > 1e-14: raise RuntimeError('anchor is not a convex mixture')
        basis = []; trials = []
        for source in (BASE, OLD):
            state = snap.read(source+'/state.json'); pair = latest_pair(state)
            basis.extend([{'path': state['history'][0]['input_path'], 'sha256': state['history'][0]['input_sha256']}] + pair)
            cfg = snap.read(source+'/config.json', state['config_sha256'])
            trial = load_arrays(snap.save(source+'/trial_material.npz', state['trial_sha256'])); trials.append(trial)
            audit_native_trial(cfg, trial)
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
        same_material(*trials)
        if [basis[i] for i in (1, 2, 4, 5)] != plan['basis']: raise RuntimeError('anchor basis differs from validated mixture')
        for c in basis:
            if (ROOT/c['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT/c['path']) != c['sha256']:
                raise RuntimeError('basis SHA or size mismatch')
        for f in ('operations/scan_multihistory_subspace.py', 'operations/scan_multihistory_subspace.sbatch',
                  'operations/scan_cross_history_direction.py'): snap.save(f)
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        pipeline.write_json(out/'declaration.json', {'environment': pipeline.environment(), 'basis': basis, 'anchor_weights': anchor.tolist(),
            'rcond': RCOND, 'coefficient_l1_cap': L1_CAP, 'maximum_step': 1., 'new_maps': 0, 'candidate_write_budget': 0,
            'formula': 'candidate=anchor_field+t*(raw_four_map_combination-anchor_field); same formula for predicted map',
            'objective': 'full-field unweighted residual squared L2 in three resolved difference directions'})
        paths = [ROOT/c['path'] for c in basis]
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            target, system = residual_system(paths, pipeline.SHAPE, anchor)
            step, bounds = bounded_step(paths, pipeline.SHAPE, anchor, target)
            prediction = prediction_metrics(paths, pipeline.SHAPE, anchor, target, step, edges)
        best = result['actual_map']['residual']
        checks = {'resolved_subspace': system['retained_rank'] > 0, 'nonzero_step': step > 0,
                  'bounded_coefficients': bounds['effective_coefficient_l1'] <= L1_CAP,
                  'nonnegative_prediction': prediction['candidate_negative_count'] == prediction['map_negative_count'] == 0,
                  'maximum_norm_improves': prediction['predicted_residual'] is not None and prediction['predicted_residual'] < .99*best,
                  'boundary_l1_pass': prediction['predicted_boundary_l1'] is not None and prediction['predicted_boundary_l1'] < 1e-3,
                  'boundary_bolometric_pass': prediction['predicted_boundary_bolometric'] is not None and prediction['predicted_boundary_bolometric'] < 1e-3}
        for c in basis:
            if pipeline.sha256(ROOT/c['path']) != c['sha256']: raise RuntimeError('basis changed during scan')
        pipeline.write_json(out/'prediction.json', {'system': system, 'anchor_weights': anchor.tolist(), 'raw_weights': target.tolist(),
            'effective_weights': (anchor+step*(target-anchor)).tolist(), 'bounds': bounds, 'prediction': prediction, 'checks': checks,
            'algebraic_feasibility': all(checks.values()), 'best_measured_residual': best,
            'candidate_written': False, 'actual_map_performed': False, 'accepted_material_step': False})
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0, 'candidate_written': False})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__': main()
