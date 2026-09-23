import numpy as np
from operations.source_split_tail_evidence import linearity_measurement


def test_small_absolute_error_is_retained_as_relative_failure():
    relative,error,scale=linearity_measurement([np.array([1e-100]),np.array([0.])],np.array([1.0001e-100]))
    assert relative>1e-12
    assert 0<error<1e-103 and 0<scale<1e-99


def test_cancelling_components_use_absolute_component_scale():
    relative,error,scale=linearity_measurement([np.array([1.]),np.array([-1.])],np.array([1e-16]))
    assert scale==2 and error==1e-16 and relative==5e-17


def test_exact_zero_is_not_replaced_by_floor():
    assert linearity_measurement([np.zeros(3)],np.zeros(3))==(0.,0.,0.)
