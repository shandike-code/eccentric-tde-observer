"""Replay the completed paired control; diagnose directions without accepting one."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src'), str(ROOT/'scripts'), str(ROOT/'hpc')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_half_step_after_audit import REQUIRED_GATES
from operations.audit_outer_contraction import decomposition
from operations.composite_hybrid_batch import archive
from diagnostics.material_energy_ledger import ledger
from scripts import phase7b9_formal_feedback_pair_adapter as pair
from eccentric_tde_observer.formal_feedback_pair import encoded_residual_norms
from eccentric_tde_observer.coupled_material_newton_krylov import (
    GroundStateLogSimplexCodec, ground_state_material_trial_within_trust_region)

SOURCE = 'outputs/hpc/constrained-hybrid-20260921'


def direction_geometry(base_residual, trial_residual, direction, mass, alpha):
    b, c, d = [np.asarray(x, dtype=float).reshape(-1, 4) for x in
               (base_residual, trial_residual, direction)]
    m = np.asarray(mass, dtype=float)
    if (b.shape != c.shape or b.shape != d.shape or m.shape != (len(b),)
            or not all(np.isfinite(x).all() for x in (b, c, d, m))
            or np.any(m <= 0) or not np.isfinite(alpha) or alpha <= 0):
        raise ValueError('invalid direction diagnostic')
    if np.linalg.norm(b) == 0 or np.linalg.norm(d) == 0:
        raise ValueError('zero direction or residual has no angle')
    delta = c-b
    cross = float(2*np.sum(b*delta))
    cross_mass = float(2*np.sum(m[:, None]*b*delta)/m.sum())
    return {'old_direction_vs_current_response_cosine': float(np.sum(b*d)/(np.linalg.norm(b)*np.linalg.norm(d))),
            'old_direction_l2': float(np.linalg.norm(d)), 'current_response_l2': float(np.linalg.norm(b)),
            'finite_secant_l2_squared_slope': cross/alpha,
            'finite_secant_mass_squared_slope': cross_mass/alpha,
            'secant_model_positive_step_can_decrease_l2': cross < 0,
            'secant_model_positive_step_can_decrease_mass': cross_mass < 0,
            'limitation': 'Signs describe the measured endpoint secant, not the exact coupled Jacobian.'}


def response_trial_table(base, response):
    """Screen exact decoded Picard directions; no radiation or acceptance claim."""
    codec = GroundStateLogSimplexCodec(len(base)//4)
    rows = []
    # A bounded preregistered screening grid, not fitted to an acceptance verdict.
    for alpha in (1/16, 1/32, 1/64, 1/128, 1/256, 1/512):
        encoded = base+alpha*response
        value = codec.decode(encoded)
        trust = ground_state_material_trial_within_trust_region(codec, base, encoded,
            maximum_relative_temperature_change=.5,
            maximum_absolute_material_energy_increment_fraction=.25,
            maximum_population_fraction_change=.05)
        rows.append({'alpha': alpha, 'trust_pass': bool(trust),
            'maximum_encoded_displacement': float(np.max(abs(alpha*response))),
            'minimum_temperature_k': float(value.temperature_k.min()),
            'minimum_material_energy_erg_g': float(value.specific_material_energy_erg_g.min()),
            'minimum_h_population': float(value.hydrogen_fraction.min()),
            'minimum_he_population': float(value.helium_fraction.min()),
            'coupled_response_evaluated': False})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--run', required=True); args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run); out.relative_to(ROOT/'outputs/hpc'); out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out); pipeline.write_json(out/'status.json', {'status': 'running'})
    try:
        for name in ('operations/audit_constrained_feedback.py', 'operations/audit_constrained_feedback.sbatch',
                     'operations/audit_outer_contraction.py', 'diagnostics/material_energy_ledger.py',
                     'scripts/phase7b9_formal_feedback_pair_adapter.py'):
            snap.save(name)
        status = snap.read(SOURCE+'/status.json')
        if status['status'] != 'complete' or status['completed_maps'] != 7 or status['completed_pairs'] != 2:
            raise RuntimeError('source batch incomplete')
        source_c = snap.read(SOURCE+'/C-result.json')
        vectors = {}; trials = {}; info = {}; mass = None; physical_claim = None
        for label in ('base', 'trial'):
            run = SOURCE+'/B-'+label; rd = run+'/feedback-round1'
            state = snap.read(run+'/state.json')
            if state.get('active_map') or state.get('pending_feedback') or len(state['history']) != 2:
                raise RuntimeError('source child unsettled')
            cfg = snap.read(run+'/config.json', state['config_sha256'])
            trials[label] = load_arrays(snap.save(run+'/trial_material.npz', state['trial_sha256']))
            audit_native_trial(cfg, trials[label])
            record = snap.read(rd+'/round_summary.json')
            proto = snap.read(rd+('/baseline_control_protocol.json' if label=='base' else '/feedback_protocol.json'), record['protocol_sha256'])
            for c in proto['sources'].values():
                if not c['path'].endswith('.dat'): snap.save(c['path'], c['sha256'])
            claim = proto['sources']['physical_old_time_level']
            if physical_claim is not None and claim != physical_claim: raise RuntimeError('physical time level differs')
            physical_claim = claim
            old = load_arrays(ROOT/claim['path']); t = trials[label]; phase = int(t['phase_index'])
            vectors[label] = {}; info[label] = {}
            for e, row in zip(('previous','final'), state['history']):
                manifest = snap.read(rd+'/feedback/'+e+'_manifest.json')
                radiation = proto['sources'][e+'_radiation']
                if (manifest['status'] != 'complete' or not manifest['state_gate_passed']
                    or manifest['protocol_sha256'] != record['protocol_sha256']
                    or manifest['state_path'] != radiation['path'] or manifest['state_sha256'] != radiation['sha256']
                    or row['input_path'] != radiation['path'] or row['input_sha256'] != radiation['sha256']
                    or sorted(b['block_index'] for b in manifest['completed_blocks']) != list(range(76))):
                    raise RuntimeError('feedback lineage or frequency ownership changed')
                for block in manifest['completed_blocks']: snap.save(block['partial_path'], block['partial_sha256'])
                fb = load_arrays(snap.save(manifest['feedback_artifact_path'], manifest['feedback_artifact_sha256']))
                response, residual, context = pair._material_response_residual(proto, fb)
                if mass is not None and not np.array_equal(mass, context['cell_mass']): raise RuntimeError('mass measure differs')
                mass = context['cell_mass']
                book = ledger(fb,t['density_g_cm3'],float(t['step_duration_s']),old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
                if not all(np.isfinite(v).all() for v in book.values()) or not np.all(book['remaining'] > 0):
                    raise RuntimeError('invalid material response')
                for got,want in ((book['target'],response.target_specific_material_energy_erg_g),(book['new_h'],response.hydrogen_fraction),(book['new_he'],response.helium_fraction)):
                    if not np.allclose(got,want,rtol=1e-12,atol=0): raise RuntimeError('ledger disagreement')
                norms = asdict(encoded_residual_norms(residual,mass))
                if norms != source_c[label][e]['norms']: raise RuntimeError('same-platform response norms changed')
                vectors[label][e] = residual; np.save(out/(label+'-'+e+'-residual.npy'),residual,allow_pickle=False)
                info[label][e] = {'norms':norms,'minimum_gas_heat_erg_g':float(book['remaining'].min()),'feedback_sha256':manifest['feedback_artifact_sha256']}
                if label=='trial' and e=='final':
                    summary=snap.read(rd+'/feedback_summary.json')
                    stored=np.load(snap.save(summary['encoded_residual_path'],summary['encoded_residual_sha256']),allow_pickle=False)
                    if not np.array_equal(stored,residual): raise RuntimeError('stored decision residual replay differs')
        base, trial = trials['base'],trials['trial']
        if float(base['relaxation']) != 0 or not np.array_equal(base['encoded_state'],trial['base_encoded_state']): raise RuntimeError('wrong zero control')
        for key in ('base_encoded_state','base_residual','finite_direction','density_g_cm3','phase_index','step_duration_s'):
            if not np.array_equal(base[key],trial[key]): raise RuntimeError('material lineage differs: '+key)
        if set(summary['gate_checks']) != REQUIRED_GATES: raise RuntimeError('unexpected gate inventory')
        result={'environment':pipeline.environment(),'pairs':info,'gate_checks':summary['gate_checks'],
            'comparisons':{e:decomposition(vectors['base'][e],vectors['trial'][e],mass) for e in ('previous','final')},
            'direction_geometry':{e:direction_geometry(vectors['base'][e],vectors['trial'][e],trial['finite_direction'],mass,float(trial['relaxation'])) for e in ('previous','final')},
            'response_direction_screen':{e:response_trial_table(base['encoded_state'],vectors['base'][e]) for e in ('previous','final')},
            'new_maps':0,'new_feedback_pairs':0,'accepted_material_step':False,'formal_verdict_changed':False,
            'limitations':['No true inner error bound.','Response direction is a Picard proposal, not a proved descent direction.','A new direction needs full radiation and feedback validation.']}
        pipeline.write_json(out/'audit.json',result)
        pipeline.write_json(out/'status.json',{'status':'complete','new_maps':0,'new_feedback_pairs':0})
        archive(out,'complete')
    except BaseException as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':repr(exc)}); raise


if __name__ == '__main__': main()
