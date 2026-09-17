import pytest
from operations.confirm_inner_threshold import eligible


def inputs():
    return ({'candidate_relaxation':.03125,'radiation_threshold':2.5e-4},
        {'status':'diagnostic_round_complete','history':[{'residual':3.2e-4}]*32},
        {'gate_checks':{k:True for k in ['last_two_atomic_heating_pass',
        'last_two_direct_heating_pass','last_two_formal_heating_pass']}})


def test_current_bounded_confirmation_is_eligible():
    eligible(*inputs())


@pytest.mark.parametrize('change', ['accepted','too_far','already_passed','unstable','partial','repeated'])
def test_different_science_state_requires_a_new_decision(change):
    cfg,state,summary=inputs()
    if change=='accepted':state['status']='one_material_trial_accepted'
    if change=='too_far':state['history'][-1]={'residual':.001}
    if change=='already_passed':state['history'][-1]={'residual':.0002}
    if change=='unstable':summary['gate_checks']['last_two_atomic_heating_pass']=False
    if change=='partial':state['active_map']={'iteration':33}
    if change=='repeated':state['history']=state['history'][:8]
    with pytest.raises(RuntimeError):eligible(cfg,state,summary)
