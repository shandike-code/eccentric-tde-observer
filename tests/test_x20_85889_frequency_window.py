import numpy as np
import pytest
from handoff.audit_tools.diagnose_x20_85889_frequency_window import inner, describe


def test_signed_cancellation_and_mass_weights():
    p=np.array([[3.,6.],[-2.,-4.]])
    d=describe(p,np.array([1.,3.]))
    np.testing.assert_allclose(d['signed_projection'],[3,-2])
    assert d['sum_block_norm_over_total_norm']==5
    assert inner(p.sum(0),p.sum(0),np.array([1.,3.]))==3.25


def test_zero_vector_has_no_projection():
    d=describe(np.array([[1.,2.],[-1.,-2.]]),np.ones(2))
    assert d['signed_projection']==[None,None]
    assert d['sum_block_norm_over_total_norm'] is None


@pytest.mark.parametrize('mass',[[0.,1.],[1.,float('nan')]])
def test_reject_bad_mass(mass):
    with pytest.raises(ValueError):inner([1.,2.],[1.,2.],mass)


def test_four_endpoint_identity_keeps_signs():
    a8=np.array([[1.,3.],[-2.,1.]])
    a16=np.array([[2.,2.],[-1.,0.]])
    h8=np.array([[4.,2.],[-3.,5.]])
    h16=np.array([[3.,1.],[-2.,7.]])
    np.testing.assert_array_equal((h16-a16)-(h8-a8),(h16-h8)-(a16-a8))
    assert np.any((h16-a16)-(h8-a8)<0)


def test_different_secants_do_not_share_block_identity():
    # 同一四端点log总差可望远镜消去，但不同g的逐块归因不是线性坐标。
    from handoff.audit_tools.diagnose_x20_85889_energy import log_secant
    a8,a16,h8,h16=map(np.array,([2.],[3.],[5.],[7.]))
    g8=log_secant(a8,h8);g16=log_secant(a16,h16)
    assert g8!=g16
    np.testing.assert_allclose(g16*(h16-a16)-g8*(h8-a8),np.log(h16/a16)-np.log(h8/a8))


def test_preserve_small_product_order():
    from handoff.audit_tools.diagnose_x20_85889_frequency_window import log_parts
    g=np.array([1.e-13]); dt=889.419892762322
    dq=np.array([[-7.11e-300]]); rho=np.array([5.e-11])
    actual=log_parts(g,dt,dq,rho)
    np.testing.assert_array_equal(actual,g[None,:]*dt*dq/rho[None,:])
    assert not np.array_equal(actual,g[None,:]*(dt*dq/rho[None,:]))
