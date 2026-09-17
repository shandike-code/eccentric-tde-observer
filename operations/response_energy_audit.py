"""Read-only energy-equation diagnostic; never changes formal acceptance gates."""
import argparse
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from operations.prepare_encoded_backtrack import load_arrays

RUNS=('outputs/hpc/hhe-r025-cont64',
      'outputs/hpc/hhe-backtrack-r003125-20260916-v2',
      'outputs/hpc/scale32-cont-20260917/science')


def energy_defect(candidate_energy, old_energy, radiative_increment):
    """Conservation-equation defect exists even when a response temperature does not."""
    arrays=[np.asarray(x,dtype=float) for x in (candidate_energy,old_energy,radiative_increment)]
    if any(a.shape!=arrays[0].shape or not np.all(np.isfinite(a)) for a in arrays):
        raise ValueError('incompatible or nonfinite energy arrays')
    # 原总物质能量守恒方程的差值，不反解负目标能量的温度，不改能量定义。
    return arrays[0] - arrays[1] - arrays[2]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);args=p.parse_args()
    pipeline.require_allocation(1)
    out=pipeline.safe_path(ROOT,args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):raise RuntimeError('output outside outputs/hpc')
    out.mkdir(parents=True,exist_ok=False)
    old_path=ROOT/OLD_TIME_LEVEL;old=load_arrays(old_path)
    results=[];identities=[]
    report={'classification':'read-only energy-component audit; not full coupled residual or acceptance',
      'environment':pipeline.environment(),'sources':[pipeline.claim(Path(__file__)),pipeline.claim(old_path),
      pipeline.claim(ROOT/'diagnostics/material_energy_ledger.py')],
      'energy_defect_definition':'candidate_specific_material_energy - old_specific_material_energy - dt*Q/rho',
      'formal_acceptance_changed':False,'endpoints':results}
    pipeline.write_json(out/'status.json',{'status':'running'})
    try:
      for name in RUNS:
        run=ROOT/name;state=pipeline.read(run/'state.json');cfg=pipeline.read(run/'config.json')
        if state['status']!='diagnostic_round_complete' or state.get('active_map') or state.get('pending_feedback'):
            raise RuntimeError('source not stopped and settled')
        if pipeline.sha256(run/'config.json')!=state['config_sha256']:
            raise RuntimeError('source config changed')
        if pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True):
            raise RuntimeError('source dependencies changed')
        last=state['diagnostic']['rounds'][-1];folder=(ROOT/last['ledger']).parent
        summary=pipeline.read(folder/'feedback_summary.json');book=pipeline.read(folder/'material_energy_ledger.json')
        if pipeline.sha256(folder/'feedback_protocol.json')!=last['protocol_sha256'] or summary['protocol_sha256']!=last['protocol_sha256']:
            raise RuntimeError('formal protocol lineage changed')
        trial=load_arrays(run/'trial_material.npz');phase=int(trial['phase_index']);dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
        if (pipeline.sha256(run/'trial_material.npz')!=book['inputs']['trial_material']['sha256']
            or pipeline.sha256(old_path)!=book['inputs']['old_time_level']['sha256']
            or dt!=float(old['step_duration_s'][phase]) or not np.array_equal(rho,old['density_g_cm3'][phase])):
            raise RuntimeError('trial or physical old time level changed')
        identities.append((phase,dt))
        report['sources'].extend(pipeline.claim(x) for x in [run/'trial_material.npz',run/'state.json',folder/'feedback_summary.json',folder/'material_energy_ledger.json'])
        for label in ('previous','final'):
          path=folder/f'{label}_feedback.npz';claim=summary[f'{label}_feedback']
          if pipeline.sha256(path)!=claim['feedback_artifact_sha256']:
              raise RuntimeError('formal feedback bytes changed')
          feedback=load_arrays(path);report['sources'].append(pipeline.claim(path))
          led=ledger(feedback,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
          defect=energy_defect(trial['specific_material_energy_erg_g'],led['total_old'],led['radiative_energy'])
          worst=int(np.argmin(led['remaining_relative_to_old_gas_heat']))
          cells={key:led[key].tolist() for key in ['gas_old','ion_old','ion_new','radiative_energy','remaining','delta_ionization']}
          cells.update(candidate_temperature_k=trial['temperature_k'].tolist(),old_temperature_k=old['temperature_k'][phase].tolist(),
              candidate_energy_erg_g=trial['specific_material_energy_erg_g'].tolist(),energy_equation_defect_erg_g=defect.tolist())
          failed=int(np.count_nonzero(led['remaining']<=0))
          if failed!=book['endpoints'][label]['failing_cells']:
              raise RuntimeError('independent replay disagrees with recorded failure count')
          results.append({'source_run':name,'endpoint':label,'alpha':float(trial['relaxation']),
            'heating_pair_change':summary['comparison']['atomic_heating_volume_l1'],
            'inner_gate_passed':summary['gate_checks']['two_inner_radiation_residuals_pass'],
            'failing_cells':failed,'worst_cell':worst,
            'remaining_over_old_gas':float(led['remaining_relative_to_old_gas_heat'][worst]),
            'radiative_increment_over_old_gas':float(led['radiative_energy'][worst]/led['gas_old'][worst]),
            'delta_ionization_over_old_gas':float(led['delta_ionization'][worst]/led['gas_old'][worst]),
            'energy_equation_defect_over_old_gas':float(defect[worst]/led['gas_old'][worst]),
            'split_self_check':led['split_self_check'],'cells':cells})
      if len(set(identities))!=1:raise RuntimeError('different physical time levels cannot be directly compared')
      report['physical_phase_and_dt']=identities[0]
      report['interpretation_limits']=[
        'Frozen radiation response can leave its temperature domain while the algebraic energy defect is finite.',
        'A finite diagnostic defect neither accepts a material step nor proves the nonlinear equations have a physical root.',
        'Candidates have different radiation convergence histories; their difference is not a validated Jacobian.',
        'No dt reduction, clipping, floors, population changes, or replaced formal norm.']
      pipeline.write_json(out/'energy_audit.json',report)
      pipeline.write_json(out/'status.json',{'status':'complete','endpoints':len(results)})
    except Exception as exc:
      pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
