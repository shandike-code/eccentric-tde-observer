"""Read-only Anderson(1) feasibility scans on each history's last three states.

Reuse the historical algebra, not its protocol loader or candidate writer.
Predictions require a future fresh operator map; nothing is accepted here.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'src'), str(ROOT / 'scripts')]
import pipeline
from operations.audit_paired_histories import BASE, OLD, REPLAY
from operations.review_small_step_evidence import Snapshot
from scripts import phase7b9bx_slow_mode_anderson as algebra


def basis_claims(state):
    if len(state.get('history', [])) != 4 or state.get('active_map'):
        raise ValueError('expected completed four-map history')
    a, b = state['history'][-2:]
    if a['output_path'] != b['input_path'] or a['output_sha256'] != b['input_sha256']:
        raise ValueError('last maps are not consecutive')
    return [{'path': a['input_path'], 'sha256': a['input_sha256']},
            {'path': b['input_path'], 'sha256': b['input_sha256']},
            {'path': b['output_path'], 'sha256': b['output_sha256']}]


def serial(value):
    if isinstance(value, np.ndarray): return serial(value.tolist())
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)): raise ArithmeticError('NaN in algebraic scan')
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, dict): return {k: serial(v) for k, v in value.items()}
    if isinstance(value, list): return [serial(v) for v in value]
    return value


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', required=True); a = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, a.run); out.relative_to(ROOT / 'outputs/hpc')
    out.mkdir(parents=True, exist_ok=False); snap = Snapshot(out)
    pipeline.write_json(out / 'status.json', {'status': 'running'})
    try:
        if snap.read(REPLAY + '/status.json')['status'] != 'complete':
            raise RuntimeError('owed pair must be independently completed first')
        for f in ('operations/diagnose_history_slow_modes.py', 'operations/diagnose_history_slow_modes.sbatch',
                  'scripts/phase7b9bx_slow_mode_anderson.py'):
            snap.save(f)
        master = snap.save(pipeline.MASTER)
        with np.load(master, allow_pickle=False) as z: edges = z['active_edge_hz'].copy()
        result = {'environment': pipeline.environment(), 'scope': 'predictions only, no candidate bytes written',
                  'new_maps': 0, 'fresh_map_required': True,
                  'null_note': 'null positivity upper bound means unbounded, not a replacement intensity', 'histories': {}}
        for name, source in (('base', BASE), ('old', OLD)):
            state = snap.read(source + '/state.json'); cfg = snap.read(source + '/config.json', state['config_sha256'])
            if not any(r['sha256'] == pipeline.sha256(master) for r in cfg['sources']):
                raise RuntimeError('frequency master not among frozen dependencies')
            basis = basis_claims(state)
            for claim in basis:
                path = ROOT / claim['path']
                if path.stat().st_size != pipeline.STATE_BYTES or pipeline.sha256(path) != claim['sha256']:
                    raise RuntimeError('radiation basis bytes changed')
            config = {'scan_frequency_chunk': 16, 'diagnostic_frequency_block': 128,
                      'minimum_forward_picard_fraction': 1., 'maximum_forward_picard_fraction': 96.}
            for i, claim in enumerate(basis, 9): config[f'x{i}_state_path'] = claim['path']
            pipeline.write_json(out / f'{name}-declaration.json', {'basis': basis, 'configuration': config,
                                'source_state': pipeline.claim(ROOT / source / 'state.json')})
            # 中文：只计算全局系数与正性上界，不裁剪任何辐射单元，不写外推态。
            with np.errstate(invalid='raise', over='raise', divide='raise'):
                direction = algebra._scan_direction(config, pipeline.SHAPE)
                fraction = float(direction['selected_forward_fraction'])
                metrics = algebra._candidate_metrics(config, pipeline.SHAPE, fraction, edges)
            latest = state['history'][-1]['residual']
            gates = {'basis_positive': bool(np.all(direction['minimum_basis_intensities'] >= 0)),
                     'direction_resolved': bool(direction['difference_ratio'] > 1e-12),
                     'forward_fraction_above_one': fraction > 1.,
                     'coefficient_l1_below_192': abs(1-fraction)+abs(fraction) < 192.,
                     'predicted_positive': metrics['candidate_negative_count'] == 0 and metrics['predicted_map_negative_count'] == 0,
                     'predicted_max_norm_ratio_below_099': metrics['predicted_global_original_operator_residual']/latest < .99,
                     'predicted_boundary_pass': metrics['predicted_boundary_spectrum_l1'] < 1e-3 and metrics['predicted_boundary_bolometric_fraction'] < 1e-3}
            for claim in basis:
                if pipeline.sha256(ROOT / claim['path']) != claim['sha256']:
                    raise RuntimeError('radiation basis changed during scan')
            result['histories'][name] = serial({'direction': direction, 'metrics': metrics, 'algebraic_gates': gates,
                 'algebraic_feasibility': all(gates.values()), 'latest_actual_residual': latest,
                 'actual_candidate_residual': None, 'actual_map_performed': False})
            pipeline.write_json(out / 'prediction.json', result)
        pipeline.write_json(out / 'status.json', {'status': 'complete', 'new_maps': 0, 'candidate_written': False})
    except BaseException as exc:
        pipeline.write_json(out / 'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__': main()
