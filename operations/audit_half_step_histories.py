"""Replay both endpoints of two radiation histories at identical material."""
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
from operations.material_direction_diagnostic import latest_pair
from operations.radiation_history_diagnostic import identical_material, require_ownership, difference_metrics
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from scripts import phase7b9_formal_feedback_pair_adapter as adapter
from scripts import phase7b7j_second_assembled_feedback as assembly
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
from diagnostics.material_energy_ledger import ledger, heating_decomposition, endpoint_report, mass_weights

RUNS = {'base_seed': 'outputs/hpc/half-step-base-seeded-20260920',
        'prior_seed': 'outputs/hpc/half-step-precision-20260920'}


def verify_feedback(manifest, fb, snap):
    """Reassemble all recorded blocks in their original addition order."""
    require_ownership(manifest['completed_blocks'])
    combined = assembly._zero(4096)
    for block in manifest['completed_blocks']:
        partial = load_arrays(snap.save(block['partial_path'], block['partial_sha256']))
        for key in combined:
            if partial[key].shape != combined[key].shape or not np.isfinite(partial[key]).all():
                raise RuntimeError('invalid partial array: '+key)
            combined[key] += partial[key]
    for key, full in combined.items():
        parent = full.reshape(256, 16, *full.shape[1:]).mean(axis=1)
        for name, value in ((key, full), ('parent_'+key, parent), ('half_'+key, parent[:128])):
            if not np.array_equal(value, fb[name]):
                raise RuntimeError('feedback reassembly or depth mapping differs: '+name)
    for value in fb.values():
        if np.issubdtype(value.dtype, np.number) and not np.isfinite(value).all():
            raise RuntimeError('nonfinite feedback')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run)
    out.relative_to(ROOT/'outputs/hpc')
    out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out)
    pipeline.write_json(out/'status.json', {'status': 'running', 'new_maps': 0})
    try:
        for name in ('audit_half_step_histories.py', 'audit_half_step_histories.sbatch',
                     'radiation_history_diagnostic.py', 'material_direction_diagnostic.py',
                     'review_small_step_evidence.py', 'prepare_encoded_backtrack.py',
                     'prepare_half_step_after_audit.py'):
            snap.save('operations/'+name)
        snap.save('diagnostics/material_energy_ledger.py')
        protocols, summaries, trials, states = {}, {}, {}, {}
        for label, run in RUNS.items():
            state = snap.read(run+'/state.json'); states[label] = state
            pair = latest_pair(state)
            cfg = snap.read(run+'/config.json', state['config_sha256'])
            trial = load_arrays(snap.save(run+'/trial_material.npz', state['trial_sha256']))
            trials[label] = trial
            audit_native_trial(cfg, trial)
            folder = str(Path(pair['ledger']).parent)
            summary = snap.read(folder+'/feedback_summary.json'); summaries[label] = summary
            if summary['protocol_sha256'] != pair['protocol_sha256']:
                raise RuntimeError('summary lineage changed')
            proto = snap.read(folder+'/feedback_protocol.json', pair['protocol_sha256'])
            protocols[label] = (proto, pair['protocol_sha256'], folder)
            gates = summary['gate_checks']
            if set(gates) != REQUIRED_GATES or {k for k,v in gates.items() if v is not True} != {
                    'candidate_l2_contraction_pass', 'candidate_mass_weighted_contraction_pass'}:
                raise RuntimeError('reference no longer has the declared two failed gates')
            if proto['sources']['trial_material']['sha256'] != state['trial_sha256']:
                raise RuntimeError('trial source changed')
            for claim in list(cfg['sources']) + list(proto['sources'].values()):
                if not claim['path'].endswith('.dat'):
                    snap.save(claim['path'], claim['sha256'])
        identical_material(trials['base_seed'], trials['prior_seed'])
        a, b = (protocols[k][0] for k in RUNS)
        for key in ('angular_direction_count', 'physical_frequency_groups', 'radiation_depth_cell_count',
                    'material_cell_count', 'block_count', 'core_frequency_groups', 'rate_quadrature_order_per_group'):
            if a['configuration'][key] != b['configuration'][key]:
                raise RuntimeError('scientific discretization differs: '+key)
        for key in ('physical_old_time_level', 'base_residual'):
            if a['sources'][key] != b['sources'][key]:
                raise RuntimeError('physical baseline declaration differs: '+key)
        old_claim = a['sources']['physical_old_time_level']
        old = load_arrays(snap.save(old_claim['path'], old_claim['sha256']))
        trial = trials['base_seed']; phase = int(trial['phase_index'])
        mass = old['cell_mass_g_cm2']; weights = mass_weights(mass)
        vectors, feedbacks, ledgers, pairs = {}, {}, {}, {}
        for label, (proto, digest, folder) in protocols.items():
            vectors[label], feedbacks[label], ledgers[label], pairs[label] = {}, {}, {}, {}
            for i, endpoint in enumerate(('previous', 'final')):
                manifest = snap.read(folder+'/feedback/'+endpoint+'_manifest.json')
                claim = proto['sources'][endpoint+'_radiation']
                row = states[label]['history'][-2:][i]
                if (manifest['status'] != 'complete' or not manifest['state_gate_passed']
                    or manifest['protocol_sha256'] != digest or manifest['state_sha256'] != claim['sha256']
                    or manifest['state_path'] != claim['path'] or row['input_sha256'] != claim['sha256']
                    or row['input_path'] != claim['path']):
                    raise RuntimeError('feedback endpoint lineage failed')
                recorded = summaries[label][endpoint+'_feedback']
                if (recorded['feedback_artifact_sha256'] != manifest['feedback_artifact_sha256']
                    or recorded['feedback_artifact_path'] != manifest['feedback_artifact_path']):
                    raise RuntimeError('summary and manifest feedback claim differs')
                fb = load_arrays(snap.save(manifest['feedback_artifact_path'], manifest['feedback_artifact_sha256']))
                verify_feedback(manifest, fb, snap)
                response, residual, context = adapter._material_response_residual(proto, fb)
                if not np.array_equal(mass, context['cell_mass']):
                    raise RuntimeError('mass measure differs')
                led = ledger(fb, trial['density_g_cm3'], float(trial['step_duration_s']),
                             old['temperature_k'][phase], old['hydrogen_fraction'][phase], old['helium_fraction'][phase])
                for key, value in led.items():
                    if not np.isfinite(value).all(): raise RuntimeError('nonfinite ledger: '+key)
                for got, expected in ((led['target'], response.target_specific_material_energy_erg_g),
                                      (led['new_h'], response.hydrogen_fraction),
                                      (led['new_he'], response.helium_fraction)):
                    if not np.allclose(got, expected, rtol=1e-12, atol=0):
                        raise RuntimeError('independent ledger and response disagree')
                vectors[label][endpoint], feedbacks[label][endpoint], ledgers[label][endpoint] = residual, fb, led
                pairs[label][endpoint] = {'norms': asdict(encoded_residual_norms(residual, mass)),
                    'radiation_residual': row['residual'], 'feedback_sha256': manifest['feedback_artifact_sha256'],
                    'energy': endpoint_report(led, weights, endpoint)}
                if endpoint == 'final':
                    s = summaries[label]
                    stored = np.load(snap.save(s['encoded_residual_path'], s['encoded_residual_sha256']), allow_pickle=False)
                    if not np.array_equal(residual, stored):
                        raise RuntimeError('same-platform replay differs from stored formal residual')
            pipeline.write_json(out/'progress.json', {'last_replayed': label, 'new_maps': 0})
        widths = feedbacks['base_seed']['final']['subcell_width_cm']
        for endpoints in feedbacks.values():
            for fb in endpoints.values():
                if not np.array_equal(widths, fb['subcell_width_cm']) or np.any(widths <= 0):
                    raise RuntimeError('radiation volume measure differs')
        drift = {k: difference_metrics(v['final'], v['previous'], mass) for k,v in vectors.items()}
        cross = {e: difference_metrics(vectors['base_seed'][e], vectors['prior_seed'][e], mass)
                 for e in ('previous','final')}
        heating = {k: heating_decomposition(f['previous'], f['final']) for k,f in feedbacks.items()}
        heating['cross_final'] = heating_decomposition(feedbacks['prior_seed']['final'], feedbacks['base_seed']['final'])
        result = {'environment': pipeline.environment(), 'pairs': pairs, 'observed_adjacent_drifts': drift,
            'cross_history': cross, 'heating': heating, 'new_maps': 0, 'same_material_all_fields': True,
            'same_platform_final_replay_exact': True, 'all_feedback_blocks_reassembled_exact': True,
            'accepted_material_step': False, 'formal_acceptance_changed': False,
            'scope': 'fixed material, two radiation initial histories, latest formal input endpoints',
            'limitation': 'Observed adjacent and cross-history differences are not certified inner error bounds or proof of multiple/no physical solutions.'}
        pipeline.write_json(out/'audit.json', result)
        arrays = {'cell_mass_g_cm2': mass}
        for label in RUNS:
            for endpoint in ('previous','final'):
                prefix = label+'_'+endpoint+'_'
                arrays[prefix+'encoded_residual'] = vectors[label][endpoint]
                for key in ('half_photoionization_s1', 'half_total_recombination_cm3_s',
                            'half_absorbed_power_erg_s_cm3', 'half_emitted_power_erg_s_cm3'):
                    arrays[prefix+key] = feedbacks[label][endpoint][key]
                for key, value in ledgers[label][endpoint].items(): arrays[prefix+'ledger_'+key] = value
        np.savez(out/'replayed_arrays.npz', **arrays)
        with (out/'cells.csv').open('x', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['cell_index','cell_mass_g_cm2','cross_final_squared_l2',
                'base_seed_remaining_erg_g','prior_seed_remaining_erg_g','delta_q_erg_s_cm3',
                'delta_radiative_erg_g','delta_ionization_erg_g'])
            l, r = ledgers['base_seed']['final'], ledgers['prior_seed']['final']
            for i in range(len(mass)):
                writer.writerow([i, mass[i], cross['final']['cell_squared_l2'][i], l['remaining'][i],
                    r['remaining'][i], l['q'][i]-r['q'][i], l['radiative_energy'][i]-r['radiative_energy'][i],
                    l['ion_new'][i]-r['ion_new'][i]])
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(3, 1, figsize=(10,9), layout='constrained')
        for label in RUNS:
            axes[0].plot(ledgers[label]['final']['remaining']/1e12, label=label)
            axes[1].plot(drift[label]['cell_squared_l2'], label=label+' adjacent')
        axes[1].plot(cross['final']['cell_squared_l2'], label='cross-history final')
        axes[2].plot(l['radiative_energy']-r['radiative_energy'], label='delta dt Q / rho')
        axes[2].plot(-(l['ion_new']-r['ion_new']), label='minus delta ionization')
        for ax, ylabel in zip(axes, ('Target gas heat (1e12 erg/g)', 'Squared encoded difference', 'Energy difference (erg/g)')):
            ax.set(xlabel='Material half-column cell index (not height)', ylabel=ylabel); ax.legend()
        fig.suptitle('Identical material; observed radiation-history differences')
        fig.savefig(out/'history_comparison.png', dpi=150); plt.close(fig)
        pipeline.write_json(out/'status.json', {'status': 'complete', 'new_maps': 0})
    except BaseException as exc:
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)}); raise


if __name__ == '__main__': main()
