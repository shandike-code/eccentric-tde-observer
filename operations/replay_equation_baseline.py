"""Replay archived baseline and stopped candidates with one fixed equation scale.

Read-only diagnostic. Adjacent endpoint drift is not an error bound or a new gate.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from operations.prepare_encoded_backtrack import load_arrays
from operations.conservative_residual_diagnostic import equation_residual, norms
from operations.recover_equation_baseline import recover_equation_residual
from operations.debug_baseline_parity import (
    array_difference, parity_verdict, scale_aware_verdict)
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from eccentric_tde_observer.radiation_matter_feedback import frozen_radiation_material_response
import phase7b9cy_refresh_feedback_worker_template as migration

PROTOCOL = 'outputs/phase7b9f_preregistered_converged_feedback_residual.json'
SUMMARY = 'outputs/phase7b9f_converged_feedback_residual_summary.json'
BASE_MANIFEST = 'outputs/checkpoints/phase7b9f_base_residual_manifest.json'
RECEIPT = 'handoff/evidence/ustc-baseline-input-package-20260917.json'
SOURCE_RUNS = (
    'outputs/hpc/hhe-r025-cont64',
    'outputs/hpc/scale32-cont-20260917/science',
    'outputs/hpc/hhe-r003125-confirm-20260917',
)
METRICS = ('l2', 'mass_weighted_l2', 'maximum_cell')


def pair_comparison(base_pair, trial_pair, masses):
    """Same-metric ratios; zero signal produces null, never an invented floor."""
    arrays = [np.asarray(x, dtype=float) for x in (*base_pair, *trial_pair)]
    if (any(x.ndim != 2 or x.shape != arrays[0].shape or x.shape[1] != 4 for x in arrays)
            or not all(np.all(np.isfinite(x)) for x in arrays)):
        raise ValueError('invalid residual pairs')
    m = np.asarray(masses, dtype=float)
    if m.shape != arrays[0].shape[:1] or not np.all(np.isfinite(m)) or np.any(m <= 0):
        raise ValueError('invalid fixed mass measure')
    bp, bf, tp, tf = arrays
    nb, nt = norms(bf, m), norms(tf, m)
    bd, td = norms(bf-bp, m), norms(tf-tp, m)
    signal = norms(tf-bf, m)
    # 这是已观测相邻漂移/候选差值，不是内层误差界；两端漂移之和也不补成严格界。
    ratio = lambda a, b: float(a/b) if b > 0 else None
    return {'baseline_final': nb, 'candidate_final': nt,
            'baseline_adjacent_drift': bd, 'candidate_adjacent_drift': td,
            'candidate_minus_baseline': signal,
            'ratios': {k: {
                'candidate_over_baseline': ratio(nt[k], nb[k]),
                'baseline_drift_over_difference': ratio(bd[k], signal[k]),
                'candidate_drift_over_difference': ratio(td[k], signal[k]),
                'sum_observed_drifts_over_difference': ratio(bd[k]+td[k], signal[k]),
            } for k in METRICS},
            'true_inner_error_bound_available': False,
            'formal_acceptance_evaluated': False}


def check_physical_identity(trial, old, phase, dt, rho):
    if (int(trial['phase_index']) != phase or float(trial['step_duration_s']) != dt
            or dt != float(old['step_duration_s'][phase])
            or not np.array_equal(trial['density_g_cm3'], rho)
            or not np.array_equal(rho, old['density_g_cm3'][phase])):
        raise RuntimeError('physical time level/density changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    pipeline.require_allocation(1)  # 一个分析进程，申请4CPU并不代表4个重型worker。
    out = pipeline.safe_path(ROOT, args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):
        raise ValueError('output must be a new HPC directory')
    out.mkdir(parents=True, exist_ok=False)
    pipeline.write_json(out/'status.json', {'status': 'running'})
    claims = {}
    def pin(path, expected=None):
        path = Path(path)
        rel = path.relative_to(ROOT) if path.is_absolute() else path
        p = pipeline.safe_path(ROOT, str(rel))
        item = pipeline.claim(p)
        if expected is not None and item['sha256'] != expected:
            raise RuntimeError(f'artifact identity changed: {rel}')
        if item['path'] in claims and item != claims[item['path']]:
            raise RuntimeError('input changed during replay')
        claims[item['path']] = item
        return p
    try:
        receipt = pipeline.read(pin(RECEIPT))
        package = pipeline.safe_path(ROOT, receipt['package_prefix'])
        manifest_path = pin(package/'MANIFEST.json', receipt['manifest_sha256'])
        package_manifest = pipeline.read(manifest_path)
        if package_manifest['files'] != receipt['files']:
            raise RuntimeError('package inventory changed')
        for item in receipt['files']:
            p = pin(package/item['path'], item['sha256'])
            if p.stat().st_size != item['size_bytes']:
                raise RuntimeError('package size mismatch')
        proto = pipeline.read(package/PROTOCOL)
        summary = pipeline.read(package/SUMMARY)
        if pipeline.sha256(package/PROTOCOL) != summary['protocol_sha256']:
            raise RuntimeError('baseline protocol lineage mismatch')
        migrated = None
        for name, item in proto['sources'].items():
            if item['path'].endswith('.dat'):
                continue  # 已归档反馈重放，不重算辐射；原dat身份仅保留为历史来源。
            if item['path'].startswith('outputs/'):
                pin(package/item['path'], item['sha256'])
            elif name != 'mixed_frame_frequency':
                pin(item['path'], item['sha256'])
            else:
                current = pin(item['path'])
                audit = pipeline.read(package/migration.AUDIT_PATH)
                pin(current, audit['current_frequency']['sha256'])
                legacy = migration.reconstruct_legacy_frequency_source(current.read_text())
                if migration.sha256_bytes(legacy.encode()) != item['sha256']:
                    raise RuntimeError('legacy frequency source cannot be reconstructed')
                parity = migration.positive_feedback_path_parity(legacy)
                references = migration.signed_api_references()
                if not all(x['array_equal'] for x in parity.values()) or any(references.values()):
                    raise RuntimeError('positive transfer path migration parity failed')
                migrated = {'legacy_sha256': item['sha256'], 'current_sha256': pipeline.sha256(current),
                            'exact_legacy_reconstruction': True, 'synthetic_positive_path_parity': parity,
                            'limitation': 'small parity control, not a fresh full-column radiation solve'}
        for path in [Path(__file__), Path(__file__).with_suffix('.sbatch'),
                     ROOT/'operations/recover_equation_baseline.py', ROOT/'operations/conservative_residual_diagnostic.py',
                     ROOT/'diagnostics/material_energy_ledger.py', ROOT/'scripts/phase7b9cy_refresh_feedback_worker_template.py']:
            pin(path)
        base_manifest = pipeline.read(package/BASE_MANIFEST)
        if base_manifest['status'] != 'complete':
            raise RuntimeError('baseline manifest is incomplete')
        for section, expected in [('feedback', summary['final_feedback']['feedback_artifact_sha256']),
                                  ('material_residual', summary['encoded_residual_sha256'])]:
            if base_manifest[section]['artifact']['sha256'] != expected:
                raise RuntimeError('baseline manifest disagrees with summary')
        oldpath = package/proto['sources']['physical_old_time_level']['path']
        old = load_arrays(oldpath)
        pin(OLD_TIME_LEVEL, pipeline.sha256(oldpath))
        base = load_arrays(package/proto['sources']['current_material_state']['path'])
        encoded = np.load(package/proto['sources']['encoded_material_state']['path'], allow_pickle=False)
        phase, dt = int(base['phase_index']), float(base['step_duration_s'])
        rho = base['density_g_cm3']; masses = old['cell_mass_g_cm2']
        check_physical_identity(base, old, phase, dt, rho)
        codec = GroundStateLogSimplexCodec(len(rho))
        recoded = codec.encode(base['temperature_k'], base['hydrogen_fraction'], base['helium_fraction'])
        if not np.allclose(recoded, encoded, rtol=0, atol=3e-13):
            raise RuntimeError('baseline encoding parity failed')
        def evaluate(vector, feedback):
            led = ledger(feedback, rho, dt, old['temperature_k'][phase], old['hydrogen_fraction'][phase], old['helium_fraction'][phase])
            residual = equation_residual(codec, vector, led['total_old'], led['gas_old'], led['radiative_energy'], led['new_h'], led['new_he'])
            return residual, led
        baseline, endpoints = {}, {}
        for label in ('previous', 'final'):
            claim = summary[f'{label}_feedback']
            f = load_arrays(pin(package/claim['feedback_artifact_path'], claim['feedback_artifact_sha256']))
            vector, led = evaluate(encoded, f)
            if np.any(led['remaining'] <= 0):
                raise RuntimeError('archived baseline unexpectedly leaves response domain')
            response = frozen_radiation_material_response(rho, old['temperature_k'][phase], old['hydrogen_fraction'][phase],
                old['helium_fraction'][phase], dt, f['half_photoionization_s1'], f['half_total_recombination_cm3_s'], f['half_atomic_rate_heating_erg_s_cm3'])
            legacy = codec.encode(response.temperature_k, response.hydrogen_fraction, response.helium_fraction)-encoded
            baseline[label] = vector
            endpoints[label] = {'norms': norms(vector, masses), 'legacy_l2': float(np.linalg.norm(legacy)),
                                'nonphysical_response_cells': 0, 'residual_by_cell': vector.tolist()}
            if label == 'final':
                stored = np.load(pin(package/summary['encoded_residual_path'], summary['encoded_residual_sha256']), allow_pickle=False)
                target = load_arrays(pin(package/summary['target_material_path'], summary['target_material_sha256']))
                # 入口判据锚定在残差自身尺度：1-ulp 布居差经 log 变换约成 1e-12，
                # 逐元素绝对界无法区分舍入与真实差异。严格逐位结果仍完整记录。
                difference = array_difference(legacy, stored)
                strict = parity_verdict(legacy, stored)
                replay_verdict = scale_aware_verdict(legacy, stored)
                if not replay_verdict['passed']:
                    raise RuntimeError('legacy response replay parity failed')
                if not np.allclose(encoded+stored, target['encoded_state'], rtol=0, atol=3e-13):
                    raise RuntimeError('stored target and residual disagree')
                recovered = recover_equation_residual(codec, encoded, stored, led['gas_old'])
                # 代数恒等式同样按尺度判定：Mac 上余量只有 2.6 倍，跨平台不应要求逐位。
                identity = scale_aware_verdict(recovered, vector)
                if not identity['passed']:
                    raise RuntimeError('converted baseline disagrees with direct energy equation')
                parity = {
                    'replay_verdict': replay_verdict,
                    'strict_element_wise_verdict': strict,
                    'conversion_identity_verdict': identity,
                    'difference': {k: v for k, v in difference.items() if k != 'difference_by_cell'},
                    'conversion_identity_maximum_absolute_difference': float(np.max(abs(recovered-vector))),
                    'note': '跨平台重放用尺度锚定判据；严格逐位判据只记录，不冒充物理接受条件。'}
        result = {'classification': 'same-scale equation residual diagnostic; no accepted material step',
                  'environment': pipeline.environment(), 'migration': migrated, 'cross_platform_parity': parity,
                  'physical_phase': phase, 'physical_dt_s': dt,
                  'baseline': {'endpoints': endpoints, 'historical_inner_radiation': base_manifest['radiation'],
                               'historical_feedback_comparison': summary['comparison']}, 'candidates': [],
                  'scope': {'new_radiation_maps': 0, 'new_directions': 0, 'formal_gates_changed': False,
                            'baseline_error_bound_available': False, 'candidate_error_bound_available': False}}
        # 基态证据先单独落盘：后面任何一步失败都不能再丢掉已完成的部分。
        pipeline.write_json(out/'baseline_replay.partial.json', result)
        for name in SOURCE_RUNS:
            run = pipeline.safe_path(ROOT, name)
            state = pipeline.read(pin(run/'state.json'))
            if state['status'] != 'diagnostic_round_complete' or state.get('active_map') or state.get('pending_feedback'):
                raise RuntimeError('candidate source must be stopped and settled')
            cfg = pipeline.read(pin(run/'config.json', state['config_sha256']))
            if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True):
                raise RuntimeError('candidate frozen dependencies changed')
            trial_path = pin(run/'trial_material.npz'); trial = load_arrays(trial_path)
            check_physical_identity(trial, old, phase, dt, rho)
            if not np.array_equal(trial['base_encoded_state'], encoded) or not np.array_equal(trial['base_residual'], stored):
                raise RuntimeError('candidate uses a different baseline')
            if not np.array_equal(trial['encoded_state'], encoded+float(trial['relaxation'])*trial['finite_direction']):
                raise RuntimeError('candidate is off the declared direction')
            entry = {'source_run': name, 'alpha': float(trial['relaxation']), 'rounds': []}
            # cont64只需末轮；确认run保留两轮，显式检查漂移是否随精度改善。
            rounds = state['diagnostic']['rounds'] if name == SOURCE_RUNS[-1] else state['diagnostic']['rounds'][-1:]
            for rr in rounds:
                folder = (ROOT/rr['ledger']).parent
                pin(folder/'feedback_protocol.json', rr['protocol_sha256'])
                fs = pipeline.read(pin(folder/'feedback_summary.json'))
                book = pipeline.read(pin(folder/'material_energy_ledger.json'))
                if (fs['protocol_sha256'] != rr['protocol_sha256']
                    or book['inputs']['trial_material']['sha256'] != pipeline.sha256(trial_path)
                    or book['inputs']['old_time_level']['sha256'] != pipeline.sha256(oldpath)):
                    raise RuntimeError('candidate feedback lineage mismatch')
                pair, cells = {}, {}
                for label in ('previous', 'final'):
                    f = load_arrays(pin(folder/f'{label}_feedback.npz', fs[f'{label}_feedback']['feedback_artifact_sha256']))
                    pair[label], led = evaluate(trial['encoded_state'], f)
                    cells[label] = int(np.count_nonzero(led['remaining'] <= 0))
                    if cells[label] != book['endpoints'][label]['failing_cells']:
                        raise RuntimeError('response domain replay mismatch')
                row = pair_comparison((baseline['previous'], baseline['final']), (pair['previous'], pair['final']), masses)
                row.update(round_folder=str(folder.relative_to(ROOT)), nonphysical_response_cells=cells,
                           heating_pair_change=fs['comparison']['atomic_heating_volume_l1'],
                           residual_by_cell={k:v.tolist() for k,v in pair.items()})
                entry['rounds'].append(row)
            result['candidates'].append(entry)
            pipeline.write_json(out/'baseline_replay.partial.json', result)
        # 已停止源在本次只读重放期间也不得改变；记录所有小工件和实际执行代码身份。
        if pipeline.verify_claims(ROOT, list(claims.values()), hash_files=True):
            raise RuntimeError('input changed during replay')
        result['sources'] = list(claims.values())
        pipeline.write_json(out/'baseline_comparison.json', result)
        pipeline.write_json(out/'status.json', {'status': 'complete', 'candidate_runs': len(result['candidates'])})
    except Exception as exc:
        # 失败也保留已经完成的部分结果，失败原因单独记录，不覆盖证据。
        for partial in (out/'baseline_replay.partial.json',):
            if partial.exists():
                pipeline.write_json(out/'baseline_replay.failed.json',
                                    {**pipeline.read(partial), 'failure': str(exc)})
        pipeline.write_json(out/'status.json', {'status': 'failed', 'error': str(exc)})
        raise


if __name__ == '__main__':
    main()
