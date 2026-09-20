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
from operations.material_direction_diagnostic import common_direction, latest_pair, secant_diagnostic
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms

CURRENT = 'outputs/hpc/half-step-precision-20260920'
PREVIOUS = 'outputs/hpc/subspace-feedback-20260920'
BASELINE = 'outputs/hpc/baseline-zero-control-20260919'


from operations.audit_outer_contraction import decomposition

def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        for name in ('operations/audit_half_step_direction.py', 'operations/audit_half_step_direction.sbatch',
                     'operations/material_direction_diagnostic.py',
                     'scripts/phase7b9_formal_feedback_pair_adapter.py', 'src/eccentric_tde_observer/formal_feedback_pair.py'):
            snap.save(name)
        protocols = {}; summaries = {}; trials = {}; states = {}
        for label, run in (('candidate', CURRENT), ('full_step', PREVIOUS), ('baseline_control', BASELINE)):
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
                pair = latest_pair(state); folder = str(Path(pair['ledger']).parent)
                summary = snap.read(folder+'/feedback_summary.json')
                if summary['protocol_sha256'] != pair['protocol_sha256']:
                    raise RuntimeError('feedback summary differs from settled round')
                proto = snap.read(folder+'/feedback_protocol.json', pair['protocol_sha256'])
                protocols[label] = (proto, pair['protocol_sha256'], folder); summaries[label] = summary
                gates = summary['gate_checks']
                if (set(gates) != REQUIRED_GATES or {k for k,v in gates.items() if v is not True}
                        != {'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass'}):
                    raise RuntimeError('requires stable full and half candidates, each rejected only by two contraction gates')
            if proto['sources']['trial_material']['sha256'] != state['trial_sha256']:
                raise RuntimeError('formal protocol and run disagree about actual material bytes')
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
            for c in proto['sources'].values():
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
        common_direction(trials['candidate'], trials['full_step'])
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
                claim = proto['sources'][endpoint+'_radiation']; row = states[label]['history'][-2:][i]
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
        result = {'environment': pipeline.environment(), 'scope': 'read-only half versus full material-step direction audit',
            'component_labels': ['log specific gas thermal energy', 'log H II / H I', 'log He II / He I', 'log He III / He I'],
            'formal_comparison': summaries['candidate']['comparison'], 'formal_gates': summaries['candidate']['gate_checks'],
            'formal_baseline_claim': original_claim, 'pairs': results, 'comparisons': comparisons,
            'observed_adjacent_drifts': drift,
            'baseline_control_final_minus_archive': asdict(encoded_residual_norms(vectors['baseline_control']['final']-archived, masses)),
            'half_minus_full_residual_norms': asdict(encoded_residual_norms(vectors['candidate']['final']-vectors['full_step']['final'], masses)),
            'finite_secants': {name: secant_diagnostic(b, vectors['candidate']['final'], vectors['full_step']['final'], masses, float(candidate['relaxation'])) for name,b in [('archived',archived), ('control_previous',vectors['baseline_control']['previous']), ('control_final',vectors['baseline_control']['final'])]},
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
