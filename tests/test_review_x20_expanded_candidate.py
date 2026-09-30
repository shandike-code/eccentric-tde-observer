import copy
import numpy as np
import pytest
from handoff.audit_tools.review_x20_expanded_candidate import numbers


def test_high_precision_witness_rejects_boundary_failure_even_when_flag_says_pass():
    f=np.ones((8,3));f[2]=1.000001
    # coefficient1=5把近锚点的输入组合成大于原边界变化的状态；flag无法覆盖重算。
    raw=[0.,5.,0.,0.]
    r=dict(raw_coefficients=raw,selected_coefficients=(.9*np.array(raw)).tolist(),full_fraction=.9,half_fraction=.45,
        full_field_positivity_and_linf_evaluated=False,true_maps_evaluated=False,raw_weight_l1=9.,
        endpoints=[{},{}],available_gates_passed=True,checks=dict(fake=True))
    with pytest.raises(AssertionError):numbers(np.eye(5),f,r)
