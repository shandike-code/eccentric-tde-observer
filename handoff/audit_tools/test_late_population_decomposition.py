import numpy as np
import pytest
from handoff.audit_tools.decompose_late_population_drift import split_change, log_secant


def test_common_drift_cancels_without_scalar_norm_subtraction():
    mass=np.array([1.,3.]);old=np.arange(8,dtype=float);step=np.array([2.,-1.,0.,0.,0.,0.,0.,0.])
    record,signal=split_change(old+step,old,2*old+step,2*old,mass)
    np.testing.assert_array_equal(signal,np.zeros(8))
    assert all(v>0 for v in record['candidate'])
    assert record['signal']==[0.,0.,0.]


def test_opposite_drift_adds_despite_equal_norms():
    x=np.array([1.,0.,0.,0.]);zero=np.zeros(4)
    record,signal=split_change(x,zero,-x,zero,np.ones(1))
    assert record['candidate']==record['control']==[1.,1.,1.]
    assert record['signal']==[2.,2.,2.]
    np.testing.assert_array_equal(signal,2*x)


def test_log_secant_has_exact_zero_limit_and_rejects_nonpositive():
    before=np.array([2.,4.,8.]);after=np.array([2.,8.,4.])
    change,factor=log_secant(before,after)
    assert factor[0]==.5
    np.testing.assert_allclose(change,[0.,np.log(2.),-np.log(2.)])
    np.testing.assert_allclose(factor*(after-before),change)
    with pytest.raises(ValueError):log_secant(before,np.array([0.,8.,4.]))
