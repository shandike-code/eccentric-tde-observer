"""Audit an equation residual without inverting a nonphysical response temperature.

This is not a replacement acceptance protocol or a new material solve.
"""
import argparse
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from operations.prepare_encoded_backtrack import load_arrays
from operations.response_energy_audit import RUNS
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def equation_residual(codec, encoded, old_energy, gas_scale, radiative_increment, response_h, response_he):
    """Return fixed-scale energy defect plus population log-ratio defects."""
    state=codec.decode(encoded)
    n=len(state.temperature_k)
    old,scale,increment=(np.asarray(a,dtype=float) for a in (old_energy,gas_scale,radiative_increment))
    if any(a.shape!=(n,) or not np.all(np.isfinite(a)) for a in (old,scale,increment)) or np.any(scale<=0):
        raise ValueError('invalid fixed energy scale or energy arrays')
    # 候选始终在正热能/simplex域；只借用同一 codec 计算布居 log-ratio。
    # 此处候选温度不是响应温度，encode 的热能坐标完全丢弃。
    population_image=codec.encode(state.temperature_k,response_h,response_he).reshape(n,4)
    result=np.asarray(encoded).reshape(n,4).copy()-population_image
    # 原总能量方程，不改变dt/能量；旧气体热能是固定量，不随候选调参。
    result[:,0]=(state.specific_material_energy_erg_g-old-increment)/scale
    if not np.all(np.isfinite(result)):raise ArithmeticError('nonfinite equation residual')
    return result


def norms(values, masses):
    cell=np.linalg.norm(values,axis=1)
    weights=np.asarray(masses)/np.sum(masses)
    return {'l2':float(np.linalg.norm(values)),
            'mass_weighted_l2':float(np.sqrt(np.sum(weights*cell**2))),
            'maximum_cell':float(np.max(cell)), 'worst_cell':int(np.argmax(cell)),
            'maximum_energy_component':float(np.max(np.abs(values[:,0]))),
            'maximum_population_logratio_component':float(np.max(np.abs(values[:,1:])))}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);a=p.parse_args()
    pipeline.require_allocation(1)
    out=pipeline.safe_path(ROOT,a.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):raise RuntimeError('outside outputs/hpc')
    out.mkdir(parents=True,exist_ok=False)
    pipeline.write_json(out/'status.json',{'status':'running'})
    try:
      oldpath=ROOT/OLD_TIME_LEVEL;old=load_arrays(oldpath)
      result={'classification':'equation residual diagnostic only; not an accepted step or root existence proof',
       'definition':'energy=(e_candidate-e_old-dt*Q/rho)/old_gas_heat; population=logratios(candidate)-logratios(BE response)',
       'formal_acceptance_changed':False,'physical_dt_changed':False,
       'norms_comparable_to_legacy_encoded_residual':False,
       'environment':pipeline.environment(),'sources':[pipeline.claim(oldpath),pipeline.claim(Path(__file__)),
       pipeline.claim(ROOT/'diagnostics/material_energy_ledger.py')], 'runs':[]}
      for name in RUNS:
        run=ROOT/name;s=pipeline.read(run/'state.json');cfg=pipeline.read(run/'config.json')
        if s['status']!='diagnostic_round_complete' or s.get('active_map') or s.get('pending_feedback'):
            raise RuntimeError('source is not stopped')
        if pipeline.sha256(run/'config.json')!=s['config_sha256'] or pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True):
            raise RuntimeError('source config/dependencies changed')
        last=s['diagnostic']['rounds'][-1];folder=(ROOT/last['ledger']).parent
        summary=pipeline.read(folder/'feedback_summary.json');book=pipeline.read(folder/'material_energy_ledger.json')
        if pipeline.sha256(folder/'feedback_protocol.json')!=last['protocol_sha256'] or summary['protocol_sha256']!=last['protocol_sha256']:
            raise RuntimeError('formal pair lineage changed')
        trial=load_arrays(run/'trial_material.npz');phase=int(trial['phase_index']);dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
        if (pipeline.sha256(run/'trial_material.npz')!=book['inputs']['trial_material']['sha256']
            or pipeline.sha256(oldpath)!=book['inputs']['old_time_level']['sha256']
            or dt!=float(old['step_duration_s'][phase]) or not np.array_equal(rho,old['density_g_cm3'][phase])):
            raise RuntimeError('trial or physical time level changed')
        result['sources'].extend(pipeline.claim(x) for x in [run/'state.json',run/'trial_material.npz',folder/'feedback_summary.json'])
        codec=GroundStateLogSimplexCodec(len(rho));pair={};entry={'source_run':name,'alpha':float(trial['relaxation']),'endpoints':{}}
        for label in ('previous','final'):
            path=folder/f'{label}_feedback.npz'
            if pipeline.sha256(path)!=summary[f'{label}_feedback']['feedback_artifact_sha256']:
                raise RuntimeError('feedback changed')
            result['sources'].append(pipeline.claim(path));f=load_arrays(path)
            led=ledger(f,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            vector=equation_residual(codec,trial['encoded_state'],led['total_old'],led['gas_old'],led['radiative_energy'],led['new_h'],led['new_he'])
            pair[label]=vector
            entry['endpoints'][label]={'norms':norms(vector,old['cell_mass_g_cm2']),
                'legacy_response_nonphysical_cells':int(np.count_nonzero(led['remaining']<=0)),
                'residual_by_cell':vector.tolist()}
        entry['adjacent_residual_difference']=norms(pair['final']-pair['previous'],old['cell_mass_g_cm2'])
        result['runs'].append(entry)
      pipeline.write_json(out/'equation_residual.json',result)
      pipeline.write_json(out/'status.json',{'status':'complete','runs':len(result['runs'])})
    except Exception as exc:
      pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
