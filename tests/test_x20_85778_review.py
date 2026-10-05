from copy import deepcopy
import pytest
from handoff.audit_tools.review_x20_85778_prediction import measured_scope

def negative_prediction():
    row=dict(group_count=32,squared_l2=[1.,1.,1.],linf=[1.,1.,1.],scales=[1.,1.,1.],
        minima=[0.,0.,0.,0.],boundary_flux=[1.]*6,boundary_l1_numerator=[1.]*3,boundary_signed=[1.]*3)
    rows=[dict(deepcopy(row),first_group=32*j) for j in range(301)]
    rows[296]['minima'][2]=-5e-324
    p=dict(slabs=rows,passed=False,checks=dict(full_field_nonnegative=False),status='negative_field_rejected',other_gates_evaluated=False)
    return p,dict(passed=False,checks=p['checks'].copy())

def test_smallest_subnormal_negative_is_preserved():
    z=measured_scope(*negative_prediction())
    assert z['negative_slabs']==[dict(first_group=9472,minima=[0.,0.,-5e-324,0.])]
    assert set(z['checks'])=={'full_field_nonnegative'} and not z['passed']

def test_uncomputed_gates_cannot_be_reported_evaluated():
    p,s=negative_prediction();p['other_gates_evaluated']=True
    with pytest.raises(AssertionError):measured_scope(p,s)

def test_missing_or_duplicate_slab_rejected():
    p,s=negative_prediction();p['slabs'][297]=p['slabs'][296].copy()
    with pytest.raises(AssertionError):measured_scope(p,s)
