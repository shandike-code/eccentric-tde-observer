"""Write one guarded global affine candidate, then measure one fresh full map."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import shutil
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'src'), str(ROOT / 'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_extension_run import carry_trial
from operations.prepare_common_seed_precision import same_material
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.diagnose_history_slow_modes import basis_claims, BASE, OLD

SCAN = 'outputs/hpc/paired-history-slow-mode-scan-20260919'


def affine_chunk(a, b, fraction):
    """Match the preregistered arithmetic order; reject invalid cells, never clip."""
    if a.shape != b.shape or not np.isfinite(fraction) or not 1 < fraction <= 96:
        raise ValueError('invalid affine basis or coefficient')
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)) or np.any(a < 0) or np.any(b < 0):
        raise ValueError('invalid radiation basis')
    with np.errstate(over='raise', invalid='raise'):
        candidate = b + (fraction - 1.) * (b - a)
    if not np.all(np.isfinite(candidate)) or np.any(candidate < 0):
        raise ArithmeticError('affine candidate left nonnegative finite domain')
    return candidate


def write_candidate(paths, destination, fraction, count, chunk):
    """Stream through ordinary files to bound resident memory in the 4-CPU run."""
    temporary = destination.with_suffix('.partial')
    minimum = float('inf')
    if destination.exists(): raise FileExistsError(destination)
    with open(paths[0], 'rb') as fa, open(paths[1], 'rb') as fb, temporary.open('xb') as output:
        for offset in range(0, count, chunk):
            n = min(chunk, count - offset)
            a, b = np.fromfile(fa, dtype=np.float64, count=n), np.fromfile(fb, dtype=np.float64, count=n)
            if a.size != n or b.size != n: raise RuntimeError('short radiation basis read')
            candidate = affine_chunk(a, b, fraction)
            minimum = min(minimum, float(np.min(candidate)))
            candidate.tofile(output)
        if fa.read(1) or fb.read(1): raise RuntimeError('unexpected radiation basis tail')
    if temporary.stat().st_size != count * 8: raise RuntimeError('candidate size mismatch')
    os.replace(temporary, destination)
    return minimum


def validation_checks(row, latest):
    return {'actual_maximum_norm_improves': row['residual'] / latest < .99,
            'actual_boundary_spectrum_pass': row['boundary_l1'] < 1e-3,
            'actual_boundary_bolometric_pass': row['boundary_bolometric'] < 1e-3,
            'worker_memory_pass': row['maximum_worker_rss_mib'] < 6144}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--history', choices=('base', 'old'), required=True)
    p.add_argument('--workers', type=int, choices=(2, 16), required=True); p.add_argument('--run', required=True)
    args = p.parse_args(); pipeline.require_allocation(args.workers)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT / 'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out / 'validation_status.json', {'status': 'preparing', 'new_maps': 0})
    try:
        if snap.read(SCAN + '/status.json')['status'] != 'complete': raise RuntimeError('scan incomplete')
        prediction = snap.read(SCAN + '/prediction.json')['histories'][args.history]
        declaration = snap.read(SCAN + f'/{args.history}-declaration.json')
        if not prediction['algebraic_feasibility'] or not all(prediction['algebraic_gates'].values()):
            raise RuntimeError('algebraic guards failed')
        source = BASE if args.history == 'base' else OLD
        state = snap.read(source + '/state.json', declaration['source_state']['sha256'])
        basis = basis_claims(state)
        if basis != declaration['basis']: raise RuntimeError('scan basis differs from current source history')
        cfg = deepcopy(snap.read(source + '/config.json', state['config_sha256']))
        trial = load_arrays(snap.save(source + '/trial_material.npz', state['trial_sha256']))
        if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True): raise RuntimeError('source dependency changed')
        for claim in basis:
            if (ROOT / claim['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT / claim['path']) != claim['sha256']:
                raise RuntimeError('large basis changed')
        if shutil.disk_usage(out).free < 4 * pipeline.STATE_BYTES + 8 * 1024**3:
            raise RuntimeError('insufficient space for candidate, pipeline slots and margin')
        fraction = float(prediction['direction']['selected_forward_fraction'])
        plan = {'environment': pipeline.environment(), 'history': args.history, 'basis': basis,
                'fraction': fraction, 'prediction': prediction, 'maximum_new_maps': 1,
                'formula': 'candidate=b+(fraction-1)*(b-a)', 'candidate_clipping': False,
                'material_changed': False, 'NUMPY_MADVISE_HUGEPAGE': os.environ.get('NUMPY_MADVISE_HUGEPAGE'),
                'code': [pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix('.sbatch'))]}
        pipeline.write_json(out / 'validation_declaration.json', plan)
        candidate = out / 'anderson_candidate.dat'
        minimum = write_candidate([ROOT / r['path'] for r in basis[:2]], candidate, fraction,
                                  int(np.prod(pipeline.SHAPE)), 16 * pipeline.SHAPE[1] * pipeline.SHAPE[2])
        for claim in basis:
            if pipeline.sha256(ROOT / claim['path']) != claim['sha256']: raise RuntimeError('basis changed during candidate write')
        copied = carry_trial(ROOT / source, out)
        same_material(load_arrays(out / 'trial_material.npz'), trial)
        seed = pipeline.claim(candidate)
        cfg.update(run=args.run, workers=args.workers, maximum_maps=1, radiation_threshold=1e-4,
                   seed='warm', warm_seed=seed, extension_of=source,
                   extension_purpose='one fresh original map of a guarded affine radiation candidate')
        cfg['sources'] = list(cfg['sources']) + [copied['source'], copied['destination'], seed,
            pipeline.claim(out / 'validation_declaration.json'), pipeline.claim(Path(__file__)),
            pipeline.claim(Path(__file__).with_suffix('.sbatch'))]
        pipeline.write_json(out / 'config.json', cfg)
        pipeline.write_json(out / 'native_trial_audit.json', audit_native_trial(cfg, trial))
        pipeline.write_json(out / 'state.json', {'config_sha256': pipeline.sha256(out / 'config.json'),
             'status': 'initializing', 'initialization_blocks': [], 'history': [],
             'slots': [args.run + f'/state_{i}.dat' for i in range(3)], 'current_slot': 0, 'active_map': None})
        pipeline.run_pipeline(out, 1, False)
        mapped = pipeline.read(out / 'state.json')
        if mapped.get('active_map') or len(mapped['history']) != 1:
            pipeline.write_json(out / 'validation_status.json', {'status': 'incomplete', 'new_maps': len(mapped['history'])})
            return
        row = mapped['history'][0]
        if row['input_sha256'] != seed['sha256']: raise RuntimeError('fresh map used a different candidate')
        checks = validation_checks(row, prediction['latest_actual_residual'])
        result = {'history': args.history, 'candidate': seed, 'candidate_minimum_intensity': minimum,
                  'actual_map': row, 'predicted_residual': prediction['metrics']['predicted_global_original_operator_residual'],
                  'actual_minus_predicted_residual': row['residual'] - prediction['metrics']['predicted_global_original_operator_residual'],
                  'validation_checks': checks, 'extrapolation_validated': all(checks.values()),
                  'accepted_material_step': False, 'feedback_evaluated': False,
                  'full_intensity_prediction_error_evaluated': False,
                  'note': 'Map aggregate enforces complete ownership, finite metrics and nonnegative input/output; agreement of scalar residual alone does not prove operator affinity.'}
        pipeline.write_json(out / 'validation_result.json', result)
        pipeline.write_json(out / 'validation_status.json', {'status': 'complete', 'new_maps': 1,
                               'extrapolation_validated': all(checks.values()), 'accepted_material_step': False})
    except BaseException as exc:
        pipeline.write_json(out / 'validation_status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__': main()
