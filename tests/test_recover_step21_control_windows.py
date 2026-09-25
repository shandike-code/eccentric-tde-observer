from copy import deepcopy
import numpy as np
import pytest
from operations import recover_step21_control_windows as recovery
fresh=recovery.fresh

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


def templates():
    finite=reference()
    for k in ('outer_base_material','base_residual','physical_old_time_level'):finite['sources'][k]={'path':k,'sha256':'frozen'}
    finite['outer_iteration']={'index':21,'base_accepted_index':20,'base_is_accepted_trial':True,'physical_time_advanced':False}
    zero=deepcopy(finite);recovery.fixed.set_authorization(zero,'control');return finite,zero


def test_reproduces_failed_zero_template_and_constructs_zero_output_from_valid_template():
    finite,zero=templates();saved=deepcopy(zero);es,rows=endpoints();out=fresh.ROOT/'outputs/hpc/test-recover'
    with pytest.raises(RuntimeError,match='acceptance authorization changed'):fresh.new_protocol(zero,out,es,rows,16)
    p=recovery.control_protocol(finite,zero,out,es,rows,{'path':'control-trial'}, {'path':'retained'}, {'path':'declaration'})
    assert zero==saved and finite['authorization']['accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass'] is True
    assert p['sources']['trial_material']=={'path':'control-trial'} and p['authorization']['zero_displacement_control'] is True
    for key in ('accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass','accept_finite_trial_only_if_all_acceptance_gates_pass','accept_material_step'):assert p['authorization'][key] is False
    assert p['numerical_backtracking']['alpha']==0 and not p['numerical_backtracking']['physical_time_advanced']


@pytest.mark.parametrize('kind',['gate','old_layer','base','residual'])
def test_finite_template_cannot_change_science_identity(kind):
    finite,zero=templates();es,rows=endpoints()
    if kind=='gate':finite['acceptance_gates']['last_two_atomic_heating_volume_l1_below']=.01
    else:finite['sources'][{'old_layer':'physical_old_time_level','base':'outer_base_material','residual':'base_residual'}[kind]]={'path':'changed'}
    with pytest.raises(RuntimeError):recovery.control_protocol(finite,zero,fresh.ROOT/'outputs/hpc/test-recover',es,rows,{}, {}, {})


def history():return [{'iteration':i,'input_sha256':str(i-1),'output_sha256':str(i)} for i in range(1,9)]


def test_only_history_is_inherited_after_warm_identity():
    rows=history();state={'history':[],'active_map':None,'current_sha256':'8','slots':['new0','new1','new2'],'current_slot':0}
    recovered=recovery.inherit_history(state,rows,{'sha256':'8'});assert recovered['history']==rows and recovered['slots']==['new0','new1','new2']
    recovered['history'][0]['iteration']=100;assert rows[0]['iteration']==1


@pytest.mark.parametrize('kind',['existing','partial','length','lineage','seed','state'])
def test_unsafe_history_import_rejected(kind):
    rows=history();state={'history':[],'active_map':None,'current_sha256':'8'};seed={'sha256':'8'}
    if kind=='existing':state['history']=[{}]
    if kind=='partial':state['active_map']={}
    if kind=='length':rows.pop()
    if kind=='lineage':rows[2]['input_sha256']='bad'
    if kind=='seed':seed['sha256']='bad'
    if kind=='state':state['current_sha256']='bad'
    with pytest.raises(RuntimeError):recovery.inherit_history(state,rows,seed)


def test_owed_feedback_runs_before_exactly_eight_new_maps():
    events=[];recovery.continuation_schedule(lambda n:events.append(('feedback',n)),lambda n:events.append(('map',n)))
    assert events==[('feedback',8)]+[('map',n) for n in range(9,17)]+[('feedback',16)]


def test_failed_owed_feedback_forbids_new_maps():
    def feedback(n):raise RuntimeError('failed feedback')
    with pytest.raises(RuntimeError):recovery.continuation_schedule(feedback,lambda n:pytest.fail('new map before feedback'))
