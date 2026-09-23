import numpy as np
import pytest
from operations.review_step16_state_failure import source_metrics


def test_net_cancellation_can_fail_while_volume_comparison_passes():
    # Local source discrepancy remains tiny, but opposite signs cancel in the
    # physical column integral. Neither metric can stand in for the other.
    r=np.array([1000.,-999.]);o=np.array([1000.,-999.002])
    m=source_metrics(r,o,np.ones(2))
    assert m['volume_l1']<1e-3
    assert m['global_fraction']>1e-3
    assert m['absolute_over_net_scale']>1000
    assert m['absolute_integral_difference']==pytest.approx(.002)


def test_no_artificial_floor_for_zero_net_integral():
    with pytest.raises(ValueError,match='zero denominator'):
        source_metrics(np.array([1.,-1.]),np.array([1.,-1.]),np.ones(2))
