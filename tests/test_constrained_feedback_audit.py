import numpy as np
import pytest
from operations.audit_constrained_feedback import direction_geometry


def test_positive_secant_cannot_be_made_descending_by_shorter_positive_step():
    b=np.arange(1.,9.);r=direction_geometry(b,b*1.1,b,np.array([1.,2.]),.1)
    assert r['finite_secant_l2_squared_slope']==pytest.approx(2*(b@b))
    assert not r['secant_model_positive_step_can_decrease_l2']
    assert not r['secant_model_positive_step_can_decrease_mass']


def test_negative_secant_is_diagnostic_and_retains_direction_sign():
    b=np.ones(8);r=direction_geometry(b,b*.9,-b,np.ones(2),.1)
    assert r['old_direction_vs_current_response_cosine']==pytest.approx(-1)
    assert r['secant_model_positive_step_can_decrease_l2']
    assert 'not the exact' in r['limitation']


@pytest.mark.parametrize('mass,alpha',[(np.array([0.,1.]),.1),(np.ones(2),0),(np.ones(2),np.nan)])
def test_invalid_scales_rejected(mass,alpha):
    with pytest.raises(ValueError): direction_geometry(np.ones(8),np.ones(8)*2,np.ones(8),mass,alpha)


def test_zero_direction_is_not_regularized():
    with pytest.raises(ValueError,match='zero direction'):
        direction_geometry(np.ones(8),np.ones(8)*2,np.zeros(8),np.ones(2),.1)
