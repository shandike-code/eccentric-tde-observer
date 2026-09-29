from decimal import localcontext
import copy
import numpy as np
import pytest
from handoff.audit_tools.review_x20_fullspace import cap_halfspaces,enumerate_vertices,numbers,RUN,SOURCE,read,arrays


def test_independent_three_dimensional_polytope_has_twelve_vertices():
    with localcontext() as ctx:
        ctx.prec=70
        rows=[(a,b) for a,b in cap_halfspaces() if any(a)]
        vertices=enumerate_vertices([a for a,b in rows],[b for a,b in rows])
    assert len(vertices)==12
    for point in vertices:
        x=np.array(point,float);assert np.abs(np.r_[x[0],1-sum(x),x[1:]]).sum()==17


@pytest.mark.parametrize('damage',['denominator','dual','cut'])
def test_fullspace_audit_rejects_changed_evidence(damage):
    if not (RUN/'result.json').exists():pytest.skip('Mac fullspace diagnostic')
    result=copy.deepcopy(read(RUN/'result.json'));data=arrays(SOURCE/'boundary-spectra.npz')
    if damage=='denominator':result['denominator_bounds'][0]['upper']-=.01
    elif damage=='dual':result['trace'][-1]['certificate']['squared_lower_70digit']='.8'
    else:result['trace'][0]['cuts'][0]['b']-=.01
    with pytest.raises(AssertionError):numbers(data['gram'],data['spectra'],result)
