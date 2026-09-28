import numpy as np
import pytest
from operations.boundary_constrained_proposal import constrained_coefficients,gram_stats,residual_basis,proposal_fields,boundary_spectrum


def test_exact_constrained_quadratic_minimum_in_box():
    # ||[1,a,b]||^2，约束a+b=1；唯一最小点a=b=1/2。
    c=constrained_coefficients(np.eye(3),[-1,1,1])
    assert c['a']==c['b']==.5 and c['predicted_squared_l2']==1.5
    assert c['predicted_signed_flux']==0


def test_endpoint_minimum_and_empty_intersection():
    g=np.diag([1.,100.,1.])
    c=constrained_coefficients(g,[-1,1,1])
    assert np.isclose(c['a'],1/101) and np.isclose(c['b'],100/101)
    with pytest.raises(ValueError,match='empty'):constrained_coefficients(g,[-3,1,1])
    with pytest.raises(ValueError):constrained_coefficients(np.diag([1,-1,1]),[-1,1,1])
    with pytest.raises(ValueError):constrained_coefficients(g,[0,1,0])


def test_gram_keeps_signed_cross_terms_and_all_cells():
    v=[np.array([1.,2.,3.]),np.array([2.,-1.,0.]),np.array([0.,2.,-4.])]
    np.testing.assert_array_equal(gram_stats(v),np.array(v)@np.array(v).T)
    assert gram_stats(v)[0][2]<0


def test_half_uses_original_and_no_unselected_subnormal_underflow():
    x=np.ones((32,2,3));q=2*x;u=q.copy();op=lambda z:2*z+1
    arrays=(x,op(x),q,op(q),u,op(u))
    z,p,h,ph=proposal_fields(34*128,arrays,.4,.8)
    np.testing.assert_allclose(z,1.4*x);np.testing.assert_allclose(p,op(z));np.testing.assert_allclose(h,1.2*x)
    np.testing.assert_allclose(ph,op(h));assert not np.array_equal(h,.5*q+.5*z)
    tiny=np.full_like(x,np.nextafter(0.,1.))
    z,p,h,ph=proposal_fields(0,(tiny,op(tiny),tiny,op(tiny),tiny,op(tiny)),.4,.8)
    assert np.array_equal(z,tiny) and np.array_equal(h,tiny)
    with pytest.raises(ValueError,match='support'):proposal_fields(0,arrays,.4,.8)


def test_affine_basis_reconstructs_operator_with_neighbor_coupling():
    x=np.ones((32,2,3));q=x.copy();u=2*x
    op=lambda z:.25*z+.05*np.roll(z,1,axis=0)+1
    aa=(x,op(x),q,op(q),u,op(u));r=residual_basis(*aa)
    z,p,h,ph=proposal_fields(20*128,aa,.4,.8)
    np.testing.assert_allclose(p,op(z));np.testing.assert_allclose(p-z,r[0]+.4*r[1]+.8*r[2])


def test_boundary_includes_only_both_outgoing_surfaces_with_width():
    a=np.ones((2,2,3));mu=np.array([-.5,.5]);w=np.array([1.,1.]);width=np.array([2.,3.])
    a[:,0,-1]=100.;a[:,1,0]=100.  # incoming rays must not enter outgoing flux
    np.testing.assert_allclose(boundary_spectrum(a,mu,w,width),2*np.pi*width)
