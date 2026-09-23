from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from operations import common_native_feedback as fresh


def reference():
    gates={'consecutive_inner_radiation_state_count_at_least':2,'each_global_original_operator_residual_below':1e-4,
        'each_boundary_spectrum_l1_below':1e-3,'each_boundary_bolometric_fraction_below':1e-3,'each_formal_feedback_state_gate_passed':True,
        'maximum_last_two_photoionization_volume_l1_below':1e-3,'maximum_last_two_total_recombination_volume_l1_below':1e-3,
        'last_two_atomic_heating_volume_l1_below':1e-3,'last_two_direct_heating_volume_l1_below':1e-3,'last_two_formal_heating_volume_l1_below':1e-3,
        'inner_noise_to_trial_signal_l2_ratio_below':.1,'candidate_to_base_residual_l2_ratio_below':1.,'candidate_to_base_mass_weighted_norm_ratio_below':1.,
        'candidate_to_base_maximum_cell_norm_ratio_below':1.,'candidate_state_must_match_frozen_phase7b9i_bytes':True,'minimum_population_fraction_at_least':0.,'all_residual_components_finite':True}
    return {'configuration':{'reuse_completed_feedback_manifests':True,'feedback_origin_protocol_sha256':'old'},
        'sources':{'adapter_runner':{'path':'scripts/phase7b9_formal_feedback_pair_adapter.py'},'trial_material':{'path':'frozen-trial.npz'},'previous_feedback_manifest':{},'final_feedback_artifact':{},'common_origin_protocol':{}},
        'authorization':{'reuse_only_after_bytewise_reproduction_audit':True,'accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass':True,'reject_this_trial_if_any_gate_fails':True,'accept_dynamic_nlte_solution':False},
        'formal_state_gates':fresh.pair._formal_state_gates(),'acceptance_gates':gates}


def endpoints():
    es={'previous':{'path':'new-previous.dat','sha256':'one'},'final':{'path':'new-final.dat','sha256':'two'}}
    rows=[dict(iteration=i,input_sha256=a,output_sha256=b,residual=2e-5,boundary_l1=1e-4,boundary_bolometric=1e-4) for i,a,b in [(3,'one','two'),(4,'two','three')]]
    return es,rows


def test_new_protocol_cannot_reuse_old_feedback_or_change_material():
    old=reference();before=deepcopy(old);es,rows=endpoints()
    p=fresh.new_protocol(old,fresh.ROOT/'outputs/hpc/test-common',es,rows,16)
    assert old==before and p['sources']['trial_material']==old['sources']['trial_material']
    assert p['acceptance_gates']==old['acceptance_gates'] and p['formal_state_gates']==old['formal_state_gates']
    assert 'reuse_completed_feedback_manifests' not in p['configuration'] and 'previous_feedback_manifest' not in p['sources']
    assert p['sources']['adapter_runner']['path']=='operations/common_native_feedback.py'
    assert p['sources']['legacy_adapter']==old['sources']['adapter_runner']
    assert p['sources']['final_radiation']==es['final']


@pytest.mark.parametrize('mutation',('hash','order','gap','gate'))
def test_inconsistent_endpoint_or_threshold_is_rejected(mutation):
    ref=reference();es,rows=endpoints()
    if mutation=='hash':es['final']['sha256']='wrong'
    if mutation=='order':rows[0]['output_sha256']='wrong'
    if mutation=='gap':rows[1]['iteration']=5
    if mutation=='gate':ref['formal_state_gates']['each_state_wall_time_strictly_below_s']=7200.
    with pytest.raises(RuntimeError):fresh.new_protocol(ref,fresh.ROOT/'outputs/hpc/test-common',es,rows,16)


def test_worker_preserves_native_raw_and_uses_independent_formal(monkeypatch,tmp_path):
    monkeypatch.setattr(fresh,'ROOT',tmp_path)
    monkeypatch.setattr(fresh.pair,'load_frozen_pair_protocol',lambda *a,**k:{'common_worker_claims':[]})
    monkeypatch.setattr(fresh.reused,'verify',lambda c:None)
    monkeypatch.setattr(fresh.pipeline,'claim',lambda p:{'path':str(p.relative_to(tmp_path)),'sha256':fresh.pipeline.sha256(p),'size_bytes':p.stat().st_size})
    raw={fresh.bridge.FORMAL:np.ones(4)*9,'atomic_rate_heating_erg_s_cm3':np.ones(4)*3}
    def native_adapter(protocol,sha,label,index,partial,report):
        np.savez(partial,**raw);fresh.pipeline.write_json(report,{'block_index':index,'partial_sha256':fresh.pipeline.sha256(partial)})
    monkeypatch.setattr(fresh.pair,'run_worker_adapter',native_adapter)
    monkeypatch.setattr(fresh,'common_block',lambda *a:{'common_formal_erg_s_cm3':np.ones(4)*2})
    p=tmp_path/'block00.npz';r=tmp_path/'block00.json';fresh.worker(tmp_path/'protocol.json','sha','final',0,p,r)
    assert np.array_equal(fresh.load_arrays(p)[fresh.bridge.FORMAL],np.ones(4)*2)
    assert np.array_equal(fresh.load_arrays(p)['atomic_rate_heating_erg_s_cm3'],raw['atomic_rate_heating_erg_s_cm3'])
    assert np.array_equal(fresh.load_arrays(p.with_suffix('.legacy.npz'))[fresh.bridge.FORMAL],raw[fresh.bridge.FORMAL])
    with pytest.raises(FileExistsError):fresh.worker(tmp_path/'protocol.json','sha','final',0,p,r)
