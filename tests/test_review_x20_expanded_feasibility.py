import copy
import numpy as np
import pytest
from handoff.audit_tools.review_x20_expanded_feasibility import cap_halfspaces,cap_vertices,numbers,RUN,SOURCE,read,arrays


def test_four_dimensional_cap_geometry_has_twenty_distinct_vertices():
    vertices=cap_vertices();assert len(vertices)==len({tuple(v) for v in vertices})==20
    for v in vertices:
        assert all(sum(x*y for x,y in zip(a,v))<=b for a,b in cap_halfspaces())
        assert sum(abs(z) for z in [v[0],1-sum(v),*v[1:]])==17


@pytest.mark.parametrize('damage',['denominator','dual','cut'])
def test_independent_review_rejects_altered_certificate(damage):
    if not (RUN/'result.json').exists():pytest.skip('Mac small-data source')
    result=copy.deepcopy(read(RUN/'result.json'));data=arrays(SOURCE/'expanded-system.npz')
    if damage=='denominator':result['denominator_bounds'][0]['upper']-=.01
    elif damage=='dual':result['trace'][0]['certificate']['squared_lower_70digit']='.8'
    else:result['trace'][0]['cuts'][0]['b']-=.01
    with pytest.raises(AssertionError):numbers(data['gram'],data['spectra'],result)
