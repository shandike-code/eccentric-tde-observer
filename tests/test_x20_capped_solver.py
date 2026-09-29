import copy,json
from pathlib import Path
import numpy as np
import pytest
from operations.x20_capped_solver import solve
from handoff.audit_tools.review_x20_subspace import quadratic_bound,reduce_prediction


def test_joint_cap_solution_and_support_bound_known_quadratic():
    # q=1+||c-target||^2，等式c0=0；目标在cap外，因此最优在cap边界。
    target=np.array([2.,4.,0.]);g=np.eye(4);g[0,0]=1+target@target;g[0,1:]=g[1:,0]=-target
    c,r=solve(g,[0,1,0,0],cap=3)
    np.testing.assert_allclose(c,[0,2,0],atol=1e-13)
    assert r['squared_upper']==pytest.approx(9/21)
    assert r['squared_support_lower']==pytest.approx(r['squared_upper'],abs=1e-12)


def test_infeasible_or_unresolved_equality_rejected():
    with pytest.raises(ValueError,match='no point'):solve(np.eye(4),[100,1,0,0])
    g=np.diag([1,1,1,1e-15])
    with pytest.raises(ValueError,match='resolved'):solve(g,[0,1,0,0])


def test_cap_only_bound_contains_known_optimum():
    g=np.eye(4);r=quadratic_bound(g)
    assert r['l2_upper']==pytest.approx(1) and r['l2_conservative_lower']<=1


def test_actual_result_and_mutations():
    path=Path('outputs/review-20260925/x20-subspace-80862-received/prediction.json')
    if not path.exists():pytest.skip('Mac received artifact')
    p=json.loads(path.read_text());r=reduce_prediction(p)
    c,s=solve(p['gram'],p['boundary_coefficients'])
    assert .777<s['l2_ratio']<.779 and abs(s['squared_upper']-s['squared_support_lower'])<1e-8
    np.testing.assert_allclose(c,r['joint_cap_boundary_certificate']['coefficients'],rtol=2e-9,atol=0)
    assert s['l2_ratio']==pytest.approx(r['joint_cap_boundary_certificate']['l2_ratio'],rel=1e-10)
    assert r['checks']['full_l2_benefit'] is False
    bad=copy.deepcopy(p);bad['system_slabs'].pop()
    with pytest.raises(AssertionError):reduce_prediction(bad)
    bad=copy.deepcopy(p);bad['bounds']['selected_fraction']*=2
    with pytest.raises(AssertionError):reduce_prediction(bad)
