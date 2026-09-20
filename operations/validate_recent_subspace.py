"""Validate the declared four-map subspace candidate against the original operator."""
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
from operations.scan_cross_history_direction import chunks, algebra
from operations.scan_recent_positive_subspace import recent_basis, BASE, OLD
from operations.scan_multihistory_subspace import fields
from operations.validate_cross_history_candidate import validation_checks

SCAN = 'outputs/hpc/recent-positive-subspace-20260920'



def mix_parameters(anchor, target, step):
    anchor, target = np.asarray(anchor, dtype=float), np.asarray(target, dtype=float)
    if (anchor.shape != (4,) or target.shape != (4,) or not np.all(np.isfinite(anchor))
        or not np.all(np.isfinite(target)) or not np.isfinite(step) or not 0 <= step <= 1
        or np.any(anchor < 0) or abs(anchor.sum()-1) > 1e-12 or abs(target.sum()-1) > 1e-12):
        raise ValueError('invalid subspace coefficients')
    if np.sum(abs(anchor+step*(target-anchor))) > 32.:
        raise ValueError('effective coefficient L1 exceeds the declared cap')
    return anchor, target, float(step)


def validated_plan(prediction, declaration, best):
    required = ('positive_step', 'coefficient_cap', 'full_field_nonnegative',
                'improves_latest_measured_maximum_norm', 'boundary_l1', 'boundary_bolometric')
    if (prediction.get('algebraic_feasibility') is not True
        or any(prediction.get('checks', {}).get(k) is not True for k in required)):
        raise RuntimeError('algebraic guards failed or missing')
    residual = prediction['prediction']['predicted_residual']
    if not np.isfinite(best) or best <= 0 or not np.isfinite(residual) or residual < 0 or residual >= .99*best:
        raise RuntimeError('prediction no longer improves the current measured baseline')
    if not np.array_equal(declaration['anchor_weights'], prediction['anchor_weights']):
        raise RuntimeError('declared and reported anchors differ')
    return mix_parameters(declaration['anchor_weights'], prediction['raw_weights'], prediction['step'])


def subspace_chunk(arrays, anchor, target, step):
    """Preserve the exact expression and operation order from the declared scan."""
    anchor, target, step = mix_parameters(anchor, target, step)
    if len(arrays) != 6 or any(a.shape != arrays[0].shape for a in arrays):
        raise ValueError('six equally shaped basis arrays required')
    if any(not np.all(np.isfinite(a)) or np.any(a < 0) for a in arrays):
        raise ValueError('invalid radiation basis')
    with np.errstate(over='raise', invalid='raise'):
        ax, ay = fields(arrays, anchor); tx, ty = fields(arrays, target)
        # 中文：与扫描逐运算一致，不能代换为重排后的有效权重和；后者舍入不同。
        x, y = ax+step*(tx-ax), ay+step*(ty-ay)
    if any(not np.all(np.isfinite(a)) or np.any(a < 0) for a in (x, y)):
        raise ArithmeticError('subspace candidate or predicted map is not finite nonnegative')
    return x, y


def write_candidate(paths, destination, shape, anchor, target, step):
    mix_parameters(anchor, target, step)
    if destination.exists(): raise FileExistsError(destination)
    temporary = destination.with_suffix('.partial'); minimum = np.inf
    with temporary.open('xb') as output:
        for _, arrays in chunks(paths, shape):
            x, _ = subspace_chunk(arrays, anchor, target, step)
            minimum = min(minimum, float(x.min())); x.tofile(output)
    if temporary.stat().st_size != int(np.prod(shape))*8:
        raise RuntimeError('candidate size mismatch')
    os.replace(temporary, destination)
    return minimum

def full_field_error(paths, shape, anchor, target, step, edges):
    """Compare actual output to the declared affine prediction without writing it."""
    err2 = pred2 = defect2 = maximum_error = scale = 0.
    mu, weight = algebra.gauss_legendre_split_mu_weights(shape[1], 0.)
    widths = np.diff(edges)
    if widths.shape != (shape[0],) or not np.all(np.isfinite(widths)) or np.any(widths <= 0):
        raise ValueError('invalid frequency measure')
    flux_error = actual_flux = predicted_flux = actual_bol = predicted_bol = 0.
    for start, arrays in chunks(paths, shape):
        candidate, actual = arrays[:2]
        expected_candidate, predicted = subspace_chunk(arrays[2:], anchor, target, step)
        if not np.array_equal(candidate, expected_candidate):
            raise RuntimeError("candidate bytes do not match the declared expression")
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
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required before Python starts')
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT / 'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out / 'validation_status.json', {'status': 'preparing', 'new_maps': 0})
    try:
        if snap.read(SCAN + '/status.json')['status'] != 'complete': raise RuntimeError('scan incomplete')
        prediction = snap.read(SCAN + '/prediction.json')
        declaration = snap.read(SCAN + '/declaration.json')
        source = OLD
        other_state = snap.read(BASE + '/state.json'); state = snap.read(OLD + '/state.json')
        basis = recent_basis(other_state, state)
        best = float(state['history'][-1]['residual'])
        anchor, target, step = validated_plan(prediction, declaration, best)
        if basis != declaration['basis']: raise RuntimeError('scan basis differs from current source history')
        cfg = deepcopy(snap.read(source + '/config.json', state['config_sha256']))
        trial = load_arrays(snap.save(source + '/trial_material.npz', state['trial_sha256']))
        other = load_arrays(snap.save(BASE + '/trial_material.npz', other_state['trial_sha256']))
        same_material(trial, other)
        if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True): raise RuntimeError('source dependency changed')
        for claim in basis:
            if (ROOT / claim['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT / claim['path']) != claim['sha256']:
                raise RuntimeError('large basis changed')
        if shutil.disk_usage(out).free < 4 * pipeline.STATE_BYTES + 8 * 1024**3:
            raise RuntimeError('insufficient space for candidate, pipeline slots and margin')
        plan = {'environment': pipeline.environment(), 'history': 'recent four-map constrained subspace', 'basis': basis,
                'anchor_weights': anchor.tolist(), 'raw_weights': target.tolist(), 'step': step, 'prediction': prediction, 'best_measured_residual': best, 'maximum_new_maps': 1,
                'formula': 'anchor_field+step*(raw_four_map_combination-anchor_field), same operation order for candidate and predicted map',
                'full_field_prediction_error_fraction_of_actual_defect_limit': .01, 'candidate_clipping': False,
                'material_changed': False, 'NUMPY_MADVISE_HUGEPAGE': os.environ.get('NUMPY_MADVISE_HUGEPAGE'),
                'code': [pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix('.sbatch'))]}
        pipeline.write_json(out / 'validation_declaration.json', plan)
        candidate = out / 'subspace_candidate.dat'
        minimum = write_candidate([ROOT/c['path'] for c in basis], candidate, pipeline.SHAPE, anchor, target, step)
        for claim in basis:
            if pipeline.sha256(ROOT / claim['path']) != claim['sha256']: raise RuntimeError('basis changed during candidate write')
        copied = carry_trial(ROOT / source, out)
        same_material(load_arrays(out / 'trial_material.npz'), trial)
        seed = pipeline.claim(candidate)
        cfg.update(run=args.run, workers=args.workers, maximum_maps=1, radiation_threshold=1e-4,
                   seed='warm', warm_seed=seed, extension_of=source,
                   extension_purpose='one original map of the declared four-map subspace combination with full-field prediction check')
        cfg['sources'] = list(cfg['sources']) + [copied['source'], copied['destination'], seed,
            pipeline.claim(out / 'validation_declaration.json'), pipeline.claim(Path(__file__)),
            pipeline.claim(Path(__file__).with_suffix('.sbatch')),
            pipeline.claim(ROOT/'operations/scan_cross_history_direction.py'),
            pipeline.claim(ROOT/'operations/audit_affine_feedback_histories.py'),
            pipeline.claim(ROOT/BASE/'trial_material.npz'),
            pipeline.claim(ROOT/'operations/scan_recent_positive_subspace.py'),
            pipeline.claim(ROOT/'operations/scan_positive_subspace.py'),
            pipeline.claim(ROOT/'operations/scan_multihistory_subspace.py'),
            pipeline.claim(ROOT/'operations/validate_cross_history_candidate.py'),
            pipeline.claim(ROOT/SCAN/'prediction.json'), pipeline.claim(ROOT/SCAN/'declaration.json')]
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
        checks = validation_checks(row, best)
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        field_error = full_field_error([candidate, ROOT/row['output_path'], *[ROOT/c['path'] for c in basis]],
                                       pipeline.SHAPE, anchor, target, step, edges)
        checks['full_field_prediction_error_resolved'] = field_error['prediction_error_resolved']
        for claim in basis:
            if pipeline.sha256(ROOT/claim['path']) != claim['sha256']: raise RuntimeError('basis changed during full validation')
        result = {'history': 'recent four-map constrained subspace', 'candidate': seed, 'candidate_minimum_intensity': minimum,
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
