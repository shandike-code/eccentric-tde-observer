"""Two-map, zero-material-displacement control from the original base radiation.

This is a baseline/implementation check, never a nonlinear line-search step.
Feedback is evaluated through the existing state evaluator without run_pair's
material-acceptance decision. No supervisor submits additional jobs for this run.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.review_small_step_evidence import Snapshot
from operations.conservative_residual_diagnostic import equation_residual, norms
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from scripts import phase7b9_formal_feedback_pair_adapter as pair

PREFIX='outputs/baseline-audit-inputs-20260917'
SEED='outputs/checkpoints/baseline-recheck-20260918/state_b.dat'
SOURCE='outputs/hpc/hhe-r025-ext16-20260917'
MAXIMUM_MAPS=2
WORKERS=2


def zero_trial(source, base, baseline_residual):
    """Set only the declared material displacement to zero, with exact identity."""
    # 零位移保持同一个物理旧时间层，只撤去非线性候选的物质位移。
    if not np.array_equal(source['base_encoded_state'],base) or not np.array_equal(source['base_residual'],baseline_residual):
        raise ValueError('source uses a different archived baseline')
    if not np.array_equal(source['encoded_state'],base+float(source['relaxation'])*source['finite_direction']):
        raise ValueError('source direction identity is broken')
    codec=GroundStateLogSimplexCodec(len(source['temperature_k']))
    decoded=codec.decode(base)
    trial={k:np.array(v,copy=True) for k,v in source.items()}
    for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        trial[k]=np.array(getattr(decoded,k),copy=True)
    trial.update(encoded_state=np.array(base,copy=True),relaxation=np.array(0.0))
    for k in ('base_encoded_state','finite_direction','base_residual'):
        if not np.array_equal(trial[k],source[k]):raise RuntimeError('zero-control identity changed')
    if not np.array_equal(trial['encoded_state'],trial['base_encoded_state']+float(trial['relaxation'])*trial['finite_direction']):
        raise RuntimeError('zero displacement identity failed')
    return trial


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True);args=parser.parse_args()
    pipeline.require_allocation(WORKERS)
    out=pipeline.safe_path(ROOT,args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):raise ValueError('new output must be under outputs/hpc')
    out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out)
    pipeline.write_json(out/'control_status.json',{'status':'preparing'})
    try:
        receipt=snap.read('handoff/evidence/ustc-baseline-input-package-20260917.json')
        for row in receipt['files']:snap.save(PREFIX+'/'+row['path'],row['sha256'])
        package=out/'inputs'/PREFIX
        protocol=pipeline.read(package/'outputs/phase7b9f_preregistered_converged_feedback_residual.json')
        expected=protocol['sources']['final_radiation']
        seed=pipeline.claim(ROOT/SEED)
        if seed['size_bytes']!=expected['size_bytes'] or seed['sha256']!=expected['sha256']:
            raise RuntimeError('transferred baseline radiation differs from frozen protocol')
        source_state=snap.read(SOURCE+'/state.json')
        if source_state['status'] not in {'diagnostic_round_complete','budget_exhausted'} or source_state.get('active_map') or source_state.get('pending_feedback'):
            raise RuntimeError('template source must be stopped and settled')
        config=deepcopy(snap.read(SOURCE+'/config.json',source_state['config_sha256']))
        source=load_arrays(snap.save(SOURCE+'/trial_material.npz',source_state['trial_sha256']))
        for row in config['sources']:
            if row['path'].endswith('.dat'):continue
            snap.save(row['path'],row['sha256'])
        base=np.load(package/'outputs/phase7b9d_encoded_base_material_state.npy',allow_pickle=False)
        legacy=np.load(package/'outputs/phase7b9f_base_material_residual.npy',allow_pickle=False)
        trial=zero_trial(source,base,legacy)
        oldpath=snap.save(OLD_TIME_LEVEL,protocol['sources']['physical_old_time_level']['sha256']);old=load_arrays(oldpath)
        phase=int(trial['phase_index']);dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
        if dt!=float(old['step_duration_s'][phase]) or not np.array_equal(rho,old['density_g_cm3'][phase]):
            raise RuntimeError('old physical time level changed')
        np.savez(out/'trial_material.npz',**trial)
        reread=load_arrays(out/'trial_material.npz')
        for k in ('encoded_state','base_encoded_state','finite_direction','base_residual','relaxation'):
            if not np.array_equal(reread[k],trial[k]):raise RuntimeError('written zero-trial identity mismatch')
        archived=load_arrays(package/protocol['sources']['current_material_state']['path'])
        decode_changes={}
        for k in ('temperature_k','hydrogen_fraction','helium_fraction'):
            scale=float(np.max(abs(archived[k])))
            change=float(np.max(abs(trial[k]-archived[k])))/scale
            decode_changes[k]=change
            if change>2e-12:raise RuntimeError('baseline physical decode differs beyond migration allowance')
        config.update(run=args.run,workers=WORKERS,maximum_maps=MAXIMUM_MAPS,seed='warm',warm_seed=seed,
                      candidate_relaxation=0.0,radiation_threshold=1e-4,
                      physics_scope='zero material displacement; baseline control only',
                      seed_provenance='original archived 7B9f final radiation; SHA verified inside Slurm')
        config['sources']=list(config['sources'])+[pipeline.claim(out/'trial_material.npz'),pipeline.claim(Path(__file__)),pipeline.claim(Path(__file__).with_suffix('.sbatch'))]
        declaration={'scope':'zero-step baseline check; never material acceptance','maximum_new_maps':2,'workers':2,
                     'original_radiation_claim':expected,'transferred_seed':seed,'decode_relative_changes':decode_changes,
                     'trial':pipeline.claim(out/'trial_material.npz'),'physical_dt_changed':False,
                     'baseline_error_bound_established':False,'radiation_seed_is_archived_endpoint':True,
                     'environment':pipeline.environment(),
                     'pre_run_check':{'code':'exact base/direction/zero-trial identity and native input checks',
                                      'logic':'archived I and archived matter, two native maps, two state feedbacks, original feedback comparison',
                                      'physics':'same dt, grid, density and microphysics; no claim of accepted matter or full disc'}}
        pipeline.write_json(out/'control_declaration.json',declaration)
        config['sources'].append(pipeline.claim(out/'control_declaration.json'))
        pipeline.write_json(out/'native_trial_audit.json',audit_native_trial(config,trial))
        pipeline.write_json(out/'config.json',config)
        pipeline.write_json(out/'state.json',{'config_sha256':pipeline.sha256(out/'config.json'),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[args.run+f'/state_{i}.dat' for i in range(3)],'current_slot':0,'active_map':None})
        pipeline.write_json(out/'control_status.json',{'status':'mapping','maximum_new_maps':2})
        pipeline.run_pipeline(out,MAXIMUM_MAPS,do_feedback=False)
        state=pipeline.read(out/'state.json')
        if len(state['history'])!=2 or state.get('active_map') or state['status'] not in {'radiation','feedback_ready'}:
            raise RuntimeError('bounded maps incomplete or resource gate failed; preserve state for inspection')
        if state['history'][0]['input_sha256']!=expected['sha256']:
            raise RuntimeError('first map did not use the archived baseline radiation')
        path=pipeline.feedback_protocol(config,state)
        fp=pipeline.read(path)
        fp['phase']='zero-displacement baseline feedback audit'
        fp['authorization'].update(accept_material_step=False,zero_displacement_control=True)
        pipeline.write_json(path,fp)
        digest=pipeline.sha256(path)
        loaded=pair.load_frozen_pair_protocol(path,digest,validate_sources=True)
        pair._validate_worker_template_sources(loaded)
        pipeline.write_json(out/'control_status.json',{'status':'feedback','new_maps':2})
        summary=pipeline.read(package/'outputs/phase7b9f_converged_feedback_residual_summary.json')
        original=load_arrays(package/summary['final_feedback']['feedback_artifact_path'])
        result={'scope':'baseline control only','accepted_material_step':False,'history':state['history'],
                'physical_dt_s':dt,'feedback_protocol':pipeline.claim(path),'endpoints':{}}
        codec=GroundStateLogSimplexCodec(len(rho))
        for label in ('previous','final'):
            # 两次反馈分别消费历史 I 和一次映射后的 I；不能据此接受物质步。
            manifest=pair._run_feedback_state(loaded,path,digest,label)
            if manifest['status']!='complete' or not manifest['state_gate_passed']:
                raise RuntimeError('formal state diagnostic failed')
            feedback=pair._feedback_arrays(manifest)
            book=ledger(feedback,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            residual=equation_residual(codec,base,book['total_old'],book['gas_old'],book['radiative_energy'],book['new_h'],book['new_he'])
            original_book=ledger(original,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            original_residual=equation_residual(codec,base,original_book['total_old'],original_book['gas_old'],original_book['radiative_energy'],original_book['new_h'],original_book['new_he'])
            result['endpoints'][label]={'feedback_sha256':manifest['feedback_artifact_sha256'],
                'failed_cells':int(np.count_nonzero(book['remaining']<=0)),
                'minimum_remaining_over_oldgas':float(np.min(book['remaining_relative_to_old_gas_heat'])),
                'equation_norms':norms(residual,old['cell_mass_g_cm2']),
                'equation_difference_from_archive':norms(residual-original_residual,old['cell_mass_g_cm2']),
                'feedback_comparison_to_archive':pair._feedback_stability_comparison(original,feedback),
                'equation_by_cell':residual.tolist()}
            pipeline.write_json(out/'control_result.partial.json',result)
        result['limitations']=['Two further maps do not establish a true inner error bound.',
            'Previous endpoint replays the original radiation field with Linux decoded base material.',
            'Final endpoint changes only the radiation iterate at identical encoded matter.',
            'No line search, physical timestep change, or material-acceptance decision was executed.']
        pipeline.write_json(out/'control_result.json',result)
        pipeline.write_json(out/'control_status.json',{'status':'complete','new_maps':2,'accepted_material_step':False})
        state['status']='baseline_control_complete';pipeline.write_json(out/'state.json',state)
    except Exception as exc:
        pipeline.write_json(out/'control_status.json',{'status':'failed','error':str(exc)})
        raise


if __name__=='__main__':main()
