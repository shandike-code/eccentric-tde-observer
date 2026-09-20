"""Declare one dyadic material backtrack after a stable, rejected feedback pair."""
from __future__ import annotations
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'hpc'),str(ROOT/'src'),str(ROOT/'scripts')]
import pipeline
from operations.review_small_step_evidence import Snapshot
from operations.prepare_encoded_backtrack import candidate_arrays, load_arrays, audit_native_trial
from operations.prepare_common_seed_precision import latest_seed
from operations.audit_affine_feedback_histories import require_settled_pair

SOURCE='outputs/hpc/subspace-feedback-20260920'
AUDIT='outputs/hpc/outer-contraction-audit-20260920'
ALPHA=0.001953125
REQUIRED_GATES = {
    'last_two_photoionization_pass', 'last_two_total_recombination_pass',
    'last_two_atomic_heating_pass', 'last_two_direct_heating_pass',
    'last_two_formal_heating_pass', 'inner_noise_resolved_pass',
    'candidate_l2_contraction_pass', 'candidate_mass_weighted_contraction_pass',
    'candidate_maximum_cell_contraction_pass', 'two_formal_feedback_states_pass',
    'two_inner_radiation_residuals_pass', 'two_boundary_spectra_pass',
    'two_boundary_bolometric_pass', 'candidate_state_bytes_pass',
    'population_nonnegative_pass', 'all_residual_components_finite_pass',
}


def guarded_half_trial(source, old, baseline, summary):
    expected={'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass'}
    gates=summary['gate_checks']
    if (set(gates)!=REQUIRED_GATES
        or set(k for k,v in gates.items() if v is not True)!=expected
        or summary['decision']['finite_trial_accepted_as_one_nonlinear_step'] is not False):
        raise ValueError('requires a stable pair rejected only by L2 and mass contraction')
    if float(source['relaxation'])!=2*ALPHA:
        raise ValueError('source is not the declared 0.00390625 candidate')
    trial,checks=candidate_arrays(source,old,baseline,ALPHA)
    # 中文：只缩小物质迭代位移，物理时间步、基态、方向和接受基准逐位不变。
    for key in ('base_encoded_state','finite_direction','base_residual','density_g_cm3','step_duration_s','phase_index'):
        if not np.array_equal(trial[key],source[key]):raise RuntimeError('backtrack changed '+key)
    return trial,checks


def assert_written_trial(actual, expected):
    if set(actual)!=set(expected) or any(not np.array_equal(actual[k],expected[k]) for k in expected):
        raise RuntimeError('written material trial differs from the declared backtrack')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',required=True)
    p.add_argument('--workers',type=int,choices=(2,16),required=True);args=p.parse_args()
    pipeline.require_allocation(args.workers)
    if os.environ.get('NUMPY_MADVISE_HUGEPAGE')!='0':raise RuntimeError('NUMPY_MADVISE_HUGEPAGE=0 required')
    out=pipeline.safe_path(ROOT,args.run);out.relative_to(ROOT/'outputs/hpc');out.mkdir(parents=True,exist_ok=False)
    snap=Snapshot(out);pipeline.write_json(out/'preparation_status.json',{'status':'preparing'})
    try:
        state=snap.read(SOURCE+'/state.json');pair=require_settled_pair(state);seed=latest_seed(state)
        cfg=deepcopy(snap.read(SOURCE+'/config.json',state['config_sha256']))
        if pipeline.verify_claims(ROOT,cfg['sources'],hash_files=True):raise RuntimeError('frozen dependency changed')
        if pipeline.claim(ROOT/seed['path'])!=seed:raise RuntimeError('latest source radiation changed')
        folder=SOURCE+'/feedback-round1';summary=snap.read(folder+'/feedback_summary.json')
        if summary['protocol_sha256']!=pair['protocol_sha256']:raise RuntimeError('source pair identity changed')
        proto=snap.read(folder+'/feedback_protocol.json',pair['protocol_sha256'])
        if snap.read(AUDIT+'/status.json')['status']!='complete':raise RuntimeError('contraction audit incomplete')
        audit=snap.read(AUDIT+'/audit.json')
        if (audit['formal_comparison']!=summary['comparison']
            or audit['formal_gates']!=summary['gate_checks']
            or audit['formal_baseline_claim']!=proto['sources']['base_residual']):
            raise RuntimeError('audit does not describe this rejected pair')
        for endpoint in ('previous','final'):
            snap.save(proto['configuration'][endpoint+'_feedback_output'],
                      audit['pairs']['candidate'][endpoint]['feedback_sha256'])
        if proto['sources']['trial_material']['sha256']!=state['trial_sha256']:
            raise RuntimeError('source trial differs from the formally evaluated candidate')
        source=load_arrays(snap.save(SOURCE+'/trial_material.npz',state['trial_sha256']))
        c=proto['sources']['physical_old_time_level'];old=load_arrays(snap.save(c['path'],c['sha256']))
        c=proto['sources']['base_residual'];baseline=np.load(snap.save(c['path'],c['sha256']),allow_pickle=False)
        trial,checks=guarded_half_trial(source,old,baseline,summary)
        for c in cfg['sources']:
            if not c['path'].endswith('.dat'):snap.save(c['path'],c['sha256'])
        np.savez(out/'trial_material.npz',**trial)
        assert_written_trial(load_arrays(out/'trial_material.npz'),trial)
        cfg.update(run=args.run,workers=args.workers,maximum_maps=4,feedback_every=2,radiation_threshold=1e-4,
            seed='warm',warm_seed=seed,candidate_relaxation=ALPHA,extension_of=SOURCE,
            physics_scope='one 0.001953125 material backtrack at unchanged physical time and frozen encoded direction',
            seed_provenance='previous candidate radiation is a numerical initial guess only, not a solution of this material',
            extension_purpose='test one smaller material step after stable but noncontracting feedback; bounded four maps and two feedback pairs')
        declaration={'environment':pipeline.environment(),'source_run':SOURCE,'source_seed':seed,
            'source_alpha':float(source['relaxation']),'candidate_alpha':ALPHA,'candidate_gates':checks,
            'maximum_new_maps':4,'maximum_feedback_pairs':2,'workers':args.workers,
            'physical_dt_changed':False,'base_and_direction_changed':False,'science_gates_relaxed':False,
            'seed_is_solution_for_new_material':False,'automatic_budget_extension':False,
            'accepted_material_step':False,'source_summary':pipeline.claim(ROOT/folder/'feedback_summary.json'),
            'audit':pipeline.claim(ROOT/AUDIT/'audit.json'),'trial':pipeline.claim(out/'trial_material.npz')}
        pipeline.write_json(out/'backtrack_declaration.json',declaration)
        cfg['sources']=list(cfg['sources'])+[seed,pipeline.claim(out/'trial_material.npz'),
            pipeline.claim(out/'backtrack_declaration.json'),pipeline.claim(Path(__file__)),
            pipeline.claim(ROOT/'operations/half_step_after_audit.sbatch'),
            pipeline.claim(ROOT/'operations/prepare_encoded_backtrack.py'),
            pipeline.claim(ROOT/'operations/audit_outer_contraction.py'),
            pipeline.claim(ROOT/AUDIT/'audit.json'),pipeline.claim(ROOT/folder/'feedback_summary.json')]
        pipeline.write_json(out/'config.json',cfg)
        pipeline.write_json(out/'native_trial_audit.json',audit_native_trial(cfg,trial))
        pipeline.write_json(out/'state.json',{'config_sha256':pipeline.sha256(out/'config.json'),'status':'initializing',
            'initialization_blocks':[],'history':[],'slots':[args.run+f'/state_{i}.dat' for i in range(3)],
            'current_slot':0,'active_map':None})
        pipeline.run_pipeline(out,0,False)
        initialized=pipeline.read(out/'state.json')
        if initialized['status']!='radiation' or initialized['history'] or initialized['current_sha256']!=seed['sha256']:
            raise RuntimeError('initialization did not preserve the declared seed')
        assert_written_trial(load_arrays(out/'trial_material.npz'),trial)
        pipeline.write_json(out/'preparation_status.json',{'status':'complete','new_maps':0})
    except BaseException as exc:
        pipeline.write_json(out/'preparation_status.json',{'status':'failed','error':str(exc)});raise


if __name__=='__main__':main()
