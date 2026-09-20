"""Replay encoded residuals and localize failed contraction without changing gates."""
from __future__ import annotations
import argparse
import csv
from dataclasses import asdict
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_common_seed_precision import same_material
from operations.audit_affine_feedback_histories import require_settled_pair
from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms

CURRENT = 'outputs/hpc/subspace-feedback-20260920'
PREVIOUS = 'outputs/hpc/mixed-followup-20260920'
BASELINE = 'outputs/hpc/baseline-zero-control-20260919'


def decomposition(base, candidate, mass):
    """Signed squared-norm excess by layer and component, in the unchanged codec."""
    mass = np.asarray(mass, dtype=float)
    bn = asdict(encoded_residual_norms(base, mass))
    cn = asdict(encoded_residual_norms(candidate, mass))
    if any(v <= 0 for v in bn.values()):
        raise ValueError('baseline norms must be positive; no invented denominator')
    b, c = np.asarray(base).reshape(-1, 4), np.asarray(candidate).reshape(-1, 4)
    delta = c-b
    # 中文：精确恒等式分离方向交叉项与二次项；不是新接受门，也不是热能分量。
    cross, quadratic = 2*b*delta, delta*delta
    excess = cross+quadratic
    weighted = excess*(mass/mass.sum())[:, None]
    if not np.all(np.isfinite(excess)) or not np.all(np.isfinite(weighted)):
        raise ArithmeticError('nonfinite residual decomposition')
    for got, want in ((excess.sum(), cn['l2']**2-bn['l2']**2),
                      (weighted.sum(), cn['mass_weighted']**2-bn['mass_weighted']**2)):
        if abs(got-want) > 1e-12*max(bn['l2']**2, cn['l2']**2):
            raise ArithmeticError('squared-norm identity failed')
    return {'base_norms': bn, 'candidate_norms': cn,
            'candidate_over_base': {k: cn[k]/bn[k] for k in bn},
            'squared_l2_excess': float(excess.sum()), 'squared_mass_norm_excess': float(weighted.sum()),
            'component_cross_terms': cross.sum(axis=0).tolist(),
            'component_quadratic_terms': quadratic.sum(axis=0).tolist(),
            'component_l2_excess': excess.sum(axis=0).tolist(),
            'component_mass_excess': weighted.sum(axis=0).tolist(),
            'cell_l2_excess': excess.sum(axis=1).tolist(), 'cell_mass_excess': weighted.sum(axis=1).tolist(),
            'cell_component_excess': excess.tolist(),
            'note': 'Signed contributions sum to the squared norm difference; log-codec components are not physical energy shares.'}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        for name in ('operations/audit_outer_contraction.py', 'operations/audit_outer_contraction.sbatch',
                     'scripts/phase7b9_formal_feedback_pair_adapter.py', 'src/eccentric_tde_observer/formal_feedback_pair.py'):
            snap.save(name)
        protocols = {}; summaries = {}; trials = {}; states = {}
        for label, run in (('candidate', CURRENT), ('previous_candidate', PREVIOUS), ('baseline_control', BASELINE)):
            state = snap.read(run+'/state.json'); states[label] = state
            cfg = snap.read(run+'/config.json', state['config_sha256'])
            trials[label] = load_arrays(snap.save(run+'/trial_material.npz', state['trial_sha256']))
            audit_native_trial(cfg, trials[label])
            if label == 'baseline_control':
                status = snap.read(run+'/control_status.json'); control = snap.read(run+'/control_result.json')
                if status['status'] != 'complete' or status['new_maps'] != 2 or state.get('active_map') or state.get('pending_feedback'):
                    raise RuntimeError('baseline control is not complete and settled')
                claim = control['feedback_protocol']; proto = snap.read(claim['path'], claim['sha256'])
                protocols[label] = (proto, claim['sha256'], run)
            else:
                pair = require_settled_pair(state); folder = run+'/feedback-round1'
                summary = snap.read(folder+'/feedback_summary.json')
                if summary['protocol_sha256'] != pair['protocol_sha256']:
                    raise RuntimeError('feedback summary differs from settled round')
                proto = snap.read(folder+'/feedback_protocol.json', pair['protocol_sha256'])
                protocols[label] = (proto, pair['protocol_sha256'], folder); summaries[label] = summary
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
            for c in proto['sources'].values():
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
        same_material(trials['candidate'], trials['previous_candidate'])
        candidate, base = trials['candidate'], trials['baseline_control']
        if float(base['relaxation']) != 0 or not np.array_equal(base['encoded_state'], candidate['base_encoded_state']):
            raise RuntimeError('zero-control material is not the candidate base')
        for key in ('base_encoded_state', 'base_residual', 'finite_direction', 'density_g_cm3', 'phase_index', 'step_duration_s'):
            if not np.array_equal(base[key], candidate[key]): raise RuntimeError('baseline physical identity changed: '+key)
        source_proto = protocols['candidate'][0]
        for proto, _, _ in protocols.values():
            for key in ('base_residual', 'physical_old_time_level'):
                if proto['sources'][key]['sha256'] != source_proto['sources'][key]['sha256']:
                    raise RuntimeError('baseline residual or physical old state identity differs')
        original_claim = source_proto['sources']['base_residual']
        archived = np.load(snap.save(original_claim['path'], original_claim['sha256']), allow_pickle=False)
        if not np.array_equal(archived, candidate['base_residual']):
            raise RuntimeError('trial metadata and formal baseline residual differ')
        vectors = {}; results = {}; masses = None
        for label, (proto, digest, folder) in protocols.items():
            vectors[label] = {}; results[label] = {}
            for i, endpoint in enumerate(('previous', 'final')):
                manifest = snap.read(folder+'/feedback/'+endpoint+'_manifest.json')
                claim = proto['sources'][endpoint+'_radiation']; row = states[label]['history'][i]
                if (manifest['status'] != 'complete' or not manifest['state_gate_passed']
                    or manifest['protocol_sha256'] != digest or manifest['state_sha256'] != claim['sha256']
                    or manifest['state_path'] != claim['path'] or row['input_sha256'] != claim['sha256']
                    or row['input_path'] != claim['path']
                    or sorted(b['block_index'] for b in manifest['completed_blocks']) != list(range(76))):
                    raise RuntimeError('feedback endpoint lineage or ownership failed')
                for block in manifest['completed_blocks']:
                    snap.save(block['partial_path'], block['partial_sha256'])
                if label in summaries:
                    recorded = summaries[label][endpoint+'_feedback']
                    if recorded['feedback_artifact_sha256'] != manifest['feedback_artifact_sha256']:
                        raise RuntimeError('summary and manifest feedback hashes differ')
                fb = load_arrays(snap.save(manifest['feedback_artifact_path'], manifest['feedback_artifact_sha256']))
                _, residual, context = adapter._material_response_residual(proto, fb)
                if masses is not None and not np.array_equal(masses, context['cell_mass']):
                    raise RuntimeError('mass measure changed')
                masses = np.asarray(context['cell_mass']); vectors[label][endpoint] = residual
                results[label][endpoint] = {'norms': asdict(encoded_residual_norms(residual, masses)),
                    'radiation_residual': row['residual'], 'feedback_sha256': manifest['feedback_artifact_sha256']}
                if label in summaries and endpoint == 'final':
                    summary = summaries[label]
                    stored = np.load(snap.save(summary['encoded_residual_path'], summary['encoded_residual_sha256']), allow_pickle=False)
                    if not np.array_equal(residual, stored):
                        raise RuntimeError('same-platform replay differs from the actual encoded residual')
        comparisons = {'formal_archived': decomposition(archived, vectors['candidate']['final'], masses)}
        for endpoint in ('previous', 'final'):
            comparisons['zero_control_'+endpoint] = decomposition(vectors['baseline_control'][endpoint], vectors['candidate']['final'], masses)
        metrics = {'l2': 'candidate_to_base_residual_l2_ratio', 'mass_weighted': 'candidate_to_base_mass_weighted_norm_ratio',
                   'maximum_cell': 'candidate_to_base_maximum_cell_norm_ratio'}
        for key, field in metrics.items():
            if not np.isclose(comparisons['formal_archived']['candidate_over_base'][key], summaries['candidate']['comparison'][field], rtol=1e-12, atol=0):
                raise RuntimeError('independent norm decomposition does not reproduce formal ratio')
        drift = {name: asdict(encoded_residual_norms(v['final']-v['previous'], masses)) for name, v in vectors.items()}
        result = {'environment': pipeline.environment(), 'scope': 'read-only encoded contraction and baseline drift audit',
            'component_labels': ['log specific gas thermal energy', 'log H II / H I', 'log He II / He I', 'log He III / He I'],
            'formal_comparison': summaries['candidate']['comparison'], 'formal_gates': summaries['candidate']['gate_checks'],
            'formal_baseline_claim': original_claim, 'pairs': results, 'comparisons': comparisons,
            'observed_adjacent_drifts': drift,
            'baseline_control_final_minus_archive': asdict(encoded_residual_norms(vectors['baseline_control']['final']-archived, masses)),
            'candidate_change_since_previous_run': asdict(encoded_residual_norms(vectors['candidate']['final']-vectors['previous_candidate']['final'], masses)),
            'new_maps': 0, 'accepted_material_step': False, 'formal_acceptance_changed': False,
            'limitation': 'Neither an observed adjacent drift nor a swapped diagnostic denominator establishes a true inner error bound or a new acceptance verdict.'}
        pipeline.write_json(out/'audit.json', result)
        with (out/'cell_excess.csv').open('x', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n'); writer.writerow(['cell_index', 'cell_mass_g_cm2', 'squared_l2_excess', 'squared_mass_norm_excess'])
            c = comparisons['formal_archived']
            for i in range(len(masses)):writer.writerow([i, masses[i], c['cell_l2_excess'][i], c['cell_mass_excess'][i]])
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(9, 6), layout='constrained')
        for ax, field, text in zip(axes, ('cell_l2_excess', 'cell_mass_excess'), ('Squared L2 excess', 'Squared mass-weighted norm excess')):
            ax.plot(comparisons['formal_archived'][field]);ax.axhline(0, color='black', lw=.6)
            ax.set(xlabel='Material half-column cell index (not geometric height)', ylabel=text)
        fig.suptitle('Candidate minus frozen baseline: signed encoded-norm contributions')
        fig.savefig(out/'cell_excess.png', dpi=160);plt.close(fig)
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)}); raise


if __name__ == '__main__':main()
