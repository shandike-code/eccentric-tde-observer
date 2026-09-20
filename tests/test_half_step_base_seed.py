from copy import deepcopy
import numpy as np
import pytest
from operations.prepare_half_step_base_seed import baseline_seed,verify_material_pair,verify_reference,REQUIRED_GATES


def state():
    return {'status':'baseline_control_complete','history':[
        {'output_path':'s1','output_sha256':'h1'}, {'output_path':'s2','output_sha256':'h2'}],
        'slots':['s0','s1','s2'],'current_slot':2,'current_sha256':'h2','active_map':None}


def test_baseline_seed_uses_its_latest_output():
    c=baseline_seed(state());assert c['path']=='s2' and c['sha256']=='h2'


@pytest.mark.parametrize('key,value',[('status','radiation'),('active_map',{'map':3}),
    ('pending_feedback',{'round':1}),('current_sha256','h1'),('current_slot',1),('history',[])])
def test_baseline_seed_refuses_unsettled_or_old_slots(key,value):
    s=state();s[key]=value
    with pytest.raises(ValueError):baseline_seed(s)


def materials():
    t={k:np.ones(8) for k in ('base_encoded_state','finite_direction','base_residual','density_g_cm3')}
    t.update(phase_index=np.array(1367),step_duration_s=np.array(889.),relaxation=np.array(.001953125))
    t['encoded_state']=t['base_encoded_state']+.001953125*t['finite_direction']
    b=deepcopy(t);b['relaxation']=np.array(0.);b['encoded_state']=b['base_encoded_state'].copy()
    return t,b


def test_baseline_is_the_same_physical_base_not_the_half_step():
    verify_material_pair(*materials())


@pytest.mark.parametrize('key',['relaxation','encoded_state','finite_direction','density_g_cm3','phase_index','step_duration_s'])
def test_mismatched_base_or_physics_cannot_seed_the_declared_control(key):
    t,b=materials();b[key]=b[key]+1
    with pytest.raises(ValueError):verify_material_pair(t,b)


def reference():
    h=[{'input_path':str(i),'input_sha256':'h'+str(i)} for i in range(8)]
    p={'endpoints':[7,8],'protocol_sha256':'p','endpoints_claim':{
        'previous':{'path':'6','sha256':'h6'},'final':{'path':'7','sha256':'h7'}}}
    s={'status':'diagnostic_round_complete','history':h,'diagnostic':{'rounds':[{},p]}}
    d={'protocol_sha256':'p','gate_checks':{k:k not in {
        'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass'} for k in REQUIRED_GATES},
        'decision':{'finite_trial_accepted_as_one_nonlinear_step':False}}
    return s,d


def test_reference_uses_the_last_actual_feedback_pair():
    assert verify_reference(*reference())['endpoints']==[7,8]


@pytest.mark.parametrize('fault',['heat_failed','missing_gate','wrong_protocol','accepted'])
def test_reference_cannot_be_replaced_by_another_verdict(fault):
    s,d=reference()
    if fault=='heat_failed':d['gate_checks']['last_two_atomic_heating_pass']=False
    if fault=='missing_gate':del d['gate_checks']['inner_noise_resolved_pass']
    if fault=='wrong_protocol':d['protocol_sha256']='other'
    if fault=='accepted':d['decision']['finite_trial_accepted_as_one_nonlinear_step']=True
    with pytest.raises(ValueError):verify_reference(s,d)
