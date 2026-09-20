"""Exact-order field construction and verification for the four-pair scan."""
from pathlib import Path
import os
import numpy as np
from operations.scan_half_four_map_subspace import fields, checks, ANCHOR
from operations.scan_cross_history_direction import chunks, algebra

EXPECTED_CHECKS = {'resolved_rank', 'constraint_budget_resolved', 'finite_coefficients',
    'coefficient_sum', 'coefficient_cap', 'full_field_nonnegative', 'maximum_norm_improves_best',
    'boundary_l1', 'boundary_bolometric'}


def weights_checked(weights):
    w = np.asarray(weights, dtype=float)
    if (w.shape != (4,) or not np.isfinite(w).all() or abs(float(w.sum())-1) >= 1e-12
            or float(np.sum(abs(w))) > 32.):
        raise ValueError('invalid four-pair coefficients')
    return w


def verify_scan(prediction, declaration, pairs, best):
    gate = prediction['checks']
    if (prediction['algebraic_feasibility'] is not True or set(gate) != EXPECTED_CHECKS
            or any(v is not True for v in gate.values())):
        raise ValueError('scan checks incomplete or failed')
    if (declaration['pairs'] != pairs or declaration['pair_order'] !=
            ['73929_last','73888_last','74057_previous','74057_last']
            or declaration['new_maps'] != 0 or declaration['candidate_write_budget'] != 0
            or declaration['coefficient_l1_cap'] != 32. or declaration['rank_requirement'] != 3
            or declaration['relative_rank_cutoff'] != 1e-12
            or declaration['maximum_cut_passes'] != 6 or declaration['maximum_cuts'] != 4096
            or declaration['same_material_all_fields'] is not True
            or declaration['same_operator_and_old_time_level'] is not True
            or prediction['actual_map_performed'] is not False or prediction['candidate_written'] is not False
            or prediction['accepted_material_step'] is not False
            or prediction['best_measured_residual'] != best or declaration['best_measured_residual'] != best):
        raise ValueError('scan scope, source pairs or baseline differ')
    w = weights_checked(prediction['effective_weights'])
    raw = np.asarray(prediction['raw_weights']); step = prediction['coefficient_step']
    if (raw.shape != (4,) or not np.isfinite(raw).all() or not np.isfinite(step) or not 0 < step <= 1
            or not np.array_equal(declaration['anchor_weights'], ANCHOR)
            or not np.array_equal(prediction['anchor_weights'], ANCHOR)
            or not np.array_equal(w, ANCHOR+step*(raw-ANCHOR))):
        raise ValueError('effective weights differ from the declared expression')
    p = prediction['prediction']; system = prediction['system']
    values = [p['predicted_residual'], p['predicted_residual_squared_l2'],
              p['predicted_boundary_l1'], p['predicted_boundary_bolometric'], *p['minimum_fields'], best]
    eig = np.asarray(system['eigenvalues'], dtype=float)
    if (not np.isfinite(values).all() or min(values) < 0 or best <= 0
            or eig.shape != (3,) or not np.isfinite(eig).all() or eig[0] <= 1e-12*max(abs(eig))
            or system['relative_cutoff'] != 1e-12 or system['retained_rank'] != 3):
        raise ValueError('nonfinite, negative or unresolved scan numbers')
    rounds = prediction['rounds']
    if not 1 <= len(rounds) <= 6 or rounds[-1]['statistics']['negative_counts'] != [0,0]:
        raise ValueError('constraint scan did not resolve within its budget')
    if not all(checks(w, p, best, system['retained_rank'], True).values()):
        raise ValueError('scan numbers disagree with pass flags')
    return w


def candidate_chunk(arrays, weights):
    w = weights_checked(weights)
    if len(arrays) != 8 or any(a.shape != arrays[0].shape for a in arrays):
        raise ValueError('eight equally shaped explicit-pair arrays required')
    if any(not np.isfinite(a).all() or np.any(a < 0) for a in arrays):
        raise ValueError('invalid source radiation')
    with np.errstate(over='raise', invalid='raise'):
        x, y = fields(arrays, w)
    if any(not np.isfinite(a).all() or np.any(a < 0) for a in (x,y)):
        raise ArithmeticError('candidate or prediction is outside the nonnegative finite domain')
    return x, y


def write_candidate(paths, destination, shape, weights):
    weights_checked(weights)
    if destination.exists(): raise FileExistsError(destination)
    tmp = destination.with_suffix('.partial'); minimum = np.inf
    with tmp.open('xb') as output:
        for _, arrays in chunks(paths, shape):
            x, _ = candidate_chunk(arrays, weights)
            minimum = min(minimum, float(x.min())); x.tofile(output)
    if tmp.stat().st_size != int(np.prod(shape))*8: raise RuntimeError('candidate byte count differs')
    os.replace(tmp, destination)
    return minimum


def full_field_error(paths, shape, weights, edges):
    """Compare full actual output and reconstruct the exact candidate bytes."""
    err2 = pred2 = defect2 = maximum = scale = num = fa_scale = fp_scale = ba = bp = 0.
    mu, mw = algebra.gauss_legendre_split_mu_weights(shape[1], 0.); widths = np.diff(edges)
    if widths.shape != (shape[0],) or not np.isfinite(widths).all() or np.any(widths <= 0):
        raise ValueError('invalid frequency measure')
    for start, arrays in chunks(paths, shape):
        candidate, actual = arrays[:2]
        expected, predicted = candidate_chunk(arrays[2:], weights)
        if not np.array_equal(candidate, expected):
            raise RuntimeError('candidate bytes differ from the declared operation order')
        error = actual-predicted; defect = actual-candidate
        err2 += float(np.sum(error*error)); pred2 += float(np.sum(predicted*predicted)); defect2 += float(np.sum(defect*defect))
        maximum = max(maximum, float(np.max(abs(error))))
        scale = max(scale, float(np.max(abs(actual))), float(np.max(abs(predicted))))
        fa = algebra._block_flux(actual, mu, mw, widths[start:start+len(actual)])
        fp = algebra._block_flux(predicted, mu, mw, widths[start:start+len(predicted)])
        num += float(np.sum(abs(fa-fp))); fa_scale += float(np.sum(abs(fa))); fp_scale += float(np.sum(abs(fp)))
        ba += float(np.sum(fa)); bp += float(np.sum(fp))
    if not np.isfinite([err2,pred2,defect2,maximum,scale,num,fa_scale,fp_scale,ba,bp]).all():
        raise ArithmeticError('nonfinite full-field comparison')
    return {'error_l2': float(np.sqrt(err2)), 'relative_field_l2': float(np.sqrt(err2/pred2)) if pred2 > 0 else None,
            'maximum_error_over_field_scale': maximum/scale if scale > 0 else None,
            'error_over_actual_defect_l2': float(np.sqrt(err2/defect2)) if defect2 > 0 else None,
            'boundary_prediction_l1_error': num/max(fa_scale,fp_scale) if max(fa_scale,fp_scale) > 0 else None,
            'boundary_prediction_bolometric_error': abs(ba-bp)/max(abs(ba),abs(bp)) if max(abs(ba),abs(bp)) > 0 else None,
            'candidate_reconstruction_exact': True,
            'prediction_error_resolved': bool(err2 < 1e-4*defect2 or err2 == defect2 == 0.)}
