"""Bounded positivity-constrained scan using the latest four consecutive maps.

This writes no intensity candidate and runs no transfer map. Every proposed
combination is scanned over the complete field; sampled cuts never certify it.
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_common_seed_precision import same_material, latest_seed
from operations.scan_multihistory_subspace import (
    bounded_step, prediction_metrics,
)

LATEST = 'outputs/hpc/mixed-followup-20260920'
BASE = 'outputs/hpc/cross-mixture-feedback-20260919'
OLD = LATEST
MAX_PASSES = 6
MAX_CUTS = 4096
L1_CAP = 32.


from operations.scan_positive_subspace import solve_constrained, collect_cuts
from operations.scan_multihistory_subspace import residual_system
from operations.scan_cross_history_direction import latest_pair


def recent_basis(first, second):
    """Require four consecutive measured maps, never graft histories into a run."""
    a, b = latest_pair(first), latest_pair(second)
    first_input = {'path': first['history'][0]['input_path'], 'sha256': first['history'][0]['input_sha256']}
    second_input = {'path': second['history'][0]['input_path'], 'sha256': second['history'][0]['input_sha256']}
    if a[-1]['sha256'] != second_input['sha256']:
        raise RuntimeError('the recent source runs do not form one consecutive chain')
    return [first_input, *a, second_input, *b]

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
        first = snap.read(BASE+'/state.json')
        latest = snap.read(LATEST+'/state.json')
        basis = recent_basis(first, latest)
        anchor = np.array([0., 0., 0., 1.])
        best = float(latest['history'][-1]['residual'])
        trials = []
        for source in (BASE, OLD):
            state = snap.read(source+'/state.json'); latest_seed(state)
            cfg = snap.read(source+'/config.json', state['config_sha256'])
            trial = load_arrays(snap.save(source+'/trial_material.npz', state['trial_sha256']))
            audit_native_trial(cfg, trial); trials.append(trial)
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
        same_material(trials[0], trials[1])
        for c in basis:
            if (ROOT/c['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT/c['path']) != c['sha256']:
                raise RuntimeError('basis SHA or size mismatch')
        for name in ('operations/scan_recent_positive_subspace.py', 'operations/scan_recent_positive_subspace.sbatch',
                     'operations/scan_positive_subspace.py', 'operations/scan_multihistory_subspace.py', 'operations/scan_cross_history_direction.py'):
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
        target, system = residual_system(paths, pipeline.SHAPE, anchor)
        pipeline.write_json(out/'residual_system.json', system)
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
