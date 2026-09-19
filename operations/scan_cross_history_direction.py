"""Read-only, positivity-bounded residual minimization along a history difference.

X(g)=X_base+g*(X_base-X_old); predicted T(X(g)) uses the same affine
combination of the two measured outputs. This prediction needs a fresh map.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.audit_affine_feedback_histories import BASE, OLD, require_settled_pair
from operations.prepare_common_seed_precision import same_material
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.review_small_step_evidence import Snapshot
from scripts import phase7b9bx_slow_mode_anderson as algebra

AUDIT = 'outputs/hpc/affine-feedback-history-audit-20260919'
COEFFICIENT_L1_CAP = 32.


def latest_pair(state):
    require_settled_pair(state)
    a, b = state['history']
    if (a['output_path'] != b['input_path'] or a['output_sha256'] != b['input_sha256']
        or state['slots'][state['current_slot']] != b['output_path']
        or state['current_sha256'] != b['output_sha256']):
        raise RuntimeError('source does not retain its latest consecutive real map')
    return [{'path': b[k+'_path'], 'sha256': b[k+'_sha256']} for k in ('input', 'output')]


def chunks(paths, shape, frequency_chunk=16):
    """Ordinary read-only streams keep the resident set bounded."""
    with ExitStack() as stack:
        streams = [stack.enter_context(Path(p).open('rb')) for p in paths]
        for start in range(0, shape[0], frequency_chunk):
            n = min(frequency_chunk, shape[0]-start)
            count = n * shape[1] * shape[2]
            arrays = [np.fromfile(f, dtype=np.float64, count=count) for f in streams]
            if any(a.size != count for a in arrays): raise RuntimeError('short basis read')
            if any(not np.all(np.isfinite(a)) or np.any(a < 0) for a in arrays):
                raise ArithmeticError('radiation basis must be finite and nonnegative')
            yield start, [a.reshape(n, shape[1], shape[2]) for a in arrays]
        if any(f.read(1) for f in streams): raise RuntimeError('unexpected basis tail')


def positive_interval(base, difference):
    """Exact scalar interval for base + g*difference >= 0, without cell clipping."""
    positive, negative = difference > 0, difference < 0
    lower = float(np.max(-base[positive]/difference[positive])) if positive.any() else -np.inf
    upper = float(np.min(-base[negative]/difference[negative])) if negative.any() else np.inf
    return lower, upper


def scan(paths, shape):
    # 中文：系数和恒为1，保留冻结算子的常数源；只限制一个全局系数，不修正单元值。
    lower, upper = -(COEFFICIENT_L1_CAP+1)/2, (COEFFICIENT_L1_CAP-1)/2
    rb2 = ro2 = dr2 = rb_dr = dx2 = dy2 = 0.
    for _, (xb, yb, xo, yo) in chunks(paths, shape):
        rb, ro = yb-xb, yo-xo
        dr = rb-ro; dx = xb-xo; dy = yb-yo
        rb2 += float(np.sum(rb*rb)); ro2 += float(np.sum(ro*ro))
        dr2 += float(np.sum(dr*dr)); rb_dr += float(np.sum(rb*dr))
        dx2 += float(np.sum(dx*dx)); dy2 += float(np.sum(dy*dy))
        for base, diff in ((xb, dx), (yb, dy)):
            lo, hi = positive_interval(base, diff)
            lower, upper = max(lower, lo), min(upper, hi)
    if not np.all(np.isfinite([rb2, ro2, dr2, rb_dr, dx2, dy2, lower, upper])):
        raise ArithmeticError('nonfinite accumulated direction metric')
    if not lower <= 0 <= upper: raise ArithmeticError('nonnegative basis lost g=0 feasibility')
    if lower < 0: lower = float(np.nextafter(lower, 0.))
    if upper > 0: upper = float(np.nextafter(upper, 0.))
    raw = -rb_dr/dr2 if dr2 > 0 else None
    selected = min(max(raw, lower), upper) if raw is not None else 0.
    return {'gamma_unconstrained': raw, 'gamma': selected, 'feasible_interval': [lower, upper],
            'coefficients': [1+selected, -selected], 'coefficient_l1': abs(1+selected)+abs(selected),
            'base_residual_squared_l2': rb2, 'old_residual_squared_l2': ro2,
            'residual_difference_squared_l2': dr2,
            'direction_resolution_ratio': dr2/max(rb2, ro2) if max(rb2, ro2) > 0 else 0.,
            'relative_operator_change_along_history_difference': np.sqrt(dr2/dx2) if dx2 > 0 else None,
            'history_difference_image_l2_ratio': np.sqrt(dy2/dx2) if dx2 > 0 else None}


def metrics(paths, shape, gamma, edges):
    mu, weight = algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    widths = np.diff(edges)
    if widths.shape != (shape[0],) or not np.all(np.isfinite(widths)) or np.any(widths <= 0):
        raise ValueError('invalid frequency measure')
    maximum_change = scale = residual_l2_squared = 0.
    negative_x = negative_y = 0; minimum_x = minimum_y = np.inf
    flux_num = flux_x = flux_y = bol_x = bol_y = 0.
    for start, (xb, yb, xo, yo) in chunks(paths, shape):
        x, y = xb+gamma*(xb-xo), yb+gamma*(yb-yo)
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise ArithmeticError('nonfinite affine prediction')
        residual = y-x
        maximum_change = max(maximum_change, float(np.max(abs(residual))))
        scale = max(scale, float(np.max(abs(x))), float(np.max(abs(y))))
        residual_l2_squared += float(np.sum(residual*residual))
        minimum_x = min(minimum_x, float(np.min(x))); minimum_y = min(minimum_y, float(np.min(y)))
        negative_x += int(np.count_nonzero(x < 0)); negative_y += int(np.count_nonzero(y < 0))
        fx = algebra._block_flux(x, mu, weight, widths[start:start+len(x)])
        fy = algebra._block_flux(y, mu, weight, widths[start:start+len(y)])
        flux_num += float(np.sum(abs(fy-fx))); flux_x += float(np.sum(abs(fx))); flux_y += float(np.sum(abs(fy)))
        bol_x += float(np.sum(fx)); bol_y += float(np.sum(fy))
    return {'predicted_residual': maximum_change/scale if scale > 0 else None,
            'predicted_residual_squared_l2': residual_l2_squared,
            'predicted_boundary_l1': flux_num/max(flux_x, flux_y) if max(flux_x, flux_y) > 0 else None,
            'predicted_boundary_bolometric': abs(bol_y-bol_x)/max(abs(bol_x), abs(bol_y)) if max(abs(bol_x), abs(bol_y)) > 0 else None,
            'minimum_candidate': minimum_x, 'minimum_predicted_map': minimum_y,
            'candidate_negative_count': negative_x, 'predicted_map_negative_count': negative_y}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        if snap.read(AUDIT+'/status.json')['status'] != 'complete': raise RuntimeError('paired audit incomplete')
        states = [snap.read(source+'/state.json') for source in (BASE, OLD)]
        configs = [snap.read(source+'/config.json', state['config_sha256']) for source, state in zip((BASE, OLD), states)]
        trials = [load_arrays(snap.save(source+'/trial_material.npz', state['trial_sha256'])) for source, state in zip((BASE, OLD), states)]
        same_material(*trials)
        for cfg, trial in zip(configs, trials): audit_native_trial(cfg, trial)
        for cfg in configs:
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
        basis = [c for state in states for c in latest_pair(state)]
        for c in basis:
            if (ROOT/c['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT/c['path']) != c['sha256']:
                raise RuntimeError('basis SHA or size changed')
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        for name in ('operations/scan_cross_history_direction.py', 'operations/scan_cross_history_direction.sbatch',
                     'operations/audit_affine_feedback_histories.py', 'scripts/phase7b9bx_slow_mode_anderson.py'):
            snap.save(name)
        plan = {'environment': pipeline.environment(), 'basis': basis, 'formula': 'X=XB+g*(XB-XO); Ypred=YB+g*(YB-YO)',
                'objective': 'unweighted full-field predicted residual squared L2; actual maximum norm must improve separately',
                'coefficient_l1_cap': COEFFICIENT_L1_CAP, 'physical_dt_changed': False, 'new_maps': 0,
                'candidate_write_budget': 0, 'fresh_original_map_required': True}
        pipeline.write_json(out/'declaration.json', plan)
        paths = [ROOT/c['path'] for c in basis]
        with np.errstate(invalid='raise', divide='raise', over='raise'):
            direction = scan(paths, pipeline.SHAPE)
            prediction = metrics(paths, pipeline.SHAPE, direction['gamma'], edges)
        best = min(s['history'][-1]['residual'] for s in states)
        checks = {'resolved_direction': direction['direction_resolution_ratio'] > 1e-12,
                  'nonzero_coefficient': direction['gamma'] != 0.,
                  'bounded_coefficients': direction['coefficient_l1'] <= COEFFICIENT_L1_CAP,
                  'nonnegative_prediction': prediction['candidate_negative_count'] == prediction['predicted_map_negative_count'] == 0,
                  'maximum_norm_improves_best_history': prediction['predicted_residual'] is not None and prediction['predicted_residual'] < .99*best,
                  'boundary_spectrum_pass': prediction['predicted_boundary_l1'] is not None and prediction['predicted_boundary_l1'] < 1e-3,
                  'boundary_bolometric_pass': prediction['predicted_boundary_bolometric'] is not None and prediction['predicted_boundary_bolometric'] < 1e-3}
        for c in basis:
            if pipeline.sha256(ROOT/c['path']) != c['sha256']: raise RuntimeError('basis changed during scan')
        pipeline.write_json(out/'prediction.json', {'direction': direction, 'prediction': prediction, 'checks': checks,
            'algebraic_feasibility': all(checks.values()), 'best_measured_residual': best,
            'actual_map_performed': False, 'candidate_written': False, 'accepted_material_step': False,
            'limitations': ['Predicted affinity needs a fresh full-field map.', 'A small operator residual is not a feedback-error bound.',
                            'The history-difference image ratio does not prove a global contraction or uniqueness.']})
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0, 'candidate_written': False})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__': main()
