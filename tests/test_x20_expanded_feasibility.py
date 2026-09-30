import itertools
from decimal import Decimal,localcontext
import numpy as np
import pytest
from operations.x20_expanded_feasibility import cap_geometry,denominator_upper,dual_certificate,spectral_cut,solve,D


def test_cap_vertices_and_all_sign_faces():
    v,a,b=cap_geometry(4);assert v.shape==(20,4) and a.shape==(30,4)
    assert np.max(a@v.T-b[:,None])<=0
    for c in v:assert np.abs(np.r_[c[0],1-sum(c),c[1:]]).sum()==17


def test_denominator_upper_bounds_exact_affine_extrema():
    sys=dict(base=np.array([1.,2.]),r=np.array([.2,-.1]),di=np.array([[.1,.2,-.3,.2],[.4,-.5,.6,-.1]]),dr=np.array([[.2,-.1,.3,.1],[-.1,.3,.1,-.2]]))
    row=denominator_upper(sys,.9);v,_,_=cap_geometry(4)
    with localcontext() as ctx:
        ctx.prec=70;t=D(.9);answers=[]
        for c in v:
            incoming=sum(map(D,sys['base']))+t*sum(D(x)*sum(map(D,col)) for x,col in zip(c,sys['di'].T))
            outgoing=incoming+sum(map(D,sys['r']))+t*sum(D(x)*sum(map(D,col)) for x,col in zip(c,sys['dr'].T))
            answers.extend([incoming,outgoing])
        assert Decimal(row['maximum_70digit'])==max(answers) and D(row['upper'])>=max(answers)


def test_dual_bound_known_quadratic_minimum():
    # q=1+0.81||c||²，真实极小为1；任意非零点支撑面下界不可冒充该点值。
    _,a,b=cap_geometry(4);g=np.eye(5)
    center=dual_certificate(g,np.zeros(4),a,b)
    away=dual_certificate(g,np.array([.2,.1,-.1,.05]),a,b)
    assert 0.999999999999<center['l2_lower']<=1
    assert Decimal(away['squared_lower_70digit'])<1<Decimal(away['squared_value_70digit'])


def test_cut_is_necessary_at_known_feasible_points():
    sys=dict(r=np.array([.05,-.05]),dr=np.array([[.1,.2,0.,.1],[-.1,.1,.2,.05]]),di=np.zeros((2,4)),base=np.array([.5,.5]),limit=.11)
    cut=spectral_cut(sys,np.array([3.,2.,1.,.2]),.9,1.)
    assert cut['relaxed_ratio']>1
    for c in itertools.product((-.1,0,.1),repeat=4):
        c=np.array(c);n=np.abs(sys['r']+.9*sys['dr']@c).sum()
        if n<=.11:assert np.array(cut['a'])@c<=cut['b']+1e-14


def test_impossible_quadratic_returns_valid_exclusion():
    spectra=np.array([[1.,1.],[1.,1.],[1.01,1.],[1.,1.],[1.,1.],[1.,1.]])
    result=solve(np.eye(5),spectra,pairs=((0,1),(3,4),(4,5),(3,5)),maximum_iterations=2)
    assert result['status']=='no_20pct_candidate_in_full_registered_cap'
    assert len(result['trace'])==1 and result['trace'][0]['certificate']['l2_lower']>.8


def test_nonconvex_gram_rejected():
    with pytest.raises(ValueError,match='convex'):solve(np.diag([1,1,1,1,-1]),np.ones((6,2)),pairs=((0,1),(3,4),(4,5),(3,5)))


def test_positive_lp_multiplier_cannot_raise_certificate_above_true_minimum(monkeypatch):
    from types import SimpleNamespace
    from operations import x20_expanded_feasibility as module
    _,a,b=cap_geometry(4)
    monkeypatch.setattr(module,'linprog',lambda *args,**kwargs:SimpleNamespace(success=True,message='synthetic inexact dual',ineqlin=SimpleNamespace(marginals=np.full(len(b),1e-8))))
    result=dual_certificate(np.eye(5),np.array([.2,.1,-.1,.05]),a,b)
    assert result['positive_raw_dual_indices']==list(range(len(b)))
    assert all(y<=0 for y in result['dual_multipliers'])
    assert Decimal(result['residual_box_correction_70digit'])>0
    assert Decimal(result['squared_lower_70digit'])<1


def test_pair_mapping_keeps_long_chord_distinct():
    from operations.x20_expanded_feasibility import system
    f=np.array([[2.,1.],[3.,2.],[5.,3.],[7.,4.],[11.,5.],[13.,6.],[17.,7.],[19.,8.]])
    z=system(f,((0,1),(3,4),(4,5),(6,7)))
    np.testing.assert_array_equal(z['dr'][:,3],((f[7]-f[6])-(f[2]-f[1]))/8.)
    np.testing.assert_array_equal(z['di'][:,3],(f[6]-f[1])/8.)


def test_nearly_dependent_positive_direction_is_not_dropped():
    from operations.x20_expanded_feasibility import positive_hessian
    g=np.diag([1.,1.,2.,3.,1e-15]);assert len(positive_hessian(g))==4
    g[-1,-1]=0
    with pytest.raises(ValueError,match='no eigenvalue clipping'):positive_hessian(g)


def test_mismatched_dimension_is_rejected():
    with pytest.raises(ValueError,match='invalid Gram'):solve(np.eye(4),np.ones((8,2)),((0,1),(3,4),(4,5),(6,7)))
