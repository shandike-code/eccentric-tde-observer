"""Bounded cutting-plane diagnostic in the existing three-dimensional subspace.

This writes no intensity candidate and runs no transfer map. Every proposed
combination is scanned over the complete field; sampled cuts never certify it.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import os
from pathlib import Path
import sys
import numpy as np
from scipy.optimize import minimize, LinearConstraint

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_common_seed_precision import same_material, latest_seed
from operations.scan_multihistory_subspace import (
    fields, chunks, target_weights, bounded_step, prediction_metrics, solve_direction,
)

SCAN = 'outputs/hpc/multihistory-subspace-scan-20260919'
LATEST = 'outputs/hpc/cross-mixture-feedback-20260919'
BASE = 'outputs/hpc/affine-base-feedback-20260919'
OLD = 'outputs/hpc/affine-old-feedback-20260919'
MAX_PASSES = 6
MAX_CUTS = 4096
L1_CAP = 32.
B = np.array([[1., 0., 0.], [-1., -1., -1.], [0., 1., 0.], [0., 0., 1.]])


def solve_constrained(gram, rhs, anchor, rows, lower):
    """Small convex QP, with explicit failure and finite-coefficient checks."""
    gram, rhs, anchor = map(lambda x: np.asarray(x, dtype=float), (gram, rhs, anchor))
    _, audit = solve_direction(gram, rhs)
    if audit['retained_rank'] != 3:
        raise ValueError('this diagnostic requires all three resolved modes')
    rows = np.asarray(rows, dtype=float).reshape(-1, 3)
    lower = np.asarray(lower, dtype=float)
    if lower.shape != (len(rows),) or not np.all(np.isfinite(rows)) or not np.all(np.isfinite(lower)):
        raise ValueError('invalid positivity cuts')
    if anchor.shape != (4,) or not np.all(np.isfinite(anchor)) or np.any(anchor < 0) or abs(anchor.sum()-1) > 1e-14:
        raise ValueError('anchor must be a convex combination')
    if np.any(lower > 0):
        raise ValueError('the convex anchor must satisfy every cut')
    # 中文：四系数的L1上限等价于全部16种符号的线性不等式，不裁剪强度。
    signs = np.array(list(itertools.product((-1., 1.), repeat=4)))
    matrix = np.vstack((rows, -signs @ B))
    bounds = np.r_[lower, signs @ anchor-L1_CAP]
    values, vectors = np.linalg.eigh(gram)
    scale = float(values[-1])
    # 中文：在已可分辨的三个代数方向上白化二次型，不改物理场或残差目标。
    transform = vectors*np.sqrt(scale/values)[None, :]
    h = transform.T@rhs/scale
    result = minimize(lambda z: .5*z@z-h@z, np.zeros(3),
                      jac=lambda z: z-h, method='SLSQP',
                      constraints=LinearConstraint(matrix@transform, bounds, np.inf),
                      options={'maxiter': 200, 'ftol': 1e-12})
    if not result.success or not np.all(np.isfinite(result.x)):
        raise ArithmeticError(f'constrained solve failed: {result.message}')
    direction = transform@result.x
    violation = float(np.max(bounds-matrix@direction))
    if violation > 1e-10:
        raise ArithmeticError('small-system constraint violation')
    return target_weights(anchor, direction), {
        'iterations': int(result.nit), 'objective': float(result.fun),
        'gram_condition_number': float(values[-1]/values[0]),
        'maximum_linear_constraint_violation': violation,
        'note': 'solver tolerance does not certify field positivity; full-field scan and global backtracking follow',
    }


def collect_cuts(paths, shape, anchor, target, per_chunk=16):
    """Locate every negative cell; retain a bounded set of worst normalized cuts."""
    cuts = []
    stats = {name: {'negative_count': 0, 'block_counts': [0]*((shape[0]+127)//128),
                    'minimum_raw_intensity': 0., 'positivity_step_upper': 1., 'limiting_cell': None}
             for name in ('candidate', 'predicted_map')}
    for start, arrays in chunks(paths, shape):
        af, tf = fields(arrays, anchor), fields(arrays, target)
        pair_basis = ((arrays[0], arrays[1], arrays[3], arrays[4]),
                      (arrays[1], arrays[2], arrays[4], arrays[5]))
        for name, a, x, basis in zip(stats, af, tf, pair_basis):
            if np.any(a < 0) or not np.all(np.isfinite(x)):
                raise ArithmeticError('invalid anchor or proposed field')
            row = stats[name]; mask = x < 0
            row['negative_count'] += int(mask.sum())
            row['minimum_raw_intensity'] = min(row['minimum_raw_intensity'], float(x.min()))
            for j, count in enumerate(mask.sum(axis=(1, 2))):
                row['block_counts'][(start+j)//128] += int(count)
            ids = np.flatnonzero(mask)
            if not ids.size:
                continue
            selected_basis = np.stack([q.ravel()[ids] for q in basis], axis=1)
            # 中文：只缩放约束方程，不改变任何强度；避免极弱尾端被绝对容差吞掉。
            magnitude = np.max(abs(selected_basis), axis=1)
            if np.any(magnitude <= 0):
                raise ArithmeticError('negative combination from an all-zero basis')
            norm_values = selected_basis/magnitude[:, None]
            score = x.ravel()[ids]/magnitude
            k = min(per_chunk, len(ids))
            worst = np.argpartition(score, k-1)[:k]
            # 极弱单元先缩放再求比例，避免分母下溢；不把小值判作零。
            ratio = (a.ravel()[ids]/magnitude)/((a.ravel()[ids]-x.ravel()[ids])/magnitude)
            limiter = int(np.argmin(ratio))
            if float(ratio[limiter]) < row['positivity_step_upper']:
                fi, mu, depth = np.unravel_index(ids[limiter], a.shape)
                row['positivity_step_upper'] = float(ratio[limiter])
                row['limiting_cell'] = {'frequency_index': int(start+fi), 'angle_index': int(mu),
                    'radiation_depth_index': int(depth), 'anchor_intensity': float(a.ravel()[ids[limiter]]),
                    'raw_intensity': float(x.ravel()[ids[limiter]]), 'basis_intensities': selected_basis[limiter].tolist()}
            for j in worst:
                fi, mu, depth = np.unravel_index(ids[j], a.shape)
                values = norm_values[j]
                cuts.append({'field': name, 'index': [int(start+fi), int(mu), int(depth)],
                             'row': (values[[0, 2, 3]]-values[1]).tolist(),
                             'lower': -float(values@anchor), 'normalized_violation': float(score[j])})
    return cuts, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required before Python starts')
    out = pipeline.safe_path(ROOT, args.run)
    out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out)
    pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        if snap.read(SCAN+'/status.json')['status'] != 'complete':
            raise RuntimeError('parent scan incomplete')
        plan = snap.read(SCAN+'/declaration.json'); old = snap.read(SCAN+'/prediction.json')
        basis = plan['basis']; anchor = np.asarray(old['anchor_weights'])
        target = np.asarray(old['raw_weights']); system = old['system']
        latest = snap.read(LATEST+'/state.json'); latest_seed(latest)
        best = float(latest['history'][-1]['residual'])
        trials = []
        for source in (BASE, OLD, LATEST):
            state = snap.read(source+'/state.json'); latest_seed(state)
            cfg = snap.read(source+'/config.json', state['config_sha256'])
            trial = load_arrays(snap.save(source+'/trial_material.npz', state['trial_sha256']))
            audit_native_trial(cfg, trial); trials.append(trial)
        same_material(trials[0], trials[1]); same_material(trials[0], trials[2])
        for record in snap.read(SCAN+'/snapshot-manifest.json'):
            snap.save(record['path'], record['sha256'])
        for c in basis:
            if (ROOT/c['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT/c['path']) != c['sha256']:
                raise RuntimeError('basis SHA or size mismatch')
        for name in ('operations/scan_positive_subspace.py', 'operations/scan_positive_subspace.sbatch'):
            snap.save(name)
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z:
            edges = z['active_edge_hz'].copy()
        pipeline.write_json(out/'declaration.json', {'environment': pipeline.environment(), 'basis': basis,
            'anchor_weights': anchor.tolist(), 'maximum_cut_passes': MAX_PASSES, 'maximum_cuts': MAX_CUTS,
            'coefficient_l1_cap': L1_CAP, 'best_measured_residual': best, 'baseline_run': LATEST,
            'new_maps': 0, 'candidate_write_budget': 0, 'science_gates_relaxed': False,
            'objective': 'same full-field unweighted residual L2, subject to streamed linear positivity cuts',
            'final_formula': 'anchor_field+t*(raw_four_map_combination-anchor_field)'})
        paths = [ROOT/c['path'] for c in basis]
        cuts = {}; rounds = []
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            for iteration in range(MAX_PASSES):
                additions, stats = collect_cuts(paths, pipeline.SHAPE, anchor, target)
                row = {'iteration': iteration, 'weights': target.tolist(), 'statistics': stats}
                rounds.append(row)
                for c in additions:
                    cuts.setdefault((c['field'], *c['index']), c)
                if len(cuts) > MAX_CUTS:
                    raise RuntimeError('declared cut budget exceeded')
                pipeline.write_json(out/'cut_progress.json', {'rounds': rounds, 'cuts': list(cuts.values())})
                if not additions:
                    break
                if iteration == MAX_PASSES-1:
                    break
                target, row['next_solve'] = solve_constrained(system['gram'], system['rhs'], anchor,
                    [c['row'] for c in cuts.values()], [c['lower'] for c in cuts.values()])
            step, bounds = bounded_step(paths, pipeline.SHAPE, anchor, target)
            metrics = prediction_metrics(paths, pipeline.SHAPE, anchor, target, step, edges)
        checks = {'positive_step': step > 0, 'coefficient_cap': bounds['effective_coefficient_l1'] <= L1_CAP,
                  'full_field_nonnegative': metrics['candidate_negative_count'] == metrics['map_negative_count'] == 0,
                  'improves_latest_measured_maximum_norm': metrics['predicted_residual'] is not None and metrics['predicted_residual'] < .99*best,
                  'boundary_l1': metrics['predicted_boundary_l1'] is not None and metrics['predicted_boundary_l1'] < 1e-3,
                  'boundary_bolometric': metrics['predicted_boundary_bolometric'] is not None and metrics['predicted_boundary_bolometric'] < 1e-3}
        for c in basis:
            if pipeline.sha256(ROOT/c['path']) != c['sha256']:
                raise RuntimeError('source bytes changed during read-only scan')
        pipeline.write_json(out/'prediction.json', {'raw_weights': target.tolist(), 'anchor_weights': anchor.tolist(),
            'step': step, 'bounds': bounds, 'prediction': metrics, 'checks': checks, 'rounds': rounds,
            'algebraic_feasibility': all(checks.values()), 'best_measured_residual': best,
            'candidate_written': False, 'actual_map_performed': False, 'accepted_material_step': False,
            'full_constrained_optimum_proven': False})
        with (out/'constraint_rounds.csv').open('x', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['iteration', 'negative_candidate', 'negative_map', 'positivity_upper', 'coefficient_l1'])
            for r in rounds:
                s = r['statistics']
                writer.writerow([r['iteration'], s['candidate']['negative_count'], s['predicted_map']['negative_count'],
                                 min(q['positivity_step_upper'] for q in s.values()), sum(abs(x) for x in r['weights'])])
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(9, 3.8), layout='constrained')
        for name in ('candidate', 'predicted_map'):
            ax[0].plot([r['iteration'] for r in rounds], [r['statistics'][name]['negative_count'] for r in rounds], 'o-', label=name)
        ax[0].set(xlabel='Constraint scan index (zero based)', ylabel='Negative radiation grid elements', yscale='symlog')
        ax[0].legend()
        ax[1].plot([r['iteration'] for r in rounds], [min(q['positivity_step_upper'] for q in r['statistics'].values()) for r in rounds], 'o-')
        ax[1].set(xlabel='Constraint scan index (zero based)', ylabel='Global positivity step upper bound', ylim=(-.02, 1.02))
        fig.suptitle('Algebraic constraint diagnostic; no actual transfer map or material acceptance')
        fig.savefig(out/'constraint_rounds.png', dpi=160); plt.close(fig)
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__':
    main()
