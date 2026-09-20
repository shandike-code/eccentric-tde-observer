import numpy as np
import pytest
from operations.audit_outer_contraction import decomposition


def test_signed_cell_contributions_reproduce_both_norm_gaps():
    base=np.array([[1.,2.,0.,0.],[3.,0.,0.,0.]])
    candidate=np.array([[2.,2.,0.,0.],[1.,0.,0.,0.]])
    r=decomposition(base,candidate,np.array([1.,4.]))
    np.testing.assert_allclose(r['cell_l2_excess'],[3.,-8.])
    np.testing.assert_allclose(r['cell_mass_excess'],[.6,-6.4])
    assert r['squared_l2_excess']==pytest.approx(-5.)
    assert r['squared_mass_norm_excess']==pytest.approx(-5.8)
    assert sum(r['component_cross_terms'])+sum(r['component_quadratic_terms'])==pytest.approx(-5.)


def test_mass_measure_can_reverse_the_l2_verdict_without_changing_cells():
    b=np.array([[1.,0.,0.,0.],[3.,0.,0.,0.]])
    c=np.array([[2.,0.,0.,0.],[1.,0.,0.,0.]])
    r=decomposition(b,c,np.array([10.,1.]))
    assert r['candidate_over_base']['l2']<1
    assert r['candidate_over_base']['mass_weighted']>1


def test_equal_norm_opposite_vectors_keep_cross_and_quadratic_information():
    b=np.ones((2,4));r=decomposition(b,-b,np.ones(2))
    assert r['squared_l2_excess']==0
    assert sum(r['component_cross_terms'])==-32
    assert sum(r['component_quadratic_terms'])==32


@pytest.mark.parametrize('mass',[np.array([0.,1.]),np.array([1.,np.nan])])
def test_invalid_mass_is_rejected(mass):
    with pytest.raises(ValueError):decomposition(np.ones((2,4)),np.ones((2,4)),mass)


def test_zero_baseline_is_not_replaced_by_a_floor():
    with pytest.raises(ValueError,match='positive'):decomposition(np.zeros(8),np.ones(8),np.ones(2))
