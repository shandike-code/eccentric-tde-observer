import numpy as np
import pytest
from handoff.audit_tools.diagnose_x20_85889_frequency import ownership, projection


def test_signed_projection_keeps_cancellation():
    parts=np.array([[3.,6.],[-2.,-4.]])
    np.testing.assert_allclose(projection(parts,parts.sum(0),np.array([1.,2.])),[3.,-2.])


def test_zero_total_has_no_invented_fraction():
    assert projection(np.array([[1.,2.],[-1.,-2.]]),np.zeros(2),np.ones(2)) is None


@pytest.mark.parametrize('intervals',[[(0,2),(1,4)],[(0,1),(2,4)],[(0,2),(2,5)]])
def test_bad_ownership_rejected(intervals):
    rows=[dict(block_index=i,core_group_start=a,core_group_stop=b) for i,(a,b) in enumerate(intervals)]
    with pytest.raises(ValueError):ownership(rows,4)


def test_exact_partition_and_reordered_blocks():
    rows=[dict(block_index=i,core_group_start=2*i,core_group_stop=2*i+2) for i in range(2)]
    np.testing.assert_array_equal(ownership(rows,4),np.ones(4))
    with pytest.raises(ValueError):ownership(rows[::-1],4)


@pytest.mark.parametrize('mass',[[0.,1.],[np.nan,1.]])
def test_invalid_mass_rejected(mass):
    with pytest.raises(ValueError):projection(np.ones((2,2)),np.ones(2),np.array(mass))
