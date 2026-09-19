"""Validate a cross-history radiation candidate and its full-field map prediction."""
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
from operations.scan_cross_history_direction import latest_pair, chunks, COEFFICIENT_L1_CAP, BASE, OLD, algebra

SCAN = 'outputs/hpc/cross-history-direction-scan-20260919'


def affine_chunk(a, b, fraction):
    """Match the preregistered arithmetic order; reject invalid cells, never clip."""
    if a.shape != b.shape or not np.isfinite(fraction) or abs(1+fraction)+abs(fraction) > COEFFICIENT_L1_CAP:
        raise ValueError('invalid affine basis or coefficient')
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)) or np.any(a < 0) or np.any(b < 0):
        raise ValueError('invalid radiation basis')
    with np.errstate(over='raise', invalid='raise'):
        candidate = a + fraction * (a - b)
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


def full_field_error(paths, shape, gamma, edges):
    """Compare actual output to the declared affine prediction without writing it."""
    err2 = pred2 = defect2 = maximum_error = scale = 0.
    mu, weight = algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    widths = np.diff(edges)
    if widths.shape != (shape[0],) or not np.all(np.isfinite(widths)) or np.any(widths <= 0):
        raise ValueError('invalid frequency measure')
    flux_error = actual_flux = predicted_flux = actual_bol = predicted_bol = 0.
    for start, (candidate, actual, yb, yo) in chunks(paths, shape):
        predicted = affine_chunk(yb, yo, gamma)
        error = actual-predicted
        err2 += float(np.sum(error*error)); pred2 += float(np.sum(predicted*predicted))
        defect = actual-candidate; defect2 += float(np.sum(defect*defect))
        maximum_error = max(maximum_error, float(np.max(abs(error))))
        scale = max(scale, float(np.max(abs(actual))), float(np.max(abs(predicted))))
        fa = algebra._block_flux(actual, mu, weight, widths[start:start+len(actual)])
        fp = algebra._block_flux(predicted, mu, weight, widths[start:start+len(predicted)])
        flux_error += float(np.sum(abs(fa-fp)))
        actual_flux += float(np.sum(abs(fa))); predicted_flux += float(np.sum(abs(fp)))
        actual_bol += float(np.sum(fa)); predicted_bol += float(np.sum(fp))
    if not np.all(np.isfinite([err2, pred2, defect2, maximum_error, scale, flux_error, actual_flux, predicted_flux])):
        raise ArithmeticError('nonfinite accumulated full-field comparison')
    return {'error_l2': float(np.sqrt(err2)),
            'relative_field_l2': float(np.sqrt(err2/pred2)) if pred2 > 0 else None,
            'maximum_error_over_field_scale': maximum_error/scale if scale > 0 else None,
            'error_over_actual_defect_l2': float(np.sqrt(err2/defect2)) if defect2 > 0 else None,
            'boundary_prediction_l1_error': flux_error/max(actual_flux, predicted_flux) if max(actual_flux, predicted_flux) > 0 else None,
            'boundary_prediction_bolometric_error': abs(actual_bol-predicted_bol)/max(abs(actual_bol), abs(predicted_bol)) if max(abs(actual_bol), abs(predicted_bol)) > 0 else None,
            'prediction_error_resolved': bool(err2 < .0001*defect2 or err2 == defect2 == 0.)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--workers', type=int, choices=(2, 16), required=True); p.add_argument('--run', required=True)
    args = p.parse_args(); pipeline.require_allocation(args.workers)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT / 'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out / 'validation_status.json', {'status': 'preparing', 'new_maps': 0})
    try:
        if snap.read(SCAN + '/status.json')['status'] != 'complete': raise RuntimeError('scan incomplete')
        prediction = snap.read(SCAN + '/prediction.json')
        declaration = snap.read(SCAN + '/declaration.json')
        if not prediction['algebraic_feasibility'] or not all(prediction['checks'].values()):
            raise RuntimeError('algebraic guards failed')
        source = BASE
        state = snap.read(BASE + '/state.json'); other_state = snap.read(OLD + '/state.json')
        basis = latest_pair(state) + latest_pair(other_state)
        if basis != declaration['basis']: raise RuntimeError('scan basis differs from current source history')
        cfg = deepcopy(snap.read(source + '/config.json', state['config_sha256']))
        trial = load_arrays(snap.save(source + '/trial_material.npz', state['trial_sha256']))
        other = load_arrays(snap.save(OLD + '/trial_material.npz', other_state['trial_sha256']))
        same_material(trial, other)
        if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True): raise RuntimeError('source dependency changed')
        for claim in basis:
            if (ROOT / claim['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT / claim['path']) != claim['sha256']:
                raise RuntimeError('large basis changed')
        if shutil.disk_usage(out).free < 4 * pipeline.STATE_BYTES + 8 * 1024**3:
            raise RuntimeError('insufficient space for candidate, pipeline slots and margin')
        fraction = float(prediction['direction']['gamma'])
        plan = {'environment': pipeline.environment(), 'history': 'cross-history', 'basis': basis,
                'fraction': fraction, 'prediction': prediction, 'maximum_new_maps': 1,
                'formula': 'candidate=XB+gamma*(XB-XO); predicted=YB+gamma*(YB-YO)',
                'full_field_prediction_error_fraction_of_actual_defect_limit': .01, 'candidate_clipping': False,
                'material_changed': False, 'NUMPY_MADVISE_HUGEPAGE': os.environ.get('NUMPY_MADVISE_HUGEPAGE'),
                'code': [pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix('.sbatch'))]}
        pipeline.write_json(out / 'validation_declaration.json', plan)
        candidate = out / 'cross_candidate.dat'
        minimum = write_candidate([ROOT / basis[i]['path'] for i in (0, 2)], candidate, fraction,
                                  int(np.prod(pipeline.SHAPE)), 16 * pipeline.SHAPE[1] * pipeline.SHAPE[2])
        for claim in basis:
            if pipeline.sha256(ROOT / claim['path']) != claim['sha256']: raise RuntimeError('basis changed during candidate write')
        copied = carry_trial(ROOT / source, out)
        same_material(load_arrays(out / 'trial_material.npz'), trial)
        seed = pipeline.claim(candidate)
        cfg.update(run=args.run, workers=args.workers, maximum_maps=1, radiation_threshold=1e-4,
                   seed='warm', warm_seed=seed, extension_of=source,
                   extension_purpose='one fresh original map of the declared cross-history candidate with full-field prediction check')
        cfg['sources'] = list(cfg['sources']) + [copied['source'], copied['destination'], seed,
            pipeline.claim(out / 'validation_declaration.json'), pipeline.claim(Path(__file__)),
            pipeline.claim(Path(__file__).with_suffix('.sbatch')),
            pipeline.claim(ROOT/'operations/scan_cross_history_direction.py'),
            pipeline.claim(ROOT/'operations/audit_affine_feedback_histories.py'),
            pipeline.claim(ROOT/OLD/'trial_material.npz')]
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
        checks = validation_checks(row, prediction['best_measured_residual'])
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        field_error = full_field_error([candidate, ROOT/row['output_path'], ROOT/basis[1]['path'], ROOT/basis[3]['path']],
                                       pipeline.SHAPE, fraction, edges)
        checks['full_field_prediction_error_resolved'] = field_error['prediction_error_resolved']
        for claim in basis:
            if pipeline.sha256(ROOT/claim['path']) != claim['sha256']: raise RuntimeError('basis changed during full validation')
        result = {'history': 'cross-history', 'candidate': seed, 'candidate_minimum_intensity': minimum,
                  'actual_map': row, 'predicted_residual': prediction['prediction']['predicted_residual'],
                  'actual_minus_predicted_residual': row['residual'] - prediction['prediction']['predicted_residual'],
                  'validation_checks': checks, 'extrapolation_validated': all(checks.values()),
                  'accepted_material_step': False, 'feedback_evaluated': False,
                  'full_intensity_prediction_error_evaluated': True, 'full_field_error': field_error,
                  'note': 'Map aggregate enforces complete ownership, finite metrics and nonnegative input/output; full-field agreement is tested for this mixture only; it is not a proof of global operator affinity or feedback stability.'}
        pipeline.write_json(out / 'validation_result.json', result)
        pipeline.write_json(out / 'validation_status.json', {'status': 'complete', 'new_maps': 1,
                               'extrapolation_validated': all(checks.values()), 'accepted_material_step': False})
    except BaseException as exc:
        pipeline.write_json(out / 'validation_status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__': main()
