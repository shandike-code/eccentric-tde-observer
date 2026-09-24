from copy import deepcopy
import numpy as np
import pytest
from operations import common_step21_direction_precision as step
from tests.test_common_step21_directions import fixture


def audit():
    return {'accepted_outer_steps':20,'pairs':{k:{'all_16_pair_gates':False,'gate_checks':{'inner_noise_resolved_pass':False}} for k in ('control','thermal04','thermal08','population04','population08')}}


@pytest.mark.parametrize('mutation',['job','state','counter','pairs','noise','accepted'])
def test_rejects_wrong_or_no_longer_noisy_provenance(mutation):
    a=audit();t={'job_id':76905,'state':'COMPLETED'};step.validate_source_audit(a,t)
    if mutation=='job':t['job_id']=76871
    if mutation=='state':t['state']='FAILED'
    if mutation=='counter':a['accepted_outer_steps']=21
    if mutation=='pairs':a['pairs'].pop('control')
    if mutation=='noise':a['pairs']['population08']['gate_checks']['inner_noise_resolved_pass']=True
    if mutation=='accepted':a['pairs']['thermal08']['all_16_pair_gates']=True
    with pytest.raises(RuntimeError):step.validate_source_audit(a,t)


@pytest.mark.parametrize('key',['encoded_state','base_residual','finite_direction','temperature_k','hydrogen_fraction','step_duration_s'])
def test_fixed_trial_refuses_even_small_changes(key):
    base,_=fixture();actual=deepcopy(base);step.same_trial(actual,base)
    actual[key]=actual[key]+1e-8
    with pytest.raises(RuntimeError):step.same_trial(actual,base)


def test_zero_authorization_does_not_leak_to_nonzero_cases():
    p={'authorization':{'accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass':True}}
    step.set_authorization(p,'thermal');step.set_authorization(p,'population')
    step.set_authorization(p,'control')
    assert not p['authorization']['accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass']
    for name in ('thermal','population'):
        with pytest.raises(RuntimeError):step.set_authorization(p,name)
    with pytest.raises(ValueError):step.set_authorization(p,'mixed')


def test_larger_budget_is_fixed_and_domain_failure_stops_remaining_direction():
    assert step.LIMITS=={'control':8,'thermal':8,'population':8}
    seen=[]
    def evaluate(n):
        seen.append(n);return 'baseline_stable' if n=='control' else 'physical_domain_rejected'
    assert step.direction_sequence(evaluate)=='stopped_at_thermal'
    assert seen==['control','thermal']


def test_latest_seed_requires_consistent_rotating_state():
    s={'current_sha256':'hash','current_slot':0,'slots':['path'], 'history':[{'output_path':'path','output_sha256':'hash'}]}
    assert step.latest_seed(s)['path']=='path'
    s['current_sha256']='other'
    with pytest.raises(RuntimeError):step.latest_seed(s)
