"""Prepare four-map same-material precision comparisons from two stopped histories."""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays,audit_native_trial
from operations.prepare_extension_run import carry_trial
from operations.common_seed_trial_control import common_seed_trial

SOURCES={
    'base-seeded':'outputs/hpc/common-seed-a00390625-20260919',
    'old-history':'outputs/hpc/small-step-a00390625-cont24-20260918',
}


def latest_seed(state):
    """Reject partial, unsettled, or non-latest slots before hashing the seed."""
    if (state.get('status') not in {'common_seed_control_complete','diagnostic_round_complete'}
        or state.get('active_map') or state.get('pending_feedback') or not state.get('history')):
        raise ValueError('source must be stopped and settled')
    row=state['history'][-1]
    if (state['slots'][state['current_slot']]!=row['output_path']
        or state['current_sha256']!=row['output_sha256']):
        raise ValueError('source does not identify its latest radiation slot')
    return {'path':row['output_path'],'sha256':row['output_sha256'],'size_bytes':pipeline.STATE_BYTES}


def same_material(trial,reference):
    # 两条链只允许辐射历史不同；连冗余物质字段也逐位核对，防止混入物质扰动。
    if set(trial)!=set(reference) or any(not np.array_equal(trial[k],reference[k]) for k in trial):
        raise ValueError('paired histories do not have exactly the same material')
    common_seed_trial(trial,reference['base_encoded_state'],reference['base_residual'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history',choices=SOURCES,required=True)
    parser.add_argument('--workers',type=int,choices=(2,16),required=True)
    parser.add_argument('--run',required=True);args=parser.parse_args()
    pipeline.require_allocation(args.workers)
    out=pipeline.safe_path(ROOT,args.run)
    if not out.is_relative_to(ROOT/'outputs/hpc'):raise ValueError('output outside outputs/hpc')
    out.mkdir(parents=True,exist_ok=False);snap=Snapshot(out)
    pipeline.write_json(out/'preparation_status.json',{'status':'preparing'})
    try:
        source=SOURCES[args.history]
        state=snap.read(source+'/state.json');seed=latest_seed(state)
        cfg=deepcopy(snap.read(source+'/config.json',state['config_sha256']))
        if pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True):raise RuntimeError('source dependencies changed')
        if pipeline.claim(ROOT/seed['path'])!=seed:raise RuntimeError('source latest radiation bytes changed')
        trial=load_arrays(snap.save(source+'/trial_material.npz',state['trial_sha256']))
        other=SOURCES['old-history' if args.history=='base-seeded' else 'base-seeded']
        other_state=snap.read(other+'/state.json');latest_seed(other_state)
        reference=load_arrays(snap.save(other+'/trial_material.npz',other_state['trial_sha256']))
        same_material(trial,reference)
        for row in cfg['sources']:
            if not row['path'].endswith('.dat'):snap.save(row['path'],row['sha256'])
        copied=carry_trial(ROOT/source,out)
        same_material(load_arrays(out/'trial_material.npz'),trial)
        source_threshold=cfg['radiation_threshold']
        cfg.update(run=args.run,workers=args.workers,maximum_maps=4,feedback_every=2,
                   radiation_threshold=1e-4,seed='warm',warm_seed=seed,
                   seed_provenance='latest recorded state of exactly the same material; paired radiation-history diagnostic',
                   extension_of=source,extension_purpose='four-map common-material history comparison',
                   candidate_relaxation=.00390625)
        cfg['sources']=list(cfg['sources'])+[copied['source'],copied['destination'],
            pipeline.claim(ROOT/other/'trial_material.npz'),pipeline.claim(Path(__file__)),
            pipeline.claim(ROOT/'operations/common_seed_precision.sbatch')]
        declaration={'environment':pipeline.environment(),'history':args.history,'source_run':source,
                     'source_seed':seed,'identical_other_material':pipeline.claim(ROOT/other/'trial_material.npz'),
                     'maximum_new_maps':4,'feedback_every':2,'workers':args.workers,
                     'purpose':'measure whether same-material feedback histories approach each other',
                     'physical_dt_changed':False,'science_gates_relaxed':False,
                     'source_radiation_threshold':source_threshold,'new_radiation_threshold':1e-4,
                     'science_gate_note':'strict 1e-4 run gate; relaxed 2.5e-4 remains a comparison only',
                     'initialization_history_counts_differ':True,'accepted_material_step':False,
                     'automatic_budget_extension':False,'true_inner_error_bound_available':False}
        pipeline.write_json(out/'precision_declaration.json',declaration)
        cfg['sources'].append(pipeline.claim(out/'precision_declaration.json'))
        pipeline.write_json(out/'config.json',cfg)
        pipeline.write_json(out/'native_trial_audit.json',audit_native_trial(cfg,trial))
        pipeline.write_json(out/'state.json',{'config_sha256':pipeline.sha256(out/'config.json'),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[args.run+f'/state_{i}.dat' for i in range(3)],
            'current_slot':0,'active_map':None})
        # 只初始化并复制已验证种子，不在准备阶段先跑 map、也不越过反馈间隔。
        pipeline.run_pipeline(out,0,False)
        initialized=pipeline.read(out/'state.json')
        if initialized['status']!='radiation' or initialized['history'] or initialized['current_sha256']!=seed['sha256']:
            raise RuntimeError('initialization did not preserve the recorded input')
        pipeline.write_json(out/'preparation_status.json',{'status':'complete','new_maps':0})
    except Exception as exc:
        pipeline.write_json(out/'preparation_status.json',{'status':'failed','error':str(exc)})
        raise


if __name__=='__main__':main()
