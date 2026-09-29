import itertools
from decimal import Decimal,localcontext
import numpy as np
import pytest
from operations.x20_fullspace_feasibility import cap_geometry,denominator_upper,dual_certificate,spectral_cut,solve,D


def test_cap_vertices_and_all_sign_faces():
    v,a,b=cap_geometry();assert v.shape==(12,3) and a.shape==(14,3)
    assert np.max(a@v.T-b[:,None])<=0
    for c in v:assert np.abs(np.r_[c[0],1-sum(c),c[1:]]).sum()==17


def test_denominator_upper_bounds_exact_affine_extrema():
    sys=dict(base=np.array([1.,2.]),r=np.array([.2,-.1]),di=np.array([[.1,.2,-.3],[.4,-.5,.6]]),dr=np.array([[.2,-.1,.3],[-.1,.3,.1]]))
    row=denominator_upper(sys,.9);v,_,_=cap_geometry()
    with localcontext() as ctx:
        ctx.prec=70;t=D(.9);answers=[]
        for c in v:
            incoming=sum(map(D,sys['base']))+t*sum(D(x)*sum(map(D,col)) for x,col in zip(c,sys['di'].T))
            outgoing=incoming+sum(map(D,sys['r']))+t*sum(D(x)*sum(map(D,col)) for x,col in zip(c,sys['dr'].T))
            answers.extend([incoming,outgoing])
        assert Decimal(row['maximum_70digit'])==max(answers) and D(row['upper'])>=max(answers)


def test_dual_bound_known_quadratic_minimum():
    # q=1+0.81||c||²，真实极小为1；任意非零点支撑面下界不可冒充该点值。
    _,a,b=cap_geometry();g=np.eye(4)
    center=dual_certificate(g,np.zeros(3),a,b)
    away=dual_certificate(g,np.array([.2,.1,-.1]),a,b)
    assert 0.999999999999<center['l2_lower']<=1
    assert Decimal(away['squared_lower_70digit'])<1<Decimal(away['squared_value_70digit'])


def test_cut_is_necessary_at_known_feasible_points():
    sys=dict(r=np.array([.05,-.05]),dr=np.array([[.1,.2,0.],[-.1,.1,.2]]),di=np.zeros((2,3)),base=np.array([.5,.5]),limit=.11)
    cut=spectral_cut(sys,np.array([3.,2.,1.]),.9,1.)
    assert cut['relaxed_ratio']>1
    for c in itertools.product((-.1,0,.1),repeat=3):
        c=np.array(c);n=np.abs(sys['r']+.9*sys['dr']@c).sum()
        if n<=.11:assert np.array(cut['a'])@c<=cut['b']+1e-14


def test_impossible_quadratic_returns_valid_exclusion():
    spectra=np.array([[1.,1.],[1.,1.],[1.01,1.],[1.,1.],[1.,1.],[1.,1.]])
    result=solve(np.eye(4),spectra,maximum_iterations=2)
    assert result['status']=='no_20pct_candidate_in_full_registered_cap'
    assert len(result['trace'])==1 and result['trace'][0]['certificate']['l2_lower']>.8


def test_nonconvex_gram_rejected():
    with pytest.raises(ValueError,match='convex'):solve(np.diag([1,1,1,-1]),np.ones((6,2)))


def test_positive_lp_multiplier_cannot_raise_certificate_above_true_minimum(monkeypatch):
    from types import SimpleNamespace
    from operations import x20_fullspace_feasibility as module
    _,a,b=cap_geometry()
    monkeypatch.setattr(module,'linprog',lambda *args,**kwargs:SimpleNamespace(success=True,message='synthetic inexact dual',ineqlin=SimpleNamespace(marginals=np.full(len(b),1e-8))))
    result=dual_certificate(np.eye(4),np.array([.2,.1,-.1]),a,b)
    assert result['positive_raw_dual_indices']==list(range(len(b)))
    assert all(y<=0 for y in result['dual_multipliers'])
    assert Decimal(result['residual_box_correction_70digit'])>0
    assert Decimal(result['squared_lower_70digit'])<1
