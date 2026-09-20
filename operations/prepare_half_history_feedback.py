"""Prepare a bounded feedback pair from the validated half-step mixture output."""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path
import sys
import os
import signal
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays,audit_native_trial
from operations.prepare_extension_run import carry_trial
from operations.radiation_history_diagnostic import identical_material
from operations.validate_half_history_candidate import initialized_identity
from operations.validate_cross_history_candidate import validation_checks

SOURCE = 'outputs/hpc/half-history-map-validation-20260920'
REFERENCE = 'outputs/hpc/half-step-base-seeded-20260920'
from operations.prepare_cross_feedback import validated_cross_seed


EXPECTED_VALIDATION = {'actual_maximum_norm_improves', 'actual_boundary_spectrum_pass',
                       'actual_boundary_bolometric_pass', 'worker_memory_pass',
                       'full_field_prediction_error_resolved'}


def validated_half_seed(state, status, result, declaration):
    seed = validated_cross_seed(state, status, result)
    if (set(result['validation_checks']) != EXPECTED_VALIDATION
        or declaration['maximum_new_maps'] != 1 or declaration['material_changed'] is not False
        or declaration['physical_dt_changed'] is not False
        or result['feedback_evaluated'] is not False or result['accepted_material_step'] is not False):
        raise ValueError('validation scope or explicit gate inventory differs')
    row = result['actual_map']
    values = [row[k] for k in ('residual','boundary_l1','boundary_bolometric','maximum_worker_rss_mib')]
    ratio = result['full_field_error']['error_over_actual_defect_l2']
    if (not np.isfinite(values).all() or min(values) < 0
        or ratio is None or not np.isfinite(ratio) or not 0 <= ratio < .01
        or declaration['full_field_prediction_error_fraction_of_actual_defect_limit'] != .01
        or not all(validation_checks(row, declaration['prediction']['best_measured_residual']).values())):
        raise ValueError('numeric validation guards failed')
    return seed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,choices=(16,),required=True)
    parser.add_argument('--run',required=True);args=parser.parse_args()
    pipeline.require_allocation(args.workers)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE') != '0':
        raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 must be set before Python starts')
    signal.signal(signal.SIGUSR1,pipeline.signal_stop)
    out=pipeline.safe_path(ROOT,args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):raise ValueError('output outside outputs/hpc')
    out.mkdir(parents=True,exist_ok=False);snap=Snapshot(out)
    pipeline.write_json(out/'preparation_status.json',{'status':'preparing'})
    try:
        source=SOURCE
        state=snap.read(source+'/state.json')
        status=snap.read(source+'/validation_status.json')
        result=snap.read(source+'/validation_result.json')
        validation=snap.read(source+'/validation_declaration.json')
        seed=validated_half_seed(state,status,result,validation)
        cfg=deepcopy(snap.read(source+'/config.json',state['config_sha256']))
        if pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True):raise RuntimeError('source dependencies changed')
        if pipeline.claim(ROOT/seed['path'])!=seed:raise RuntimeError('source latest radiation bytes changed')
        trial=load_arrays(snap.save(source+'/trial_material.npz',state['trial_sha256']))
        other=REFERENCE
        other_state=snap.read(other+'/state.json')
        reference=load_arrays(snap.save(other+'/trial_material.npz',other_state['trial_sha256']))
        identical_material(trial,reference)
        for row in cfg['sources']:
            if not row['path'].endswith('.dat'):snap.save(row['path'],row['sha256'])
        copied=carry_trial(ROOT/source,out)
        identical_material(load_arrays(out/'trial_material.npz'),trial)
        source_threshold=cfg['radiation_threshold']
        cfg.update(run=args.run,workers=args.workers,maximum_maps=2,feedback_every=2,
                   radiation_threshold=1e-4,seed='warm',warm_seed=seed,
                   seed_provenance='latest recorded state of exactly the same material; paired radiation-history diagnostic',
                   extension_of=source,extension_purpose='two-map feedback diagnostic from a half-step mixture output validated against its full-field prediction',
                   candidate_relaxation=float(trial['relaxation']))
        cfg['sources']=list(cfg['sources'])+[copied['source'],copied['destination'],
            pipeline.claim(ROOT/other/'trial_material.npz'),pipeline.claim(Path(__file__)),
            pipeline.claim(ROOT/'operations/half_history_feedback.sbatch'),
            pipeline.claim(ROOT/'operations/prepare_cross_feedback.py'),
            pipeline.claim(ROOT/'operations/prepare_affine_feedback_precision.py'),
            pipeline.claim(ROOT/'operations/radiation_history_diagnostic.py'),
            pipeline.claim(ROOT/'operations/validate_half_history_candidate.py'),
            pipeline.claim(ROOT/'operations/validate_cross_history_candidate.py'),seed,
            pipeline.claim(ROOT/source/'validation_result.json'),pipeline.claim(ROOT/source/'validation_status.json')]
        declaration={'environment':pipeline.environment(),'history':'validated identical-half-step radiation mixture','source_run':source,
                     'source_seed':seed,'source_validation_state':pipeline.claim(ROOT/source/'state.json'),'identical_other_material':pipeline.claim(ROOT/other/'trial_material.npz'),
                     'maximum_new_maps':2,'feedback_every':2,'workers':args.workers,
                     'purpose':'measure true feedback of a full-field-validated mixture without assuming affine material response',
                     'source_validation_result':pipeline.claim(ROOT/source/'validation_result.json'),
                     'source_validation_declaration':pipeline.claim(ROOT/source/'validation_declaration.json'),
                     'maximum_feedback_pairs':1, 'candidate_relaxation':float(trial['relaxation']),
                     'NUMPY_MADVISE_HUGEPAGE':os.environ['NUMPY_MADVISE_HUGEPAGE'],
                     'physical_dt_changed':False,'science_gates_relaxed':False,
                     'source_radiation_threshold':source_threshold,'new_radiation_threshold':1e-4,
                     'science_gate_note':'strict 1e-4 run gate; relaxed 2.5e-4 remains a comparison only',
                     'old_history_not_grafted':True,'accepted_material_step':False,
                     'automatic_budget_extension':False,'true_inner_error_bound_available':False}
        pipeline.write_json(out/'precision_declaration.json',declaration)
        cfg['sources'].append(pipeline.claim(out/'precision_declaration.json'))
        pipeline.write_json(out/'config.json',cfg)
        pipeline.write_json(out/'native_trial_audit.json',audit_native_trial(cfg,trial))
        pipeline.write_json(out/'state.json',{'config_sha256':pipeline.sha256(out/'config.json'),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[args.run+f'/state_{i}.dat' for i in range(3)],
            'current_slot':0,'active_map':None})
        # 只初始化并复制已验证种子，不在准备阶段先跑 map、也不越过反馈间隔。
        if pipeline.STOP:
            pipeline.write_json(out/'preparation_status.json',{'status':'incomplete','new_maps':0});return
        pipeline.run_pipeline(out,0,False)
        initialized=pipeline.read(out/'state.json')
        initialized_identity(initialized,seed,trial,load_arrays(out/'trial_material.npz'))
        pipeline.write_json(out/'post_initialization_native_audit.json',audit_native_trial(cfg,trial))
        pipeline.write_json(out/'preparation_status.json',{'status':'complete','new_maps':0})
    except Exception as exc:
        pipeline.write_json(out/'preparation_status.json',{'status':'failed','error':str(exc)})
        raise


if __name__=='__main__':main()
