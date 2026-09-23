import numpy as np
import pytest
from operations.frequency_boundary_integral import boundary_integrals


def case(doppler):
    le=np.array([1.,2.,4.,8.]);ce=np.array([1.,2.5,3.5,9.])
    d=np.array([[doppler],[1.]])
    lab=np.broadcast_to(np.array([2.,5.,11.])[:,None,None],(3,2,1)).copy()
    coeff=np.array([[3.],[7.],[13.]])
    return lab,le,ce,d,coeff,coeff*2,coeff*3,coeff*0+4


@pytest.mark.parametrize('d',[.8,1.,1.2])
def test_signed_strip_matches_independent_union_of_breakpoints(d):
    args=case(d);r=boundary_integrals(*args,3.)
    lab,le,ce,_,a,e,s,j=args
    lo,hi=sorted((3.,3*d));points=sorted(set([lo,hi]+[x for x in ce if lo<x<hi]+[x for x in d*le if lo<x<hi]))
    expected=np.zeros(3)
    for left,right in zip(points[:-1],points[1:]):
        mid=(left+right)/2;k=np.searchsorted(ce,mid)-1;f=np.searchsorted(le,mid/d)-1
        intensity=d**3*lab[f,0,0]
        expected+=np.sign(d-1)*(right-left)*np.array([a[k,0]*intensity,-e[k,0],s[k,0]*(intensity-j[k,0])])
    np.testing.assert_allclose([r[k][0,0] for k in r],expected,rtol=2e-14,atol=1e-13)
    assert all(r[k][1,0]==0 for k in r)


def test_out_of_domain_is_rejected_not_clipped():
    with pytest.raises(ValueError,match='coefficient domain'):
        boundary_integrals(*case(4.),3.)
