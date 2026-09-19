"""Audit radiation-history sensitivity before and after validated affine acceleration."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'hpc'), str(ROOT / 'src'), str(ROOT / 'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot, decoded_field_audit
from operations.prepare_common_seed_precision import same_material
from operations.prepare_encoded_backtrack import load_arrays
from operations.conservative_residual_diagnostic import equation_residual, norms
from operations.replay_equation_baseline import pair_comparison
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from scripts import phase7b9_formal_feedback_pair_adapter as adapter

BASE = 'outputs/hpc/affine-base-feedback-20260919'
OLD = 'outputs/hpc/affine-old-feedback-20260919'
REPLAY = 'outputs/hpc/paired-base-round2-nohuge-replay-20260919'
FOLDERS = {
    'base_before': REPLAY,
    'old_before': 'outputs/hpc/paired-precision-old-history-20260919/feedback-round2',
    'base_after': BASE + '/feedback-round1',
    'old_after': OLD + '/feedback-round1',
}


def require_settled_pair(state):
    """Only inspect a completed pair whose endpoint claims match its fresh maps."""
    rounds = state.get('diagnostic', {}).get('rounds', [])
    if (state.get('status') not in {'diagnostic_round_complete', 'one_material_trial_accepted'}
        or state.get('active_map') or state.get('pending_feedback')
        or len(state.get('history', [])) != 2 or len(rounds) != 1):
        raise RuntimeError('new feedback pair is not settled')
    pair = rounds[0]
    if pair.get('endpoints') != [1, 2]:
        raise RuntimeError('unexpected new pair endpoints')
    for index, label in enumerate(('previous', 'final')):
        row = state['history'][index]; claim = pair['endpoints_claim'][label]
        if claim['path'] != row['input_path'] or claim['sha256'] != row['input_sha256']:
            raise RuntimeError('completed pair refers to unrelated radiation endpoints')
    return pair


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run)
    out.relative_to(ROOT / 'outputs/hpc')
    out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out)
    pipeline.write_json(out / 'status.json', {'status': 'running'})
    try:
        for name in ('operations/audit_affine_feedback_histories.py', 'operations/audit_affine_feedback_histories.sbatch',
                     'operations/conservative_residual_diagnostic.py', 'operations/replay_equation_baseline.py',
                     'diagnostics/material_energy_ledger.py'):
            snap.save(name)
        state = snap.read(BASE + '/state.json')
        old_state = snap.read(OLD + '/state.json')
        new_pairs = {'base_after': require_settled_pair(state), 'old_after': require_settled_pair(old_state)}
        for folder, current in ((BASE, state), (OLD, old_state)):
            config = snap.read(folder + '/config.json', current['config_sha256'])
            for claim in config['sources']:
                if not claim['path'].endswith('.dat'): snap.save(claim['path'], claim['sha256'])
        trial = load_arrays(snap.save(BASE + '/trial_material.npz', state['trial_sha256']))
        other = load_arrays(snap.save(OLD + '/trial_material.npz', old_state['trial_sha256']))
        same_material(trial, other)
        codec = GroundStateLogSimplexCodec(len(trial['density_g_cm3']))
        native = decoded_field_audit(trial, codec.decode(trial['encoded_state']))
        if not native['native_input_identity_pass']:
            raise RuntimeError('candidate native input differs from encoded decode')
        replay_status = snap.read(REPLAY + '/status.json')
        if replay_status['status'] != 'complete':
            raise RuntimeError('full pair replay incomplete')
        first_summary = snap.read(REPLAY + '/feedback_summary.json')
        first_protocol = snap.read(REPLAY + '/feedback_protocol.json', first_summary['protocol_sha256'])
        old = load_arrays(snap.save(OLD_TIME_LEVEL, first_protocol['sources']['physical_old_time_level']['sha256']))
        phase = int(trial['phase_index']); dt = float(trial['step_duration_s']); rho = trial['density_g_cm3']
        if dt != float(old['step_duration_s'][phase]) or not np.array_equal(rho, old['density_g_cm3'][phase]):
            raise RuntimeError('physical time/density mismatch')
        masses = old['cell_mass_g_cm2']
        result = {'scope': 'fixed-material finite-accuracy history comparison', 'environment': pipeline.environment(),
                  'git': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  'native_identity': native, 'alpha': float(trial['relaxation']), 'dt_s': dt,
                  'acceptance_definition_unchanged': True, 'new_maps': 0, 'pairs': {}}
        vectors = {}; books = {}; feedbacks = {}
        for key, folder in FOLDERS.items():
            summary = snap.read(folder + '/feedback_summary.json')
            proto = snap.read(folder + '/feedback_protocol.json', summary['protocol_sha256'])
            if key in new_pairs and summary['protocol_sha256'] != new_pairs[key]['protocol_sha256']:
                raise RuntimeError('new summary is not the committed feedback round')
            if proto['sources']['trial_material']['sha256'] != state['trial_sha256']:
                raise RuntimeError('pair candidate differs')
            if proto['sources']['physical_old_time_level']['sha256'] != first_protocol['sources']['physical_old_time_level']['sha256']:
                raise RuntimeError('pair old time level differs')
            vectors[key] = {}; books[key] = {}; feedbacks[key] = {}
            entry = {'formal_encoded_comparison': summary['comparison'], 'gates': summary['gate_checks'],
                     'decision': summary['decision'], 'endpoints': {},
                     'encoded_noise_evaluated': summary['comparison'].get('inner_noise_to_trial_signal_l2_ratio') is not None,
                     'ledger_note_caveat': 'The legacy ledger unevaluated sentence is unconditional; use the formal summary for actual encoded-noise availability.'}
            for label in ('previous', 'final'):
                manifest = snap.read(folder + '/feedback/' + label + '_manifest.json')
                claim = proto['sources'][label + '_radiation']
                if (manifest['status'] != 'complete' or not manifest['state_gate_passed']
                    or manifest['protocol_sha256'] != summary['protocol_sha256']
                    or manifest['state_sha256'] != claim['sha256'] or manifest['state_path'] != claim['path']):
                    raise RuntimeError('feedback endpoint lineage failed')
                if sorted(r['block_index'] for r in manifest['completed_blocks']) != list(range(76)):
                    raise RuntimeError('block ownership incomplete')
                for partial in manifest['completed_blocks']:
                    snap.save(partial['partial_path'], partial['partial_sha256'])
                art = summary[label + '_feedback']
                if art['feedback_artifact_sha256'] != manifest['feedback_artifact_sha256']:
                    raise RuntimeError('summary/manifest feedback SHA mismatch')
                fb = load_arrays(snap.save(art['feedback_artifact_path'], art['feedback_artifact_sha256']))
                if any(not np.all(np.isfinite(v)) for v in fb.values() if np.issubdtype(v.dtype, np.number)):
                    raise RuntimeError('nonfinite feedback array')
                book = ledger(fb, rho, dt, old['temperature_k'][phase], old['hydrogen_fraction'][phase], old['helium_fraction'][phase])
                vector = equation_residual(codec, trial['encoded_state'], book['total_old'], book['gas_old'], book['radiative_energy'], book['new_h'], book['new_he'])
                vectors[key][label] = vector; books[key][label] = book; feedbacks[key][label] = fb
                entry['endpoints'][label] = {'equation_norms': norms(vector, masses),
                    'failed_cells': int(np.count_nonzero(book['remaining'] <= 0)),
                    'minimum_target_over_old_gas': float(np.min(book['remaining_relative_to_old_gas_heat'])),
                    'target_over_old_gas_by_cell': book['remaining_relative_to_old_gas_heat'].tolist(),
                    'equation_by_cell': vector.tolist()}
            entry['adjacent_equation_difference'] = norms(vectors[key]['final'] - vectors[key]['previous'], masses)
            result['pairs'][key] = entry
        result['cross_history'] = {}
        for stage in ('before', 'after'):
            b, o = f'base_{stage}', f'old_{stage}'
            result['cross_history'][stage] = {
                'equation_gap_norms': norms(vectors[b]['final'] - vectors[o]['final'], masses),
                'feedback_difference': adapter._feedback_stability_comparison(feedbacks[b]['final'], feedbacks[o]['final']),
                'observed_drift_comparison': pair_comparison(tuple(vectors[o].values()), tuple(vectors[b].values()), masses)}
        result['limitations'] = ['Equation vectors are diagnostic, not the formal encoded acceptance residual.',
                                'Adjacent drift is not a true inner error bound.',
                                'Different history iteration counts are not error-matched; no root-existence verdict.']
        pipeline.write_json(out / 'comparison.json', result)
        np.savez(out / 'vectors.npz', **{f'{k}_{l}': v for k, p in vectors.items() for l, v in p.items()})
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), layout='constrained')
        for name, color in (('base', 'tab:blue'), ('old', 'tab:orange')):
            for stage, style in (('before', '--'), ('after', '-')):
                key = f'{name}_{stage}'
                axes[0].plot(vectors[key]['final'][:, 0], style, color=color, label=f'{name}, {stage}')
                axes[1].plot(books[key]['final']['remaining_relative_to_old_gas_heat'], style, color=color)
        axes[0].set(xlabel='Material layer index', ylabel='Fixed-scale energy equation defect')
        axes[1].set(xlabel='Material layer index', ylabel='Target gas energy / old gas energy')
        axes[1].axhline(0, color='black', linewidth=.7)
        axes[0].legend(); fig.suptitle('Before/after acceleration: no accepted coupled material solution')
        fig.savefig(out / 'history_comparison.png', dpi=160); plt.close(fig)
        pipeline.write_json(out / 'status.json', {'status': 'complete', 'new_maps': 0, 'accepted_step': False})
    except BaseException as exc:
        pipeline.write_json(out / 'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__':
    main()
