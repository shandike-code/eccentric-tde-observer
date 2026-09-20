"""Bounded, read-only two-block source correction for base and trial matter.

No global candidate is written. Frozen frequency halos make this a block-local
diagnostic, not a solution or error certificate for the coupled global operator.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import resource
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.audit_mixture_material_residual import zero_matches_candidate
from eccentric_tde_observer.affine_krylov import (
    exact_nonnegative_affine_step, constrained_affine_residual_line_minimum,
)
from eccentric_tde_observer.mixed_frame_ali import mixed_frame_spatial_source_residual_correction
from eccentric_tde_observer.mixed_frame_frequency import (
    lorentz_ray_transform, lorentz_remap_comoving_group_extinction_to_lab,
)

SOURCES = {
    'base': ('outputs/hpc/baseline-zero-control-20260919',
             'be47ec8a7ef84277b0a7e14bdb5bd0d9b1b7e3a1c1f9e9a3339e9c034a708b9f'),
    'trial': ('outputs/hpc/half-four-map-feedback-20260920',
              'd9e92da7e394c772e1ced2874a78ce5b57609bc2a692329fae96e870c29234ad'),
}
BLOCKS = (14, 47)


def checked_field(value, shape=None):
    a = np.asarray(value, dtype=float)
    if (a.size == 0 or (shape is not None and a.shape != shape)
            or not np.isfinite(a).all() or np.any(a < 0)):
        raise ValueError('physical intensity must be finite, nonnegative and correctly shaped')
    return a


def relative_size(value, reference):
    numerator = float(np.max(abs(value)))
    denominator = float(np.max(abs(reference)))
    return numerator/denominator if denominator else (0. if numerator == 0 else None)


def verify_map_replay(initial, mapped, archived):
    x = checked_field(initial)
    y = checked_field(mapped, x.shape)
    z = checked_field(archived, x.shape)
    field = relative_size(y-z, z)
    defect = relative_size(y-z, z-x)
    checks = {'field_relative_error': field, 'defect_relative_error': defect,
              'array_equal': bool(np.array_equal(y, z))}
    if field is None or defect is None or field > 1e-12 or defect > 1e-6:
        raise ArithmeticError('local source map does not reproduce the archived native map')
    return checks


def evaluate_direction(initial, raw_mapped, direction, source_map):
    x = checked_field(initial)
    y = checked_field(raw_mapped, x.shape)
    d = np.asarray(direction, dtype=float)
    if d.shape != x.shape or not np.isfinite(d).all():
        raise ValueError('invalid correction direction')
    raw = y-x
    raw_l2 = float(np.linalg.norm(raw))
    if raw_l2 == 0:
        raise ValueError('zero raw defect cannot establish acceleration benefit')
    # 中文：只沿原方向退至逐点非负的端点；不裁剪任何强度分量。
    step = exact_nonnegative_affine_step(x, d)
    endpoint = checked_field(x+step*d, x.shape)
    mapped_endpoint = checked_field(source_map(endpoint), x.shape)
    end_defect = mapped_endpoint-endpoint
    line = constrained_affine_residual_line_minimum(raw, end_defect)
    fraction = float(line.selected_fraction)
    candidate = checked_field(x+(fraction*step)*d, x.shape)
    fresh = checked_field(source_map(candidate), x.shape)
    defect = fresh-candidate
    predicted = raw+fraction*(end_defect-raw)
    # 中文：用初始缺陷固定归一化，避免改变候选强度尺度制造虚假收益。
    prediction_error = float(np.linalg.norm(defect-predicted))/raw_l2
    l2_ratio = float(np.linalg.norm(defect))/raw_l2
    max_ratio = float(np.max(abs(defect)))/float(np.max(abs(raw)))
    return candidate, fresh, {
        'exact_nonnegative_step': float(step), 'line_fraction': fraction,
        'raw_defect_l2': raw_l2, 'fresh_defect_l2': float(np.linalg.norm(defect)),
        'raw_defect_linf': float(np.max(abs(raw))),
        'fresh_defect_linf': float(np.max(abs(defect))),
        'fixed_scale_l2_ratio': l2_ratio, 'fixed_scale_linf_ratio': max_ratio,
        'prediction_error_over_raw_l2': prediction_error,
        'minimum_candidate': float(np.min(candidate)), 'minimum_mapped': float(np.min(fresh)),
        'checks': {'l2_halved': l2_ratio <= .5, 'linf_halved': max_ratio <= .5,
                   'useful_step': step > 0 and fraction > 0,
                   'affine_prediction': prediction_error <= 1e-6},
    }


def worker(out, label, index):
    plan = pipeline.read(out/'declaration.json')
    record = plan['cases'][label]
    cfg = pipeline.read(ROOT/record['config']['path'])
    for c in [record['config'], record['trial'], record['state']]:
        if pipeline.sha256(ROOT/c['path']) != c['sha256']:
            raise RuntimeError('worker input declaration changed')
    source = ROOT/record['input']['path']
    native, fixed, template, context = pipeline.configure_native(cfg, source)
    base = native.base
    block = context['blocks'][index]
    if (block.core_group_start, block.core_group_stop) != (128*index, 128*(index+1)):
        raise RuntimeError('selected block frequency ownership changed')
    material = base.phase7b7i._second_full_material(template)
    fields = base.phase7b7i.phase7b7e._local_fields(context, block, material)
    global_state = np.memmap(source, mode='r', dtype='<f8', shape=pipeline.SHAPE)
    active_start = int(context['stencil'].active_outer_group_start)
    active_stop = int(context['stencil'].active_outer_group_stop)
    first = max(block.outer_group_start, active_start)
    last = min(block.outer_group_stop, active_stop)
    if last > first:
        fields['outer'][first-block.outer_group_start:last-block.outer_group_start] = global_state[first-active_start:last-active_start]
    core = slice(block.core_group_start, block.core_group_stop)
    initial = np.array(global_state[core], copy=True)
    del global_state
    old_hash = pipeline.block_hash(source, core.start, core.stop)
    mu, weight = np.asarray(context['mu']), np.asarray(context['weight'])
    width = np.diff(context['stencil'].active_lab_edge_hz)[core]

    def source_map(guess):
        result = base.phase7b7i.phase7b7e.solve_mixed_frame_ale_group_step(
            block.local_stencil, fields['old_edge'], fields['new_edge'], mu, weight,
            fields['initial'], fields['outer'], fields['true_absorption'],
            fields['thermal_emissivity'], fields['scattering'], context['beta'], context['duration_s'],
            propagation_speed_cm_s=base.phase7b7i.phase7b7e.LIGHT_SPEED_CM_S,
            source_iteration_initial_guess=guess, diagnostic_fixed_iteration_count=1,
            spatial_scheme='hybrid_step_turning_upwind', source_map_only=True)
        return np.array(result.final_lab_intensity_density, copy=True)

    started = time.perf_counter()
    mapped = source_map(initial)
    map_seconds = time.perf_counter()-started
    archived = np.memmap(ROOT/record['output']['path'], mode='r', dtype='<f8', shape=pipeline.SHAPE)
    replay = verify_map_replay(initial, mapped, archived[core])
    del archived
    transform = lorentz_ray_transform(mu, weight, context['beta'])
    extinction = lorentz_remap_comoving_group_extinction_to_lab(
        np.broadcast_to((fields['true_absorption']+fields['scattering'])[:, None, :],
                        (block.local_stencil.comoving_collision_group_count, mu.size, len(context['beta']))),
        block.local_stencil.comoving_collision_edge_hz, block.local_stencil.active_lab_edge_hz,
        transform.doppler_lab_to_comoving)
    krylov = mixed_frame_spatial_source_residual_correction(
        mapped-initial, fields['old_edge'], fields['new_edge'], block.local_stencil.outer_lab_edge_hz,
        block.local_stencil.comoving_collision_edge_hz, block.local_stencil.active_lab_edge_hz,
        block.local_stencil.active_outer_group_start, block.local_stencil.active_outer_group_stop,
        mu, weight, context['beta'], extinction, fields['scattering'], context['duration_s'],
        gmres_relative_tolerance=1e-5, gmres_restart=8, gmres_maximum_restart_cycles=2,
        allow_turning_ray_upwind=True, allow_incomplete_krylov=True)
    candidate, fresh, result = evaluate_direction(initial, mapped, krylov.correction, source_map)
    raw_boundary = float(np.sum(abs(base._block_flux(mapped, mu, weight, width)-base._block_flux(initial, mu, weight, width))))
    new_boundary = float(np.sum(abs(base._block_flux(fresh, mu, weight, width)-base._block_flux(candidate, mu, weight, width))))
    seconds = time.perf_counter()-started
    rss = base.ru_maxrss_to_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, sys.platform)/1024**2
    result['checks'].update(boundary_not_worse=new_boundary <= raw_boundary,
                            finite_budget=krylov.gmres_iteration_count <= 16,
                            memory_below_6gib=rss < 6144,
                            time_below_20_maps=seconds <= 20*map_seconds)
    if old_hash != pipeline.block_hash(source, core.start, core.stop):
        raise RuntimeError('source block changed during pilot')
    result.update(label=label, block_index=index, replay=replay, raw_map_s=map_seconds,
                  wall_s=seconds, peak_rss_mib=rss, raw_boundary_absolute=raw_boundary,
                  fresh_boundary_absolute=new_boundary, gmres_iterations=krylov.gmres_iteration_count,
                  gmres_info=krylov.gmres_reported_info, linear_audit_passed=krylov.fixed_point_converged,
                  linear_scaled_linf=krylov.final_scaled_linf_linear_residual,
                  mean_consistency=krylov.final_comoving_mean_consistency_linf,
                  input_block_sha256=old_hash, core_groups=[core.start, core.stop],
                  frequency_edges_hz=[float(context['stencil'].active_lab_edge_hz[core.start]),
                                      float(context['stencil'].active_lab_edge_hz[core.stop])],
                  eligible_for_further_block_review=all(result['checks'].values()),
                  global_candidate_written=False, formal_acceptance_changed=False)
    pipeline.write_json(out/f'{label}-block{index:02d}.json', result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    p.add_argument('--worker', choices=SOURCES)
    p.add_argument('--block', type=int, choices=BLOCKS)
    args = p.parse_args()
    pipeline.require_allocation(2)
    out = pipeline.safe_path(ROOT, args.run)
    out.relative_to(ROOT/'outputs/hpc')
    if args.worker:
        if args.block is None: raise ValueError('worker requires block')
        worker(out, args.worker, args.block)
        return
    out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out)
    pipeline.write_json(out/'status.json', {'status':'preparing', 'new_full_maps':0})
    try:
        for f in ['operations/paired_block_krylov.py', 'operations/paired_block_krylov.sbatch',
                  'operations/review_small_step_evidence.py', 'operations/prepare_encoded_backtrack.py',
                  'operations/audit_mixture_material_residual.py']:
            snap.save(f)
        cases, trials, inventories = {}, {}, []
        for label, (source, digest) in SOURCES.items():
            state = snap.read(source+'/state.json', digest)
            if state.get('active_map') or state.get('pending_feedback') or len(state['history']) != 2:
                raise RuntimeError('source is not the declared settled two-map run')
            cfg = snap.read(source+'/config.json', state['config_sha256'])
            trial = load_arrays(snap.save(source+'/trial_material.npz', state['trial_sha256']))
            trials[label] = trial
            audit_native_trial(cfg, trial)
            inventory = {}
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
                if c['path'].startswith(('src/', 'scripts/', 'hpc/')): inventory[c['path']] = c['sha256']
            inventories.append(inventory)
            row = state['history'][-1]
            pair = {}
            for key in ('input', 'output'):
                claim = {'path':row[key+'_path'], 'sha256':row[key+'_sha256'], 'size_bytes':pipeline.STATE_BYTES}
                if pipeline.verify_claims(ROOT, [claim], hash_files=True):
                    raise RuntimeError('archived map state bytes changed')
                pair[key] = claim
            pair.update(config=pipeline.claim(ROOT/source/'config.json'),
                        trial=pipeline.claim(ROOT/source/'trial_material.npz'),
                        state=pipeline.claim(ROOT/source/'state.json'))
            cases[label] = pair
        zero_matches_candidate(trials['base'], trials['trial'])
        if inventories[0] != inventories[1]: raise RuntimeError('base and candidate use different native kernels')
        plan = {'environment':pipeline.environment(), 'cases':cases, 'blocks':list(BLOCKS),
                'gmres_restart':8, 'gmres_cycles':2, 'gmres_tolerance':1e-5,
                'maximum_full_maps':0, 'maximum_local_source_maps_per_case':3,
                'case_count':4, 'workers':2, 'source_kernels_identical':True,
                'limitation':'Fixed source-run halos; local corrections only, no global state or error certificate.'}
        pipeline.write_json(out/'declaration.json', plan)
        pipeline.write_json(out/'status.json', {'status':'running', 'new_full_maps':0})
        def launch(case):
            label, index = case
            with (out/f'{label}-block{index:02d}.out').open('x') as stdout, (out/f'{label}-block{index:02d}.err').open('x') as stderr:
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--run', args.run,
                                '--worker', label, '--block', str(index)], check=True, cwd=ROOT,
                               stdout=stdout, stderr=stderr)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(launch, [(label, i) for label in SOURCES for i in BLOCKS]))
        # 中文：结束后重新核验完整输入和原map输出，防止旋转槽/并发覆盖污染试验。
        for record in cases.values():
            if pipeline.verify_claims(ROOT, list(record.values()), hash_files=True):
                raise RuntimeError('source changed during experiment')
        rows = [pipeline.read(out/f'{label}-block{i:02d}.json') for label in SOURCES for i in BLOCKS]
        pipeline.write_json(out/'summary.json', {'rows':rows,
            'all_four_local_cases_passed':all(r['eligible_for_further_block_review'] for r in rows),
            'new_full_maps':0, 'new_feedback_pairs':0, 'formal_acceptance_changed':False,
            'full_frequency_run_authorized_by_this_pilot':False,
            'source_bytes_unchanged':True})
        pipeline.write_json(out/'status.json', {'status':'complete', 'new_full_maps':0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status':'failed', 'error':str(exc), 'new_full_maps':0})
        raise


if __name__ == '__main__': main()
