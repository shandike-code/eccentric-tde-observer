"""Complete only missing final feedback in a new directory; keep timeout run immutable."""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from scripts import phase7b9_formal_feedback_pair_adapter as pair
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays
from operations.cpu_long_common_seed_control import common_seed_trial, ALPHA, PREFIX
from operations.conservative_residual_diagnostic import equation_residual, norms
from diagnostics.material_energy_ledger import ledger, OLD_TIME_LEVEL
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec

SOURCE='outputs/hpc/common-seed-a0078125-long-20260919'
WORKERS=2
OUTPUT_KEYS=('feedback_work_directory','summary_path','figure_path','target_material_output',
             'encoded_residual_output','previous_feedback_output','final_feedback_output')


def recovery_protocol(original, run):
    """Declare only execution/output differences; every scientific field stays exact."""
    result=deepcopy(original)
    cfg=result['configuration']
    for key in OUTPUT_KEYS:
        cfg[key]=str(Path(run)/Path(cfg[key]).name)
    cfg['maximum_concurrent_processes']=WORKERS
    assert result['sources']==original['sources']
    assert result['formal_state_gates']==original['formal_state_gates']
    assert result['acceptance_gates']==original['acceptance_gates']
    return result


def verify_previous(manifest, protocol, digest):
    if (manifest.get('status')!='complete' or manifest.get('state_gate_passed') is not True
        or manifest.get('protocol_sha256')!=digest or manifest.get('state_label')!='previous'
        or manifest.get('state_sha256')!=protocol['sources']['previous_radiation']['sha256']
        or manifest.get('state_path')!=protocol['sources']['previous_radiation']['path']):
        raise RuntimeError('previous feedback is incomplete or has different lineage')
    rows=manifest['completed_blocks']
    if sorted(int(r['block_index']) for r in rows)!=list(range(protocol['configuration']['block_count'])):
        raise RuntimeError('previous feedback block ownership is incomplete')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True);args=parser.parse_args()
    pipeline.require_allocation(WORKERS)
    out=pipeline.safe_path(ROOT,args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):raise ValueError('output must be under outputs/hpc')
    out.mkdir(parents=True,exist_ok=False)
    pipeline.write_json(out/'control_status.json',{'status':'preparing','new_maps':0})
    snap=Snapshot(out)
    try:
        state=snap.read(SOURCE+'/state.json')
        cfg=snap.read(SOURCE+'/config.json',state['config_sha256'])
        if len(state['history'])!=2 or state.get('active_map'):
            raise RuntimeError('source maps incomplete')
        trial=load_arrays(snap.save(SOURCE+'/trial_material.npz',state['trial_sha256']))
        failures=pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True)
        if failures:raise RuntimeError(f'frozen source dependencies changed: {failures[:3]}')
        receipt=snap.read('handoff/evidence/ustc-baseline-input-package-20260917.json')
        for row in receipt['files']:snap.save(PREFIX+'/'+row['path'],row['sha256'])
        package=out/'inputs'/PREFIX
        base=np.load(package/'outputs/phase7b9d_encoded_base_material_state.npy',allow_pickle=False)
        legacy=np.load(package/'outputs/phase7b9f_base_material_residual.npy',allow_pickle=False)
        common_seed_trial(trial,base,legacy)
        path=ROOT/SOURCE/'feedback_protocol.json';digest=pipeline.sha256(path)
        snap.save(str(path.relative_to(ROOT)),digest)
        original=pair.load_frozen_pair_protocol(path,digest,validate_sources=True)
        pair._validate_worker_template_sources(original)
        for label,row in zip(('previous','final'),state['history'],strict=True):
            claim=original['sources'][label+'_radiation']
            if claim['path']!=row['input_path'] or claim['sha256']!=row['input_sha256']:
                raise RuntimeError('feedback endpoints differ from source maps')
        previous=snap.read(SOURCE+'/feedback/previous_manifest.json')
        verify_previous(previous,original,digest)
        interrupted_final=snap.read(SOURCE+'/feedback/final_manifest.json')
        if (interrupted_final.get('status')!='running' or interrupted_final.get('completed_blocks')
            or interrupted_final.get('protocol_sha256')!=digest
            or interrupted_final.get('state_sha256')!=original['sources']['final_radiation']['sha256']):
            raise RuntimeError('recovery declaration expects exactly zero committed final blocks')
        snap.save(previous['feedback_artifact_path'],previous['feedback_artifact_sha256'])
        for row in previous['completed_blocks']:snap.save(row['partial_path'],row['partial_sha256'])
        old=load_arrays(snap.save(OLD_TIME_LEVEL,original['sources']['physical_old_time_level']['sha256']))
        phase=int(trial['phase_index']);dt=float(trial['step_duration_s']);rho=trial['density_g_cm3']
        if dt!=float(old['step_duration_s'][phase]) or not np.array_equal(rho,old['density_g_cm3'][phase]):
            raise RuntimeError('physical old time level mismatch')
        fp=recovery_protocol(original,args.run);newpath=out/'feedback_protocol.json'
        pipeline.write_json(newpath,fp);newdigest=pipeline.sha256(newpath)
        pipeline.write_json(out/'recovery_declaration.json',{
            'environment':pipeline.environment(),'source_run':SOURCE,
            'old_protocol':pipeline.claim(path),'new_protocol':pipeline.claim(newpath),
            'code':[pipeline.claim(Path(__file__)),pipeline.claim(Path(__file__).with_suffix('.sbatch'))],
            'previous_manifest':pipeline.claim(ROOT/SOURCE/'feedback/previous_manifest.json'),
            'changes':['output paths','maximum_concurrent_processes: 16 to 2'],
            'previous_feedback_reused':True,'old_run_modified':False,'new_maps':0,
            'accepted_material_step':False,'physical_dt_changed':False,
            'timeout_backup_sha256':'61779f85852f60efccda2acfc47316727f5c0aff9a0f7b3c3d2de0d21d165a85',
            'uncommitted_final_blocks_reused':False,
            'resource_note':'Original final manifest committed zero blocks; recovery final wall gate covers this new evaluation, not all spent allocation time.'})
        loaded=pair.load_frozen_pair_protocol(newpath,newdigest,validate_sources=True)
        pipeline.write_json(out/'control_status.json',{'status':'feedback','new_maps':0,'reused_previous':True})
        # previous 已完成且字节不动；只执行原 final 输入上的欠缺反馈。
        final=pair._run_feedback_state(loaded,newpath,newdigest,'final')
        if final['status']!='complete' or not final['state_gate_passed']:
            raise RuntimeError('final feedback state gate failed')
        archive_summary=pipeline.read(package/'outputs/phase7b9f_converged_feedback_residual_summary.json')
        archived=load_arrays(package/archive_summary['final_feedback']['feedback_artifact_path'])
        codec=GroundStateLogSimplexCodec(len(rho))
        archived_book=ledger(archived,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
        archived_residual=equation_residual(codec,base,archived_book['total_old'],archived_book['gas_old'],archived_book['radiative_energy'],archived_book['new_h'],archived_book['new_he'])
        result={'scope':'common-seed candidate feedback recovery only','alpha':ALPHA,'source_run':SOURCE,
                'accepted_material_step':False,'history':state['history'],'new_maps':0,'physical_dt_s':dt,
                'feedback_protocols':{'previous':pipeline.claim(path),'final':pipeline.claim(newpath)},'endpoints':{}}
        arrays={}
        for label,manifest in (('previous',previous),('final',final)):
            feedback=pair._feedback_arrays(manifest);arrays[label]=feedback
            book=ledger(feedback,rho,dt,old['temperature_k'][phase],old['hydrogen_fraction'][phase],old['helium_fraction'][phase])
            residual=equation_residual(codec,trial['encoded_state'],book['total_old'],book['gas_old'],book['radiative_energy'],book['new_h'],book['new_he'])
            result['endpoints'][label]={'feedback_sha256':manifest['feedback_artifact_sha256'],
                'failed_cells':int(np.count_nonzero(book['remaining']<=0)),
                'minimum_remaining_over_oldgas':float(np.min(book['remaining_relative_to_old_gas_heat'])),
                'equation_norms':norms(residual,old['cell_mass_g_cm2']),
                'equation_difference_from_archive':norms(residual-archived_residual,old['cell_mass_g_cm2']),
                'feedback_comparison_to_archive':pair._feedback_stability_comparison(archived,feedback),
                'equation_by_cell':residual.tolist()}
        result['adjacent_feedback_comparison']=pair._feedback_stability_comparison(arrays['previous'],arrays['final'])
        result['limitations']=['Inputs are finite-accuracy candidate radiation states, not certified converged.',
                              'Reused previous and new final have identical scientific protocol fields, different execution paths and concurrency.',
                              'No material acceptance or model-existence verdict.']
        pipeline.write_json(out/'control_result.json',result)
        pipeline.write_json(out/'control_status.json',{'status':'complete','new_maps':0,'accepted_material_step':False})
    except Exception as exc:
        pipeline.write_json(out/'control_status.json',{'status':'failed','error':str(exc),'new_maps':0})
        raise


if __name__=='__main__':main()
