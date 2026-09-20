import numpy as np
import pytest
from operations.audit_four_map_response import block_heating_change


def test_signed_blocks_cancel_at_depth_without_being_discarded():
    a=np.zeros((2,2));b=np.array([[2.,-2.],[-1.,1.]])
    r=block_heating_change(a,b,np.array([1.,3.]),a.sum(0),b.sum(0))
    assert r['block_l1']==[8.,4.]
    assert r['block_signed_integral']==[-4.,2.]
    assert r['sum_block_l1']==12. and r['net_depth_l1']==4.
    assert r['net_over_sum_block_l1']==pytest.approx(1/3)


def test_less_absolute_change_can_produce_more_net_change():
    a=np.zeros((2,1));old=np.array([[10.],[-9.]]);new=np.array([[5.],[-3.]])
    x=block_heating_change(a,old,np.ones(1),a.sum(0),old.sum(0))
    y=block_heating_change(a,new,np.ones(1),a.sum(0),new.sum(0))
    assert y['sum_block_l1']<x['sum_block_l1'] and y['net_depth_l1']>x['net_depth_l1']


def test_zero_change_is_explicit_and_not_a_fake_ratio():
    a=np.ones((2,2));r=block_heating_change(a,a,np.ones(2),a.sum(0),a.sum(0))
    assert r['sum_block_l1']==0 and r['net_over_sum_block_l1'] is None
    assert r['closure_relative_l1']==0 and r['heating_ratio']==0


def test_formal_denominator_takes_pointwise_max_before_depth_integral():
    a=np.array([[1.,0.]]);b=np.array([[0.,1.]])
    r=block_heating_change(a,b,np.ones(2),a[0],b[0])
    assert r['heating_ratio']==1.  # max of integrated norms would incorrectly give 2.


def test_block_difference_must_close_against_independent_full_feedback():
    a=np.zeros((2,2));b=np.ones((2,2))
    with pytest.raises(ArithmeticError):block_heating_change(a,b,np.ones(2),a.sum(0),b.sum(0)+.1)


@pytest.mark.parametrize('fault',['shape','width','nan','nonpositive_width'])
def test_mismatched_measure_or_invalid_values_fail(fault):
    a=np.zeros((2,2));b=np.ones((2,2));w=np.ones(2);x=a.sum(0);y=b.sum(0)
    if fault=='shape':b=np.ones((3,2))
    if fault=='width':w=np.ones(3)
    if fault=='nan':b[0,0]=np.nan
    if fault=='nonpositive_width':w[0]=0
    with pytest.raises(ValueError):block_heating_change(a,b,w,x,y)
