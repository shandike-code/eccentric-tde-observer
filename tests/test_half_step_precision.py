import numpy as np
import pytest
from operations.prepare_half_step_precision import eligible_source, ALPHA, REQUIRED_GATES


def source():
    history = [dict(input_path=f's{i}', input_sha256=f'i{i}', output_path=f's{i+1}', output_sha256=f'i{i+1}') for i in range(4)]
    pair = {'endpoints': [3,4], 'protocol_sha256': 'p', 'endpoints_claim': {
        'previous': {'path':'s2','sha256':'i2'}, 'final': {'path':'s3','sha256':'i3'}}}
    state = {'status':'diagnostic_round_complete', 'history':history, 'slots':['s4'],
             'current_slot':0, 'current_sha256':'i4', 'active_map':None, 'diagnostic':{'rounds':[{},pair]}}
    failed = {'candidate_l2_contraction_pass','candidate_mass_weighted_contraction_pass',
              'last_two_atomic_heating_pass','last_two_direct_heating_pass',
              'last_two_formal_heating_pass','two_inner_radiation_residuals_pass'}
    summary = {'protocol_sha256':'p', 'gate_checks':{k:k not in failed for k in REQUIRED_GATES},
               'decision':{'finite_trial_accepted_as_one_nonlinear_step':False}}
    trial = {'relaxation':np.array(ALPHA),'base_encoded_state':np.ones(8),
             'finite_direction':np.ones(8),'encoded_state':np.ones(8)*(1+ALPHA)}
    return state, summary, trial


def test_uses_latest_output_not_the_last_feedback_input():
    seed, pair = eligible_source(*source())
    assert seed['path']=='s4' and seed['sha256']=='i4'
    assert pair['endpoints_claim']['final']['path']=='s3'


@pytest.mark.parametrize('fault', ['unsettled','old_seed','wrong_pair','wrong_protocol',
                                  'wrong_endpoint','wrong_alpha','wrong_encoded','missing_gate',
                                  'physical_failure','already_accepted'])
def test_rejects_wrong_experiment_or_repurposed_evidence(fault):
    state, summary, trial = source()
    if fault=='unsettled': state['active_map']={'iteration':5}
    if fault=='old_seed': state['current_sha256']='i3'
    if fault=='wrong_pair': state['diagnostic']['rounds'][-1]['endpoints']=[1,2]
    if fault=='wrong_protocol': summary['protocol_sha256']='other'
    if fault=='wrong_endpoint': state['diagnostic']['rounds'][-1]['endpoints_claim']['final']['sha256']='other'
    if fault=='wrong_alpha': trial['relaxation']=np.array(2*ALPHA)
    if fault=='wrong_encoded': trial['encoded_state'][0]+=.001
    if fault=='missing_gate': del summary['gate_checks']['inner_noise_resolved_pass']
    if fault=='physical_failure': summary['gate_checks']['population_nonnegative_pass']=False
    if fault=='already_accepted': summary['decision']['finite_trial_accepted_as_one_nonlinear_step']=True
    with pytest.raises(ValueError): eligible_source(state, summary, trial)
