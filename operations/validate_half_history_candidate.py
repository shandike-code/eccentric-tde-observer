"""One original-operator map of the audited half-step history mixture."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import shutil
import signal
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_extension_run import carry_trial
from operations.prepare_encoded_backtrack import load_arrays,audit_native_trial
from operations.radiation_history_diagnostic import identical_material
from operations.half_history_basis import last_actual_map
from operations.validate_cross_history_candidate import write_candidate,full_field_error,validation_checks

SCAN='outputs/hpc/half-history-scan-20260920'
SOURCES=('outputs/hpc/half-step-base-seeded-20260920','outputs/hpc/half-step-precision-20260920')
EXPECTED_CHECKS={'resolved_direction','nonzero_coefficient','bounded_coefficients','nonnegative_prediction',
                 'maximum_norm_improves_best_history','boundary_spectrum_pass','boundary_bolometric_pass'}
CODE=('operations/validate_half_history_candidate.py','operations/validate_half_history_candidate.sbatch',
      'operations/validate_cross_history_candidate.py','operations/half_history_basis.py',
      'operations/radiation_history_diagnostic.py','operations/material_direction_diagnostic.py',
      'operations/scan_cross_history_direction.py','operations/prepare_extension_run.py',
      'operations/prepare_encoded_backtrack.py','operations/review_small_step_evidence.py',
      'scripts/phase7b9bx_slow_mode_anderson.py')


def verify_scan(prediction,declaration,basis):
    """Require the full declared guard set, not truthiness of a partial dictionary."""
    if (prediction['algebraic_feasibility'] is not True or set(prediction['checks'])!=EXPECTED_CHECKS
        or any(v is not True for v in prediction['checks'].values())):
        raise ValueError('scan checks incomplete or failed')
    if (declaration['basis']!=basis or declaration['source_order']!=list(SOURCES)
        or declaration['new_maps']!=0 or declaration['candidate_write_budget']!=0
        or declaration['coefficient_l1_cap']!=32. or declaration['physical_dt_changed'] is not False
        or prediction['actual_map_performed'] is not False or prediction['candidate_written'] is not False):
        raise ValueError('scan scope or basis differs')
    d=prediction['direction'];p=prediction['prediction'];g=float(d['gamma'])
    lo,hi=d['feasible_interval']
    if (not np.isfinite([g,lo,hi]).all() or not lo<=g<=hi or g==0
        or not np.array_equal(np.asarray(d['coefficients']),[1+g,-g])
        or d['coefficient_l1']!=abs(1+g)+abs(g) or d['coefficient_l1']>32.):
        raise ValueError('invalid affine coefficient')
    vals=[p['predicted_residual'],p['predicted_boundary_l1'],p['predicted_boundary_bolometric'],prediction['best_measured_residual']]
    if (not np.isfinite(vals).all() or min(vals)<0 or vals[-1]<=0
        or not vals[0]<.99*vals[-1] or not vals[1]<1e-3 or not vals[2]<1e-3
        or p['candidate_negative_count']!=0 or p['predicted_map_negative_count']!=0
        or p['minimum_candidate']<0 or p['minimum_predicted_map']<0
        or not d['direction_resolution_ratio']>1e-12):
        raise ValueError('scan numerical guards disagree with pass flags')
    return g


def initialized_identity(state,seed,trial,actual):
    """No map may start before verifying that initialization preserved the experiment."""
    identical_material(trial,actual)
    if (state['status']!='radiation' or state['history'] or state.get('active_map')
        or state.get('pending_feedback') or state['current_slot']!=0
        or state['current_sha256']!=seed['sha256']):
        raise RuntimeError('initialization changed seed or inherited history')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);args=p.parse_args()
    pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    signal.signal(signal.SIGUSR1,pipeline.signal_stop)
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'validation_status.json',{'status':'preparing','new_maps':0})
    try:
        for path in CODE:snap.save(path)
        if snap.read(SCAN+'/status.json')['status']!='complete':raise RuntimeError('scan incomplete')
        prediction=snap.read(SCAN+'/prediction.json');declaration=snap.read(SCAN+'/declaration.json')
        records={r['path']:r for r in snap.read(SCAN+'/snapshot-manifest.json')}
        configs=[];trials=[];basis=[]
        for source in SOURCES:
            state=snap.read(source+'/state.json',records[source+'/state.json']['sha256'])
            basis.extend(last_actual_map(state))
            cfg=snap.read(source+'/config.json',state['config_sha256']);configs.append(cfg)
            trial=load_arrays(snap.save(source+'/trial_material.npz',state['trial_sha256']));trials.append(trial)
            if pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True):raise RuntimeError('source dependency changed')
            for c in cfg['sources']:
                if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
            audit_native_trial(cfg,trial)
        identical_material(*trials);trial=trials[0];cfg=deepcopy(configs[0])
        fraction=verify_scan(prediction,declaration,basis)
        for c in basis:
            if (ROOT/c['path']).stat().st_size!=pipeline.STATE_BYTES or pipeline.sha256(ROOT/c['path'])!=c['sha256']:
                raise RuntimeError('large basis changed')
        if shutil.disk_usage(out).free<4*pipeline.STATE_BYTES+8*1024**3:raise RuntimeError('insufficient candidate/slots space')
        plan={'environment':pipeline.environment(),'basis':basis,'fraction':fraction,'prediction':prediction,
              'scan':SCAN,'maximum_new_maps':1,'maximum_candidate_writes':1,'workers':16,
              'formula':'candidate=XB+gamma*(XB-XO); prediction=YB+gamma*(YB-YO)',
              'full_field_prediction_error_fraction_of_actual_defect_limit':.01,
              'physical_dt_changed':False,'material_changed':False,'candidate_clipping':False,
              'code':[pipeline.claim(ROOT/x) for x in CODE]}
        pipeline.write_json(out/'validation_declaration.json',plan)
        if pipeline.STOP:
            pipeline.write_json(out/'validation_status.json',{'status':'incomplete','stage':'before_candidate','new_maps':0});return
        candidate=out/'half_history_candidate.dat'
        minimum=write_candidate([ROOT/basis[i]['path'] for i in (0,2)],candidate,fraction,
                                int(np.prod(pipeline.SHAPE)),16*pipeline.SHAPE[1]*pipeline.SHAPE[2])
        for c in basis:
            if pipeline.sha256(ROOT/c['path'])!=c['sha256']:raise RuntimeError('basis changed during writing')
        # 中文：物质trial先落盘、逐字段校验，再初始化；禁止默认迁移静默换成0.0625候选。
        copied=carry_trial(ROOT/SOURCES[0],out);identical_material(trial,load_arrays(out/'trial_material.npz'))
        seed=pipeline.claim(candidate)
        cfg.update(run=args.run,workers=16,maximum_maps=1,radiation_threshold=1e-4,seed='warm',warm_seed=seed,
                   extension_of=SOURCES[0],extension_purpose='one actual map validating the fixed-material half-history mixture')
        cfg['sources']=list(cfg['sources'])+[copied['source'],copied['destination'],seed,
            pipeline.claim(out/'validation_declaration.json'),pipeline.claim(ROOT/SOURCES[1]/'trial_material.npz')]+[
            pipeline.claim(ROOT/name) for name in CODE]+[pipeline.claim(ROOT/SCAN/name) for name in ('prediction.json','declaration.json')]
        pipeline.write_json(out/'config.json',cfg)
        pipeline.write_json(out/'native_trial_audit.json',audit_native_trial(cfg,trial))
        pipeline.write_json(out/'state.json',{'config_sha256':pipeline.sha256(out/'config.json'),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[args.run+f'/state_{i}.dat' for i in range(3)],
            'current_slot':0,'active_map':None})
        pipeline.run_pipeline(out,0,False)
        initialized_identity(pipeline.read(out/'state.json'),seed,trial,load_arrays(out/'trial_material.npz'))
        pipeline.write_json(out/'post_initialization_native_audit.json',audit_native_trial(cfg,trial))
        if pipeline.STOP:
            pipeline.write_json(out/'validation_status.json',{'status':'incomplete','stage':'initialized','new_maps':0});return
        pipeline.write_json(out/'validation_status.json',{'status':'mapping','new_maps':0})
        pipeline.run_pipeline(out,1,False)
        mapped=pipeline.read(out/'state.json')
        identical_material(trial,load_arrays(out/'trial_material.npz'))
        if mapped['status']=='resource_gate_failed':raise RuntimeError('map resource gate failed')
        if mapped.get('active_map') or len(mapped['history'])!=1:
            pipeline.write_json(out/'validation_status.json',{'status':'incomplete','stage':'mapping','new_maps':len(mapped['history'])});return
        row=mapped['history'][0]
        if row['input_sha256']!=seed['sha256']:raise RuntimeError('map used different candidate')
        pipeline.write_json(out/'validation_status.json',{'status':'checking_full_field','new_maps':1})
        with np.load(snap.save(pipeline.MASTER),allow_pickle=False) as z:edges=z['active_edge_hz'].copy()
        error=full_field_error([candidate,ROOT/row['output_path'],ROOT/basis[1]['path'],ROOT/basis[3]['path']],
                               pipeline.SHAPE,fraction,edges)
        checks=validation_checks(row,prediction['best_measured_residual'])
        checks['full_field_prediction_error_resolved']=error['prediction_error_resolved']
        for c in basis:
            if pipeline.sha256(ROOT/c['path'])!=c['sha256']:raise RuntimeError('basis changed during validation')
        result={'candidate':seed,'candidate_minimum_intensity':minimum,'actual_map':row,
                'predicted_residual':prediction['prediction']['predicted_residual'],
                'actual_minus_predicted_residual':row['residual']-prediction['prediction']['predicted_residual'],
                'validation_checks':checks,'extrapolation_validated':all(checks.values()),
                'full_field_error':error,'full_intensity_prediction_error_evaluated':True,
                'accepted_material_step':False,'feedback_evaluated':False,
                'note':'One actual map verifies this mixture only, not a global affinity theorem, feedback stability or coupled convergence.'}
        pipeline.write_json(out/'validation_result.json',result)
        pipeline.write_json(out/'validation_status.json',{'status':'complete','new_maps':1,
            'extrapolation_validated':all(checks.values()),'accepted_material_step':False})
    except BaseException as exc:
        pipeline.write_json(out/'validation_status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
