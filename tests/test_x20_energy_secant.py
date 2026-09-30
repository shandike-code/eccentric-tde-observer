import numpy as np
import pytest
from handoff.audit_tools.decompose_x20_feedback_energy import secant_components


def test_signed_terms_close_even_with_cancellation_and_zero_net_cell():
    a=np.array([4.,8.,10.]);b=np.array([5.,6.,10.]);ion=np.array([.5,.5,0.])
    rad=np.array([[2.,-2.,3.],[-.5,.5,-3.]])
    dq,pieces,shares=secant_components(a,b,rad,ion,np.array([1.,2.,3.]))
    np.testing.assert_allclose(dq,np.log(b/a),atol=1e-15)
    np.testing.assert_allclose(pieces.sum(axis=0),dq,atol=1e-15)
    assert np.any(shares<0) and np.sum(np.abs(shares))>1


def test_equal_states_have_no_defined_projection_fraction():
    dq,pieces,shares=secant_components(np.ones(2),np.ones(2),np.array([[1.,2.],[-1.,-2.]]),np.zeros(2),np.ones(2))
    assert shares is None and np.all(dq==0) and np.all(pieces.sum(axis=0)==0)


def test_bad_energy_book_does_not_get_renormalized():
    with pytest.raises(AssertionError):
        secant_components(np.ones(2),np.ones(2)*2,np.ones((2,2)),np.zeros(2),np.ones(2))


def test_nonpositive_gas_is_rejected():
    with pytest.raises(ValueError):
        secant_components(np.ones(2),np.zeros(2),np.ones((2,2)),np.zeros(2),np.ones(2))
