import numpy as np
import pytest
from handoff.audit_tools.review_x20_window_basis import minimum


def test_exact_orthogonal_minimum():
    basis=np.array([[1,2,3,4],[1,0,0,0],[0,1,0,0],[0,0,1,0]],float)
    r=minimum(basis@basis.T)
    np.testing.assert_allclose(r['alpha'],[-1,-2,-3])
    assert r['minimum_l2_ratio']==pytest.approx(4/np.sqrt(30))
    assert not r['all_real_coefficients_excluded_at_0_8']


def test_orthogonal_directions_cannot_help():
    r=minimum(np.eye(4))
    assert r['minimum_l2_ratio']==1 and r['all_real_coefficients_excluded_at_0_8']


def test_degenerate_or_indefinite_direction_not_clipped():
    g=np.eye(4);g[2,2]=0
    with pytest.raises(ValueError,match='positive definite'):minimum(g)
    g[2,2]=-1
    with pytest.raises(ValueError,match='positive definite'):minimum(g)


def test_ill_conditioned_positive_direction_retained():
    g=np.diag([1.,1.,1e-20,2.]);g[0,2]=g[2,0]=1e-11
    r=minimum(g)
    assert r['alpha'][1]==pytest.approx(-1e9)
    assert r['minimum_l2_ratio']==pytest.approx(np.sqrt(.99))
