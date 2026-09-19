"""Locate exact zero-cell obstructions to positive cross-history extrapolation."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.scan_cross_history_direction import chunks

SCAN = 'outputs/hpc/cross-history-direction-scan-20260919'


def obstruction_stats(paths, shape):
    """An exactly zero base cell and positive old cell forbids every g > 0."""
    results = {name: {'count': 0, 'old_subnormal_count': 0, 'maximum_old_intensity': 0.,
                     'whole_field_scale': 0., 'block_counts': [0]*((shape[0]+127)//128), 'largest_cells': []}
               for name in ('candidate', 'predicted_map')}
    for start, (xb, yb, xo, yo) in chunks(paths, shape):
        for name, base, old in (('candidate', xb, xo), ('predicted_map', yb, yo)):
            r = results[name]
            # 中文：这是严格非负域的几何障碍；再小也不删除、不加floor、不称物理可忽略。
            mask = (base == 0.) & (old > 0.)
            r['count'] += int(mask.sum())
            r['old_subnormal_count'] += int(np.count_nonzero(mask & (old < np.finfo(np.float64).tiny)))
            r['whole_field_scale'] = max(r['whole_field_scale'], float(np.max(base)), float(np.max(old)))
            for i, count in enumerate(mask.sum(axis=(1, 2))): r['block_counts'][(start+i)//128] += int(count)
            indices = np.flatnonzero(mask)
            if not indices.size: continue
            values = old.ravel()[indices]; r['maximum_old_intensity'] = max(r['maximum_old_intensity'], float(values.max()))
            best = np.argpartition(values, max(0, len(values)-8))[-8:]
            for k in best:
                fi, angle, depth = np.unravel_index(indices[k], base.shape)
                r['largest_cells'].append({'frequency_index': int(start+fi), 'angle_index': int(angle),
                    'radiation_depth_index': int(depth), 'base_intensity': 0., 'old_intensity': float(values[k])})
            r['largest_cells'] = sorted(r['largest_cells'], key=lambda x: x['old_intensity'], reverse=True)[:8]
    for r in results.values():
        r['maximum_obstruction_over_field_scale'] = r['maximum_old_intensity']/r['whole_field_scale'] if r['whole_field_scale'] > 0 else None
        r['positive_gamma_forbidden_by_exact_zero'] = r['count'] > 0
    return results


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        if snap.read(SCAN+'/status.json')['status'] != 'complete': raise RuntimeError('scan incomplete')
        plan = snap.read(SCAN+'/declaration.json'); prediction = snap.read(SCAN+'/prediction.json')
        for name in ('operations/diagnose_cross_history_positivity.py', 'operations/diagnose_cross_history_positivity.sbatch',
                     'operations/scan_cross_history_direction.py'): snap.save(name)
        basis = plan['basis']
        for c in basis:
            if (ROOT/c['path']).stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(ROOT/c['path']) != c['sha256']:
                raise RuntimeError('basis SHA or size mismatch')
        result = obstruction_stats([ROOT/c['path'] for c in basis], pipeline.SHAPE)
        with np.load(snap.save(pipeline.MASTER), allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        for row in result.values():
            for cell in row['largest_cells']:
                i = cell['frequency_index']; cell['frequency_edges_hz'] = edges[i:i+2].tolist()
        for c in basis:
            if pipeline.sha256(ROOT/c['path']) != c['sha256']: raise RuntimeError('basis changed during read-only audit')
        pipeline.write_json(out/'obstructions.json', {'environment': pipeline.environment(), 'basis': basis,
            'scan_feasible_interval': prediction['direction']['feasible_interval'], 'statistics': result,
            'new_maps': 0, 'original_bytes_changed': False, 'science_gates_relaxed': False,
            'limitation': 'Small intensity relative to the global peak does not bound its heating or material-response importance; exact zero does not establish its physical cause.'})
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__': main()
