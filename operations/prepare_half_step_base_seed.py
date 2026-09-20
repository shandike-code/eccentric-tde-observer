"""Change only the radiation initial guess of the frozen half-step candidate."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'hpc'), str(ROOT/'src'), str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import load_arrays, audit_native_trial
from operations.prepare_extension_run import carry_trial
from operations.prepare_half_step_after_audit import ALPHA, REQUIRED_GATES, assert_written_trial
from operations.material_direction_diagnostic import latest_pair

SOURCE = 'outputs/hpc/half-step-precision-20260920'
BASE = 'outputs/hpc/baseline-zero-control-20260919'
SEED_SHA = '565a19526e7fb1ab106326b3efc123ba2a589b99525759eca8b3d95fd024a0af'


def baseline_seed(state):
    """The zero-control has its own terminal status; no mutation of old helpers."""
    if (state.get('status') != 'baseline_control_complete' or state.get('active_map')
            or state.get('pending_feedback') or len(state.get('history', [])) != 2):
        raise ValueError('baseline control is not complete and settled')
    row = state['history'][-1]
    if (state['slots'][state['current_slot']] != row['output_path']
            or state['current_sha256'] != row['output_sha256']):
        raise ValueError('baseline seed is not its latest recorded output')
    return {'path':row['output_path'], 'sha256':row['output_sha256'], 'size_bytes':pipeline.STATE_BYTES}


def verify_material_pair(trial, base):
    if (float(trial['relaxation']) != ALPHA or float(base['relaxation']) != 0
            or not np.array_equal(trial['encoded_state'], trial['base_encoded_state']+ALPHA*trial['finite_direction'])
            or not np.array_equal(base['encoded_state'], trial['base_encoded_state'])):
        raise ValueError('expected the exact half-step and its zero-displacement base')
    for k in ('base_encoded_state','finite_direction','base_residual','density_g_cm3','phase_index','step_duration_s'):
        if not np.array_equal(trial[k], base[k]): raise ValueError('baseline physics changed: '+k)


def verify_reference(state, summary):
    pair = latest_pair(state)
    if len(state['history']) != 8 or len(state['diagnostic']['rounds']) != 2:
        raise ValueError('reference is not the declared eight-map half-step precision run')
    gates=summary['gate_checks']
    if (summary['protocol_sha256'] != pair['protocol_sha256']
            or set(gates) != REQUIRED_GATES
            or {k for k,v in gates.items() if v is not True} != {
                'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass'}
            or summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] is not False):
        raise ValueError('reference must have stable feedback and only two contraction failures')
    return pair


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True)
    args=parser.parse_args();pipeline.require_allocation(16)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'preparation_status.json',{'status':'preparing'})
    try:
        state=snap.read(SOURCE+'/state.json');summary=snap.read(SOURCE+'/feedback-round2/feedback_summary.json')
        pair=verify_reference(state,summary)
        proto=snap.read(SOURCE+'/feedback-round2/feedback_protocol.json',pair['protocol_sha256'])
        trial=load_arrays(snap.save(SOURCE+'/trial_material.npz',state['trial_sha256']))
        if proto['sources']['trial_material']['sha256']!=state['trial_sha256']:
            raise RuntimeError('reference material differs from its formal protocol')
        bs=snap.read(BASE+'/state.json');seed=baseline_seed(bs)
        if seed['path']!=BASE+'/state_2.dat' or seed['sha256']!=SEED_SHA:
            raise RuntimeError('baseline differs from the declared alternative initial guess')
        if snap.read(BASE+'/control_status.json')['status']!='complete':raise RuntimeError('baseline control incomplete')
        bc=snap.read(BASE+'/control_result.json')['feedback_protocol']
        bp=snap.read(bc['path'],bc['sha256'])
        base=load_arrays(snap.save(BASE+'/trial_material.npz',bs['trial_sha256']))
        if bp['sources']['trial_material']['sha256']!=bs['trial_sha256']:
            raise RuntimeError('baseline material differs from its formal protocol')
        verify_material_pair(trial,base)
        for k in ('physical_old_time_level','base_residual'):
            if bp['sources'][k]!=proto['sources'][k]:raise RuntimeError('physical reference source mismatch: '+k)
        cfg=deepcopy(snap.read(SOURCE+'/config.json',state['config_sha256']))
        base_cfg=snap.read(BASE+'/config.json',bs['config_sha256'])
        for config in (cfg,base_cfg):
            if pipeline.verify_claims(ROOT,config['sources'],hash_files=True):raise RuntimeError('frozen dependencies changed')
            for c in config['sources']:
                if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
        if pipeline.claim(ROOT/seed['path'])!=seed:raise RuntimeError('baseline radiation bytes changed')
        copied=carry_trial(ROOT/SOURCE,out)
        # 中文：逐字复制同一物质文件，仅更换辐射初猜，不继承零位移物质或其收敛结论。
        assert_written_trial(load_arrays(out/'trial_material.npz'),trial)
        cfg.update(run=args.run,workers=16,maximum_maps=8,feedback_every=4,radiation_threshold=1e-4,
                   seed='warm',warm_seed=seed,candidate_relaxation=ALPHA,extension_of=SOURCE,
                   seed_provenance='zero-displacement baseline radiation used only as an initial guess for unchanged half-step matter',
                   extension_purpose='bounded comparison of two radiation histories at identical half-step material')
        declaration={'environment':pipeline.environment(),'reference_run':SOURCE,'seed_run':BASE,'source_seed':seed,
                     'candidate_alpha':ALPHA,'maximum_new_maps':8,'maximum_feedback_pairs':2,'feedback_every':4,'workers':16,
                     'material_fields_unchanged':True,'physical_dt_changed':False,'science_gates_relaxed':False,
                     'seed_is_solution_for_new_material':False,'old_history_not_grafted':True,
                     'automatic_budget_extension':False,'true_inner_error_bound_available':False}
        pipeline.write_json(out/'history_control_declaration.json',declaration)
        cfg['sources']=list(cfg['sources'])+[seed,copied['source'],copied['destination'],
            pipeline.claim(out/'history_control_declaration.json'),pipeline.claim(Path(__file__)),
            pipeline.claim(ROOT/'operations/half_step_base_seed.sbatch'),pipeline.claim(ROOT/BASE/'state.json'),
            pipeline.claim(ROOT/BASE/'trial_material.npz'),pipeline.claim(ROOT/SOURCE/'state.json'),
            pipeline.claim(ROOT/SOURCE/'feedback-round2/feedback_summary.json'),
            pipeline.claim(ROOT/'operations/material_direction_diagnostic.py'),
            pipeline.claim(ROOT/BASE/'config.json'),pipeline.claim(ROOT/BASE/'control_status.json'),
            pipeline.claim(ROOT/BASE/'control_result.json'),bc,
            pipeline.claim(ROOT/SOURCE/'feedback-round2/feedback_protocol.json')]
        pipeline.write_json(out/'config.json',cfg)
        pipeline.write_json(out/'native_trial_audit.json',audit_native_trial(cfg,trial))
        pipeline.write_json(out/'state.json',{'config_sha256':pipeline.sha256(out/'config.json'),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[args.run+f'/state_{i}.dat' for i in range(3)],'current_slot':0,'active_map':None})
        pipeline.run_pipeline(out,0,False)
        initialized=pipeline.read(out/'state.json')
        if initialized['status']!='radiation' or initialized['history'] or initialized['current_sha256']!=seed['sha256']:
            raise RuntimeError('initialization did not preserve the alternative seed')
        assert_written_trial(load_arrays(out/'trial_material.npz'),trial)
        pipeline.write_json(out/'preparation_status.json',{'status':'complete','new_maps':0})
    except BaseException as exc:
        pipeline.write_json(out/'preparation_status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
