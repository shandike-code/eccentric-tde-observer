import numpy as np
import pytest
from handoff.audit_tools.analyze_step21_material_direction_cone import positive_interval,norm_gradients

def test_opposing_merits_have_no_positive_combination():
    r=positive_interval([[-1,2],[2,-1]])
    assert not r['feasible'] and r['lower']==2/3 and r['upper']==1/3

def test_overlap_has_strict_descent_witness():
    g=np.array([[-2,1],[1,-2]]);r=positive_interval(g)
    assert r['feasible'] and np.all(g@r['witness']<0)

def test_zero_slope_is_not_strict_descent():
    assert not positive_interval([[0,0]])['feasible']
    assert positive_interval([[-1,-1]])['feasible']

def test_squared_norm_gradient_and_tied_active_cells():
    c=np.array([[1.,2,3,4],[1.,2,3,4]]);d=np.array([[.1,.2,.3,.4],[-.2,.1,.2,-.1]])
    g,labels,active=norm_gradients(c,c+d,c-2*d,[1.,3.]);assert active==[0,1]
    np.testing.assert_allclose(g[:,1],-2*g[:,0],rtol=1e-14,atol=1e-14)
    for i in range(2):assert abs(g[i,0]-2*np.sum(c*d*(np.array([.25,.75])[:,None] if i else 1)))<1e-14

@pytest.mark.parametrize('g',[[[1,np.nan]],[[1,2,3]]])
def test_invalid_gradients_refused(g):
    with pytest.raises(ValueError):positive_interval(g)
