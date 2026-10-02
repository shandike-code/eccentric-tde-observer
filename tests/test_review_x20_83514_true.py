import copy
import numpy as np
import pytest
from handoff.audit_tools.review_x20_83514_true import norms

def rows():
    return [dict(first_group=32*i,group_count=32,squared_l2=[1.,.25,.64,0.],linf=[1.,.5,.8,0.]) for i in range(301)]

def test_reduces_all_slabs_and_keeps_affinity_separate():
    ss,top,l2,linf=norms(rows(),4)
    np.testing.assert_allclose(ss,[301,75.25,192.64,0],rtol=1e-15)
    np.testing.assert_allclose(l2,[1,.5,.8,0],rtol=1e-15)
    assert l2[3]==0 and l2[1]>.0

@pytest.mark.parametrize('damage',['missing','duplicate','nan','negative'])
def test_rejects_incomplete_or_invalid_statistics(damage):
    r=rows()
    if damage=='missing':r.pop()
    elif damage=='duplicate':r[2]['first_group']=32
    elif damage=='nan':r[0]['squared_l2'][1]=float('nan')
    else:r[0]['squared_l2'][1]=-1
    with pytest.raises(AssertionError):norms(r,4)
