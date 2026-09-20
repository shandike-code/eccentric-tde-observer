from copy import deepcopy
import numpy as np
import pytest
from operations.material_direction_diagnostic import latest_pair, common_direction, secant_diagnostic


def test_linear_response_has_identical_finite_secants():
    b=np.ones(8);v=np.arange(8.)/8;a=.125
    r=secant_diagnostic(b,b+a*v,b+2*a*v,np.ones(2),a)
    assert r['relative_secant_disagreement']==0
    assert r['secant_cosine']==pytest.approx(1)
    assert r['half_finite_secant_merit_slope']['l2_squared']==pytest.approx(2*b@v)


def test_quadratic_response_is_not_misreported_as_a_single_derivative():
    b=np.ones(8);a=.125
    r=secant_diagnostic(b,b+a*a,b+4*a*a,np.array([1.,2.]),a)
    assert r['relative_secant_disagreement']==pytest.approx(.5)
    assert r['second_difference_l2']>0


@pytest.mark.parametrize('mass,alpha',[(np.array([0.,1.]),.1),(np.ones(2),0),(np.ones(2),np.nan)])
def test_invalid_scales_are_rejected(mass,alpha):
    with pytest.raises(ValueError):secant_diagnostic(np.ones(8),np.ones(8)*2,np.ones(8)*3,mass,alpha)


def test_zero_secant_is_not_given_a_floor():
    with pytest.raises(ValueError,match='zero secant'):
        secant_diagnostic(np.ones(8),np.ones(8),np.ones(8)*2,np.ones(2),.1)


def test_pair_after_eight_maps_uses_seventh_and_eighth_inputs():
    history=[{'input_path':str(i),'input_sha256':'h'+str(i)} for i in range(8)]
    pair={'endpoints':[7,8], 'endpoints_claim':{'previous':{'path':'6','sha256':'h6'},'final':{'path':'7','sha256':'h7'}}}
    s={'status':'diagnostic_round_complete','history':history,'diagnostic':{'rounds':[{},pair]}}
    assert latest_pair(s) is pair
    s['diagnostic']['rounds'][-1]['endpoints_claim']['final']['path']='1'
    with pytest.raises(ValueError,match='lineage'):latest_pair(s)


def test_direction_comparison_allows_only_the_two_declared_material_amplitudes():
    half={k:np.ones(8) for k in ('base_encoded_state','finite_direction','base_residual','density_g_cm3')}
    half.update(phase_index=np.array(1367),step_duration_s=np.array(889.),relaxation=np.array(.001953125))
    half['encoded_state']=half['base_encoded_state']+.001953125*half['finite_direction']
    full=deepcopy(half);full['relaxation']=np.array(.00390625)
    full['encoded_state']=full['base_encoded_state']+.00390625*full['finite_direction']
    common_direction(half,full)
    full['step_duration_s']+=1
    with pytest.raises(ValueError,match='physics changed'):common_direction(half,full)
