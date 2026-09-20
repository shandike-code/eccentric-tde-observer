"""Bounded read-only affine scan for the audited identical half-step histories."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays,audit_native_trial
from operations.radiation_history_diagnostic import identical_material
from operations.half_history_basis import last_actual_map
from operations.scan_cross_history_direction import scan,metrics,COEFFICIENT_L1_CAP

SOURCES=('outputs/hpc/half-step-base-seeded-20260920','outputs/hpc/half-step-precision-20260920')
AUDIT='outputs/hpc/half-history-replay-20260920'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True);args=p.parse_args()
    pipeline.require_allocation(1)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'status.json',{'status':'running','new_maps':0})
    try:
        if snap.read(AUDIT+'/status.json')['status']!='complete':raise RuntimeError('replay audit incomplete')
        audit=snap.read(AUDIT+'/audit.json')
        for key in ('same_material_all_fields','same_platform_final_replay_exact','all_feedback_blocks_reassembled_exact'):
            if audit[key] is not True:raise RuntimeError('replay evidence missing: '+key)
        records={r['path']:r for r in snap.read(AUDIT+'/snapshot-manifest.json')}
        states=[];trials=[];basis=[]
        for source in SOURCES:
            state=snap.read(source+'/state.json',records[source+'/state.json']['sha256']);states.append(state)
            cfg=snap.read(source+'/config.json',state['config_sha256'])
            trial=load_arrays(snap.save(source+'/trial_material.npz',state['trial_sha256']));trials.append(trial)
            audit_native_trial(cfg,trial);basis.extend(last_actual_map(state))
            for claim in cfg['sources']:
                if not claim['path'].endswith('.dat'):snap.save(claim['path'],claim['sha256'])
        identical_material(*trials)
        for claim in basis:
            path=ROOT/claim['path']
            if path.stat().st_size!=pipeline.STATE_BYTES or pipeline.sha256(path)!=claim['sha256']:
                raise RuntimeError('basis size or SHA differs')
        for name in ('scan_half_history_direction.py','scan_half_history_direction.sbatch','half_history_basis.py',
                     'scan_cross_history_direction.py','radiation_history_diagnostic.py',
                     'material_direction_diagnostic.py','prepare_encoded_backtrack.py','review_small_step_evidence.py'):
            snap.save('operations/'+name)
        snap.save('scripts/phase7b9bx_slow_mode_anderson.py')
        with np.load(snap.save(pipeline.MASTER),allow_pickle=False) as z:edges=z['active_edge_hz'].copy()
        pipeline.write_json(out/'declaration.json',{'environment':pipeline.environment(),'basis':basis,
            'formula':'X=XB+g*(XB-XO); Ypred=YB+g*(YB-YO)',
            'objective':'full-field unweighted predicted residual squared L2, then separately require maximum-norm improvement',
            'coefficient_l1_cap':COEFFICIENT_L1_CAP,'same_material_all_fields':True,
            'new_maps':0,'candidate_write_budget':0,'physical_dt_changed':False,'fresh_original_map_required':True,
            'source_audit':AUDIT,'source_order':list(SOURCES)})
        paths=[ROOT/c['path'] for c in basis]
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            direction=scan(paths,pipeline.SHAPE)
            prediction=metrics(paths,pipeline.SHAPE,direction['gamma'],edges)
        best=min(s['history'][-1]['residual'] for s in states)
        checks={'resolved_direction':direction['direction_resolution_ratio']>1e-12,
                'nonzero_coefficient':direction['gamma']!=0.,
                'bounded_coefficients':direction['coefficient_l1']<=COEFFICIENT_L1_CAP,
                'nonnegative_prediction':prediction['candidate_negative_count']==prediction['predicted_map_negative_count']==0,
                'maximum_norm_improves_best_history':prediction['predicted_residual'] is not None and prediction['predicted_residual']<.99*best,
                'boundary_spectrum_pass':prediction['predicted_boundary_l1'] is not None and prediction['predicted_boundary_l1']<1e-3,
                'boundary_bolometric_pass':prediction['predicted_boundary_bolometric'] is not None and prediction['predicted_boundary_bolometric']<1e-3}
        for claim in basis:
            if pipeline.sha256(ROOT/claim['path'])!=claim['sha256']:raise RuntimeError('basis changed during scan')
        pipeline.write_json(out/'prediction.json',{'direction':direction,'prediction':prediction,'checks':checks,
            'algebraic_feasibility':all(checks.values()),'best_measured_residual':best,'actual_map_performed':False,
            'candidate_written':False,'accepted_material_step':False,
            'limitations':['Affine prediction requires an independent full original-operator map.',
                           'Operator residual and history image ratio prove neither an error bound nor uniqueness.']})
        pipeline.write_json(out/'status.json',{'status':'complete','new_maps':0,'candidate_written':False})
    except BaseException as exc:
        pipeline.write_json(out/'status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
