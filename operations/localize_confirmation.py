"""Read-only attribution of a stopped confirmation run; no solve or acceptance."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL, parent_layer_contributions, fold_to_material_layers
from operations.prepare_encoded_backtrack import load_arrays
from operations.conservative_residual_diagnostic import equation_residual, norms
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec

HEATING = 'atomic_rate_heating_erg_s_cm3'
ABSORBED = 'absorbed_power_erg_s_cm3'
EMITTED = 'emitted_power_erg_s_cm3'
SHAPE = (9632, 32, 4096)


def ownership(rows, groups=9632):
    owned = np.zeros(groups, dtype=int)
    ids = set()
    for row in rows:
        i, a, b = (int(row[k]) for k in ('block_index', 'core_group_start', 'core_group_stop'))
        if i in ids or not 0 <= a < b <= groups:
            raise ValueError('duplicate block or invalid range')
        ids.add(i); owned[a:b] += 1
    if not np.all(owned == 1):
        raise ValueError('frequency ownership has gaps or overlaps')


def attribution(previous, final, widths):
    """Exact signed attribution to the total-change L1; retain cancellation."""
    p, f, w = map(lambda x: np.asarray(x, dtype=float), (previous, final, widths))
    if p.ndim != 2 or p.shape != f.shape or w.shape != p.shape[1:] or np.any(w <= 0):
        raise ValueError('invalid block/depth/width shapes')
    if not all(np.all(np.isfinite(a)) for a in (p, f, w)):
        raise ValueError('nonfinite attribution input')
    # 先按块求和再求两态差，分母与正式体积L1相同。块贡献允许负值。
    total_p, total_f = p.sum(axis=0), f.sum(axis=0)
    delta = total_f - total_p
    denominator = float(np.sum(w * np.maximum(abs(total_p), abs(total_f))))
    if denominator <= 0:
        raise ValueError('zero heating scale; no normalized attribution')
    differences = f-p
    signed = np.sum(differences * (w*np.sign(delta))[None, :], axis=1) / denominator
    gross = np.sum(abs(differences) * w[None, :], axis=1) / denominator
    per_depth = w*abs(delta)/denominator
    numerator = float(np.sum(w*abs(delta)))
    return {'ratio': float(per_depth.sum()), 'denominator': denominator, 'numerator': numerator,
            'signed_blocks': signed, 'gross_blocks': gross, 'depth_contribution': per_depth,
            'signed_closure_error': float(abs(signed.sum()-per_depth.sum()))}


def rank(values, count=12):
    x = np.asarray(values)
    return [{'index': int(i), 'value': float(x[i])} for i in np.argsort(abs(x))[::-1][:count]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--source-run', required=True)
    args = parser.parse_args()
    pipeline.require_allocation(4)
    out = pipeline.safe_path(ROOT, args.run)
    source = pipeline.safe_path(ROOT, args.source_run)
    if not out.is_relative_to(ROOT/'outputs/hpc') or out == source:
        raise ValueError('output must be a separate HPC directory')
    out.mkdir(parents=True, exist_ok=False)
    pipeline.write_json(out/'status.json', {'status': 'running'})
    pipeline.write_json(out/'declaration.json', {'arguments': vars(args), 'sources': [pipeline.claim(Path(__file__)), pipeline.claim(Path(__file__).with_suffix('.sbatch'))], 'scope': 'read-only localization; fixed source; no continuation'})
    claims = {}
    def pin(path, expected=None):
        path = pipeline.safe_path(ROOT, str(path))
        item = pipeline.claim(path)
        if expected is not None and item['sha256'] != expected:
            raise RuntimeError(f'artifact changed: {path}')
        old = claims.get(item['path'])
        if old is not None and old != item:
            raise RuntimeError('source changed during audit')
        claims[item['path']] = item
        return path
    try:
        pin(source/'state.json'); state = pipeline.read(source/'state.json')
        if state['status'] != 'diagnostic_round_complete' or state.get('active_map') or state.get('pending_feedback'):
            raise RuntimeError('source is not fully stopped')
        pin(source/'config.json', state['config_sha256']); cfg = pipeline.read(source/'config.json')
        if tuple(cfg['shape']) != SHAPE:
            raise RuntimeError('unsupported radiation shape')
        if pipeline.verify_claims(ROOT, cfg['sources'], hash_files=True):
            raise RuntimeError('frozen source claims failed')
        for path in [Path(__file__), ROOT/'operations/conservative_residual_diagnostic.py', ROOT/'diagnostics/material_energy_ledger.py']:
            pin(path)
        result = {'classification': 'read-only localization; no new maps, direction or acceptance',
                  'environment': pipeline.environment(), 'source_run': str(source.relative_to(ROOT)),
                  'maps': [], 'rounds': []}
        all_rows = []
        for hist in state['history']:
            folder = source/f"map{hist['iteration']:04d}"
            paths = sorted(folder.glob('block*.json'))
            rows = [pipeline.read(pin(p)) for p in paths]
            ownership(rows)
            if [r['block_index'] for r in rows] != list(range(76)) or any(r['input_state_sha256'] != hist['input_sha256'] for r in rows):
                raise RuntimeError('map block lineage mismatch')
            if len({r['protocol_sha256'] for r in rows}) != 1:
                raise RuntimeError('map block protocols disagree')
            aggregate = pipeline.aggregate(rows, SHAPE[0])
            if not np.isclose(aggregate['residual'], hist['residual'], rtol=1e-13, atol=0):
                raise RuntimeError('map residual reproduction failed')
            scale = max(r['maximum_radiation_scale'] for r in rows)
            values = [r['maximum_absolute_radiation_change']/scale for r in rows]
            own = [r['block_relative_radiation_change'] for r in rows]
            result['maps'].append({'iteration': hist['iteration'], 'residual': hist['residual'],
                                  'global_scale': scale, 'global_rank': rank(values),
                                  'own_scale_rank': rank(own),
                                  'blocks': [{'index': r['block_index'], 'group_start': r['core_group_start'],
                                              'group_stop': r['core_group_stop'], 'global_relative': v,
                                              'own_relative': q} for r,v,q in zip(rows,values,own)]})
            all_rows.append(rows)
        # 只有最后一次映射的输入/输出仍应保留；对两份原始态校验哈希后定位峰值。
        last = state['history'][-1]
        paths = [pin(ROOT/last[f'{label}_path'], last[f'{label}_sha256']) for label in ('input','output')]
        if any(p.stat().st_size != np.prod(SHAPE)*8 for p in paths):
            raise RuntimeError('retained radiation shape mismatch')
        block = max(all_rows[-1], key=lambda r:r['maximum_absolute_radiation_change'])
        a,b = block['core_group_start'],block['core_group_stop']
        mapped = [np.memmap(p, dtype=np.float64, mode='r', shape=SHAPE) for p in paths]
        diff = np.asarray(mapped[1][a:b])-np.asarray(mapped[0][a:b])
        loc = np.unravel_index(np.argmax(abs(diff)), diff.shape)
        if not np.isclose(abs(diff[loc]), block['maximum_absolute_radiation_change'], rtol=1e-13, atol=0):
            raise RuntimeError('retained radiation does not reproduce block maximum')
        parent = int(loc[2])//16
        result['retained_last_map_peak'] = {'block': block['block_index'], 'frequency_index': int(loc[0]+a),
            'direction_index': int(loc[1]), 'radiation_depth_index': int(loc[2]), 'full_parent': parent,
            'half_material_cell': min(parent,255-parent), 'signed_change': float(diff[loc]),
            'input_intensity': float(mapped[0][loc[0]+a,loc[1],loc[2]]),
            'output_intensity': float(mapped[1][loc[0]+a,loc[1],loc[2]])}
        del diff, mapped
        old = load_arrays(pin(ROOT/OLD_TIME_LEVEL)); trial_path = pin(source/'trial_material.npz'); trial=load_arrays(trial_path)
        phase=int(trial['phase_index']);dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
        if dt != float(old['step_duration_s'][phase]) or not np.array_equal(rho,old['density_g_cm3'][phase]):
            raise RuntimeError('physical old time level mismatch')
        codec = GroundStateLogSimplexCodec(len(rho))
        for rr in state['diagnostic']['rounds']:
            folder=(ROOT/rr['ledger']).parent
            proto=pin(folder/'feedback_protocol.json',rr['protocol_sha256'])
            summary=pipeline.read(pin(folder/'feedback_summary.json'));book=pipeline.read(pin(folder/'material_energy_ledger.json'))
            if summary['protocol_sha256'] != rr['protocol_sha256']:
                raise RuntimeError('feedback summary lineage mismatch')
            if pipeline.sha256(trial_path) != book['inputs']['trial_material']['sha256'] or pipeline.sha256(ROOT/OLD_TIME_LEVEL) != book['inputs']['old_time_level']['sha256']:
                raise RuntimeError('ledger source mismatch')
            full, partial, vectors, ranges = {},{},{},{}
            for label in ('previous','final'):
                endpoint=rr['endpoints_claim'][label]
                manifest=pipeline.read(pin(folder/'feedback'/f'{label}_manifest.json'))
                if manifest['status'] != 'complete' or manifest['protocol_sha256'] != rr['protocol_sha256'] or manifest['state_sha256'] != endpoint['sha256']:
                    raise RuntimeError('partial manifest lineage mismatch')
                rows=manifest['completed_blocks'];ownership(rows)
                rows=sorted(rows,key=lambda r:r['block_index'])
                if [r['block_index'] for r in rows] != list(range(76)):
                    raise RuntimeError('feedback block IDs mismatch')
                ranges[label]=[(r['core_group_start'],r['core_group_stop']) for r in rows]
                full[label]=load_arrays(pin(folder/f'{label}_feedback.npz',summary[f'{label}_feedback']['feedback_artifact_sha256']))
                partial[label]={k:[] for k in (HEATING,ABSORBED,EMITTED)}
                for row in rows:
                    data=load_arrays(pin(ROOT/row['partial_path'],row['partial_sha256']))
                    for k in partial[label]:partial[label][k].append(data[k])
                for k in partial[label]:
                    partial[label][k]=np.array(partial[label][k])
                    if not np.allclose(partial[label][k].sum(axis=0),full[label][k],rtol=2e-13,atol=0):
                        raise RuntimeError(f'partial sum mismatch: {label}/{k}')
                led=ledger(full[label],rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
                vectors[label]=equation_residual(codec,trial['encoded_state'],led['total_old'],led['gas_old'],led['radiative_energy'],led['new_h'],led['new_he'])
            if ranges['previous'] != ranges['final']:raise RuntimeError('feedback pair frequency partition changed')
            widths=full['previous']['subcell_width_cm']
            if not np.array_equal(widths,full['final']['subcell_width_cm']):raise RuntimeError('feedback widths differ')
            att=attribution(partial['previous'][HEATING],partial['final'][HEATING],widths)
            if not np.isclose(att['ratio'],summary['comparison']['atomic_heating_volume_l1'],rtol=1e-10,atol=1e-14):
                raise RuntimeError('formal heating L1 not reproduced')
            if att['signed_closure_error'] > 1e-10*att['ratio']:
                raise RuntimeError('signed decomposition not closed')
            cells=fold_to_material_layers(parent_layer_contributions(att['depth_contribution']))
            entry={'round':rr['round'],'heating_ratio':att['ratio'],'numerator':att['numerator'],'denominator':att['denominator'],
                   'signed_closure_error':att['signed_closure_error'],'signed_block_rank':rank(att['signed_blocks']),
                   'gross_block_rank':rank(att['gross_blocks']), 'gross_over_net':float(att['gross_blocks'].sum()/att['ratio']),
                   'cell_rank':rank(cells), 'cell_contribution':cells.tolist(),
                   'signed_blocks':att['signed_blocks'].tolist(), 'gross_blocks':att['gross_blocks'].tolist(),
                   'emitted_change_max':float(np.max(abs(partial['final'][EMITTED]-partial['previous'][EMITTED]))),
                   'absorbed_change_max':float(np.max(abs(partial['final'][ABSORBED]-partial['previous'][ABSORBED]))),
                   'equation_norms':{k:norms(v,old['cell_mass_g_cm2']) for k,v in vectors.items()},
                   'equation_endpoint_difference':norms(vectors['final']-vectors['previous'],old['cell_mass_g_cm2'])}
            result['rounds'].append(entry)
        # 小工件必须在整个审计期间不变；大态已在读取前核验，停止态的state再次核验。
        for item in list(claims.values()):
            if not item['path'].endswith('.dat'):pin(ROOT/item['path'],item['sha256'])
        result['sources']=list(claims.values())
        pipeline.write_json(out/'localization.json',result)
        pipeline.write_json(out/'status.json',{'status':'complete','maps':len(result['maps']),'rounds':len(result['rounds'])})
    except Exception as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)});raise


if __name__ == '__main__':
    main()
