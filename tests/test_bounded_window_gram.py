from fractions import Fraction as F
import pytest
from handoff.audit_tools.bounded_window_gram import exact_qp


def gram(target):
    t=list(map(F,target));return [[sum(x*x for x in t),*[-x for x in t]]]+[[-t[i]]+[F(i==j) for j in range(3)] for i in range(3)]


def test_interior_solution_and_exact_dual_gap():
    t=[F(1,5),F(-1,10),F(3,10)];r=exact_qp(gram(t));assert r['coefficients']==t and r['value']==0 and r['gap']==0


def test_boundary_solution_respects_affine_weight_cap():
    r=exact_qp(gram([-20,0,0]));assert r['coefficients']==[-8,0,0] and r['value']==144 and r['gap']==0


def test_zero_gram_keeps_zero_anchor():
    r=exact_qp([[0]*4 for _ in range(4)]);assert r['status']=='exact_zero_gram' and r['value']==0


def test_degenerate_direction_is_not_regularized():
    g=gram([1,0,0]);g[2][2]=0
    with pytest.raises(ValueError,match='Hessian'):exact_qp(g)


def test_indefinite_stored_gram_is_rejected():
    g=gram([1,2,3]);g[0][0]-=F(1,100)
    with pytest.raises(ValueError,match='Schur'):exact_qp(g)
