"""Independent, backed-up replay of completed small-step feedback pairs.

The source runs may still be running. Snapshot one atomic state read and only
inspect rounds already declared complete there. Never read rotating .dat slots.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from operations.prepare_encoded_backtrack import load_arrays
from operations.conservative_residual_diagnostic import equation_residual, norms
from operations.replay_equation_baseline import pair_comparison
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec

BASE = 'outputs/phase7b9d_encoded_base_material_state.npy'
LEGACY = 'outputs/phase7b9f_base_material_residual.npy'
SOURCES = (
    'outputs/hpc/hhe-r025-ext16-20260917',
    'outputs/hpc/hhe-r003125-confirm-20260917',
    'outputs/hpc/small-step-a15625-cont24-20260918',
    'outputs/hpc/small-step-a078125-cont24-20260918',
    'outputs/hpc/small-step-a00390625-cont24-20260918',
)


def trial_identity(trial, base, legacy, declared_alpha, reference_direction=None):
    """A config label is not a candidate: verify the actual encoded experiment."""
    fields = ('encoded_state', 'base_encoded_state', 'finite_direction', 'base_residual')
    shape = np.asarray(base).shape
    if any(np.asarray(trial[k]).shape != shape or not np.all(np.isfinite(trial[k])) for k in fields):
        raise ValueError('nonfinite or malformed candidate vector')
    alpha = float(trial['relaxation'])
    if not np.isfinite(alpha) or alpha <= 0 or alpha != declared_alpha:
        raise ValueError('trial alpha disagrees with declared experiment')
    if not np.array_equal(trial['base_encoded_state'], base) or not np.array_equal(trial['base_residual'], legacy):
        raise ValueError('candidate uses a different baseline')
    if not np.array_equal(trial['encoded_state'], base+alpha*trial['finite_direction']):
        raise ValueError('candidate does not equal base + alpha * direction')
    if reference_direction is not None and not np.array_equal(trial['finite_direction'], reference_direction):
        raise ValueError('direction differs between candidates')
    return alpha


def classify_pair(radiation, gates, failed_cells):
    """Observed domain failures are not proofs about all steps or an exact root."""
    finite = len(radiation) == 2 and all(x is not None and np.isfinite(x) and x >= 0 for x in radiation)
    inner = finite and all(x < 2.5e-4 for x in radiation)
    feedback = all(gates.get(k) is True for k in (
        'two_formal_feedback_states_pass', 'last_two_photoionization_pass',
        'last_two_total_recombination_pass', 'last_two_atomic_heating_pass',
        'last_two_direct_heating_pass', 'last_two_formal_heating_pass',
        'two_boundary_spectra_pass', 'two_boundary_bolometric_pass'))
    return {'both_radiation_endpoints_below_relaxed_gate': bool(inner),
            'feedback_and_boundary_gates_pass': feedback,
            'response_domain_failure_observed': any(n > 0 for n in failed_cells),
            'interpretation': 'finite-accuracy observation; no universal direction verdict',
            'formal_acceptance': bool(inner and feedback and all(v is True for v in gates.values()) and not any(failed_cells)),
            'exact_inner_error_bound_available': False}


def vector_secant_check(coarse, fine, coarse_h, fine_h):
    """Compare vectors, not their lengths; equal lengths can point oppositely."""
    a, b = np.asarray(coarse, dtype=float), np.asarray(fine, dtype=float)
    if a.shape != b.shape or not all(np.all(np.isfinite(x)) for x in (a,b)):
        raise ValueError('invalid finite-difference vectors')
    if not (np.isfinite(coarse_h) and coarse_h > 0 and fine_h == coarse_h/2):
        raise ValueError('expected a positive halving pair')
    a, b = a/coarse_h, b/fine_h
    scale = max(float(np.linalg.norm(a)), float(np.linalg.norm(b)))
    return {'relative_vector_difference': float(np.linalg.norm(a-b))/scale if scale > 0 else None,
            'establishes_derivative_by_itself': False}


def decoded_field_audit(trial, decoded):
    """Native RT consumes T/H/He; old migrate_trial retained archived energy."""
    fields={}
    for key in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        a,b=np.asarray(trial[key]),np.asarray(getattr(decoded,key))
        if a.shape!=b.shape or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
            raise ValueError('invalid stored material field')
        fields[key]={'array_equal':bool(np.array_equal(a,b)),
                     'maximum_absolute_difference':float(np.max(abs(a-b))),
                     'maximum_decoded_magnitude':float(np.max(abs(b)))}
    fields['native_input_identity_pass']=all(fields[k]['array_equal'] for k in (
        'temperature_k','hydrogen_fraction','helium_fraction'))
    fields['energy_note']='Archived energy metadata is reported separately; native RT reads T/H/He, and this equation diagnostic uses decoded total energy.'
    return fields


class Snapshot:
    def __init__(self, output):
        self.output = output
        self.records = {}

    def save(self, relative, expected=None):
        """Copy exact bytes once; mismatch aborts, no old evidence overwritten."""
        path = pipeline.safe_path(ROOT, str(relative))
        if path.suffix == '.dat':
            raise ValueError('rotating large states are excluded from this audit')
        if str(relative) in self.records:
            row = self.records[str(relative)]
            if expected and row['sha256'] != expected:
                raise RuntimeError('conflicting expected source hash')
            return self.output/'inputs'/relative
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected and digest != expected:
            raise RuntimeError(f'input SHA mismatch: {relative}')
        dest = self.output/'inputs'/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(data)
        self.records[str(relative)] = {'path': str(relative), 'size_bytes': len(data), 'sha256': digest}
        pipeline.write_json(self.output/'snapshot-manifest.json', list(self.records.values()))
        return dest

    def read(self, relative, expected=None):
        return pipeline.read(self.save(relative, expected))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True)
    args = p.parse_args()
    pipeline.require_allocation(1)
    out = pipeline.safe_path(ROOT, args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):
        raise ValueError('new output must be under outputs/hpc')
    out.mkdir(parents=True, exist_ok=False)
    snap = Snapshot(out)
    pipeline.write_json(out/'status.json', {'status': 'running'})
    result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'environment': pipeline.environment(), 'runs': [], 'new_maps': 0, 'new_directions': 0}
    try:
        receipt = snap.read('handoff/evidence/ustc-baseline-input-package-20260917.json')
        prefix = receipt['package_prefix']
        for item in receipt['files']:
            snap.save(prefix+'/'+item['path'], item['sha256'])
        package = out/'inputs'/prefix
        proto = pipeline.read(package/'outputs/phase7b9f_preregistered_converged_feedback_residual.json')
        bs = pipeline.read(package/'outputs/phase7b9f_converged_feedback_residual_summary.json')
        if pipeline.sha256(package/'outputs/phase7b9f_preregistered_converged_feedback_residual.json') != bs['protocol_sha256']:
            raise RuntimeError('archived baseline protocol mismatch')
        for k in ('radiation_matter_feedback','material_newton_krylov'):
            item = proto['sources'][k];snap.save(item['path'],item['sha256'])
        for path in (Path(__file__), ROOT/'operations/conservative_residual_diagnostic.py',
                     ROOT/'operations/replay_equation_baseline.py', ROOT/'diagnostics/material_energy_ledger.py'):
            snap.save(str(path.relative_to(ROOT)))
        old = load_arrays(snap.save(OLD_TIME_LEVEL, proto['sources']['physical_old_time_level']['sha256']))
        base = np.load(package/BASE, allow_pickle=False)
        legacy = np.load(package/LEGACY, allow_pickle=False)
        material = load_arrays(package/proto['sources']['current_material_state']['path'])
        phase = int(material['phase_index']); dt = float(material['step_duration_s']);rho = material['density_g_cm3']
        if dt != float(old['step_duration_s'][phase]) or not np.array_equal(rho, old['density_g_cm3'][phase]):
            raise RuntimeError('baseline physical time mismatch')
        masses = old['cell_mass_g_cm2'];codec = GroundStateLogSimplexCodec(len(rho))
        def evaluate(encoded, feedback):
            book = ledger(feedback,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            vector = equation_residual(codec,encoded,book['total_old'],book['gas_old'],book['radiative_energy'],book['new_h'],book['new_he'])
            return vector, book
        base_pair={}; base_domain={}
        for label in ('previous','final'):
            item=bs[label+'_feedback'];path=package/item['feedback_artifact_path']
            if pipeline.sha256(path)!=item['feedback_artifact_sha256']:
                raise RuntimeError('baseline feedback hash mismatch')
            base_pair[label], book=evaluate(base,load_arrays(path))
            base_domain[label]={'failed_cells':int(np.count_nonzero(book['remaining']<=0)),
                                'minimum_remaining_over_oldgas':float(np.min(book['remaining_relative_to_old_gas_heat']))}
        result['baseline']={'domain':base_domain,'norms':{k:norms(v,masses) for k,v in base_pair.items()},
                            'adjacent_drift':norms(base_pair['final']-base_pair['previous'],masses)}
        reference_direction=None
        for name in SOURCES:
            state = snap.read(name+'/state.json')
            cfg = snap.read(name+'/config.json',state['config_sha256'])
            trial_path=snap.save(name+'/trial_material.npz',state['trial_sha256'])
            trial=load_arrays(trial_path)
            # 最早的0.0625配置没有alpha字段，实际trial仍必须核验并报告该缺失。
            alpha=trial_identity(trial,base,legacy,float(cfg.get('candidate_relaxation',0.0625)),reference_direction)
            reference_direction=trial['finite_direction']
            decoded=codec.decode(trial['encoded_state'])
            fields=decoded_field_audit(trial,decoded)
            pipeline.write_json(out/f'decode-{len(result["runs"])+1}.json',fields)
            if not fields['native_input_identity_pass']:
                raise RuntimeError('native candidate fields differ from their encoded decode')
            if int(trial['phase_index'])!=phase or float(trial['step_duration_s'])!=dt or not np.array_equal(trial['density_g_cm3'],rho):
                raise RuntimeError('candidate physical time mismatch')
            dependency_failures=[];excluded=[]
            for claim in cfg['sources']:
                if claim['path'].endswith('.dat'):
                    excluded.append(claim);continue
                try:snap.save(claim['path'],claim['sha256'])
                except RuntimeError as exc:dependency_failures.append(str(exc))
            if dependency_failures:raise RuntimeError(str(dependency_failures))
            if cfg.get('extension_of'):
                source_trial=load_arrays(snap.save(cfg['extension_of']+'/trial_material.npz'))
                for key in ('encoded_state','base_encoded_state','finite_direction','base_residual','relaxation'):
                    if not np.array_equal(trial[key],source_trial[key]):raise RuntimeError('extension switched candidate')
            hist=state['history'];rounds=state.get('diagnostic',{}).get('rounds',[])
            entry={'run':name,'captured_status':state['status'],'maps':len(hist),'alpha':alpha,
                   'trial_identity_pass':True,'decoded_fields':fields,'rounds':[],'skipped_large_dependency_hashes':excluded,
                   'recent_radiation_residuals':[h['residual'] for h in hist[-9:]],
                   'recent_contractions':[hist[i]['residual']/hist[i-1]['residual'] for i in range(max(1,len(hist)-8),len(hist))]}
            result['runs'].append(entry)
            by_iteration={h['iteration']:h for h in hist}
            for rr in rounds[-2:]:
                folder=str(Path(rr['ledger']).parent)
                fs=snap.read(folder+'/feedback_summary.json')
                snap.save(folder+'/feedback_protocol.json',rr['protocol_sha256'])
                book=snap.read(rr['ledger'])
                if fs['protocol_sha256']!=rr['protocol_sha256'] or book['inputs']['trial_material']['sha256']!=pipeline.sha256(trial_path):
                    raise RuntimeError('feedback/ledger candidate lineage mismatch')
                if book['inputs']['old_time_level']['sha256']!=proto['sources']['physical_old_time_level']['sha256']:
                    raise RuntimeError('ledger old-time identity mismatch')
                pair={};failures=[];domain={}
                for label in ('previous','final'):
                    manifest=snap.read(folder+'/feedback/'+label+'_manifest.json')
                    if manifest['status']!='complete' or manifest['protocol_sha256']!=rr['protocol_sha256'] or manifest['state_sha256']!=rr['endpoints_claim'][label]['sha256']:
                        raise RuntimeError('feedback radiation endpoint lineage mismatch')
                    item=fs[label+'_feedback']
                    feedback=load_arrays(snap.save(item['feedback_artifact_path'],item['feedback_artifact_sha256']))
                    pair[label],led=evaluate(trial['encoded_state'],feedback)
                    n=int(np.count_nonzero(led['remaining']<=0));failures.append(n)
                    if n!=book['endpoints'][label]['failing_cells']:raise RuntimeError('domain count replay mismatch')
                    ratio=led['remaining_relative_to_old_gas_heat'];worst=int(np.argmin(ratio))
                    domain[label]={'failed_cells':n,'minimum_remaining_over_oldgas':float(ratio[worst]),'worst_cell':worst,
                                   'ledger_ratio_replay_difference':float(ratio[worst]-book['endpoints'][label]['relative_worst']['ratio'])}
                radiation=[by_iteration[i]['residual'] for i in rr['endpoints']]
                row={'round':rr['round'],'radiation_residuals':radiation,'domain':domain,'gates':fs['gate_checks'],
                     'heating':fs['comparison']['atomic_heating_volume_l1'],
                     'assessment':classify_pair(radiation,fs['gate_checks'],failures),
                     'same_scale_equation_comparison':pair_comparison((base_pair['previous'],base_pair['final']), (pair['previous'],pair['final']),masses)}
                vector_path=out/f'vectors-{len(result["runs"])}-{rr["round"]}.npz'
                np.savez(vector_path,base_previous=base_pair['previous'],base_final=base_pair['final'],previous=pair['previous'],final=pair['final'])
                row['vectors']={'path':str(vector_path.relative_to(ROOT)),'sha256':pipeline.sha256(vector_path)}
                entry['rounds'].append(row)
                pipeline.write_json(out/'review.partial.json',result)
        result['limitations']=['Finite snapshots cannot prove all smaller steps fail.',
            'Local floating-point perturbations do not bound radiation-solve error.',
            'Historical baseline radiation accuracy is not refreshed by feedback replay.',
            'Current rotating .dat states and block partial files were not reread or copied.',
            'The new energy residual is diagnostic; no replacement of formal acceptance.']
        result['snapshot_manifest']=pipeline.claim(out/'snapshot-manifest.json')
        pipeline.write_json(out/'review.json',result)
        pipeline.write_json(out/'status.json',{'status':'complete','runs':len(result['runs'])})
    except Exception as exc:
        pipeline.write_json(out/'review.partial.json',result)
        pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)})
        raise


if __name__=='__main__':
    main()
