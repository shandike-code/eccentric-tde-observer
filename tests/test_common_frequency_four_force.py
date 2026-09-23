import numpy as np
import pytest
from operations.common_frequency_four_force import common_frequency_four_force as force
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S as C


def fixture(beta):
    mu,w=np.polynomial.legendre.leggauss(4);beta=np.array([beta,-beta/2])
    le=np.array([.1,1.,2.,3.,4.,6.,10.]);ce=np.array([.1,1.7,2.3,3.5,4.2,10.])
    lab=np.broadcast_to(np.array([1,3,2,7,4,8.])[:,None,None],(6,4,2)).copy()
    chi=np.broadcast_to(np.array([2,9,1,6,4.])[:,None],(5,2)).copy()
    eta=np.broadcast_to(np.array([8,3,10,2,7.])[:,None],(5,2)).copy()
    return lab,le,ce,chi,eta,mu,w,beta


def oracle(args,window):
    lab,le,ce,chi,eta,mu,w,b=args;energy=np.zeros(2);momentum=np.zeros(2);direct=np.zeros(2)
    for z in range(2):
        gamma=1/np.sqrt(1-b[z]**2)
        for m in range(4):
            d=gamma*(1-b[z]*mu[m]);a,bb=window
            # 独立标量oracle：按两个网格断点的并集解析积分每个常数段。
            breaks=sorted(set([a,bb]+[x for x in ce if a<x<bb]+[x for x in d*le if a<x<bb]))
            for l,r in zip(breaks[:-1],breaks[1:]):
                mid=(l+r)/2;f=np.searchsorted(le,mid/d)-1;k=np.searchsorted(ce,mid)-1
                collision=(eta[k,z]/d**2-d*chi[k,z]*lab[f,m,z])*(r-l)/d
                energy[z]+=2*np.pi*w[m]*collision;momentum[z]+=2*np.pi*w[m]*mu[m]*collision/C
                direct[z]+=2*np.pi*w[m]/d**2*(chi[k,z]*d**3*lab[f,m,z]-eta[k,z])*(r-l)
    return energy,momentum,direct


@pytest.mark.parametrize('beta',[-.35,0.,.35])
def test_discontinuous_two_grids_and_signed_velocity_against_scalar_oracle(beta):
    a=fixture(beta);r=force(*a,(1.5,4.5));energy,momentum,direct=oracle(a,(1.5,4.5))
    np.testing.assert_allclose(r['lab_energy_erg_s_cm3'],energy,rtol=4e-14,atol=1e-12)
    np.testing.assert_allclose(r['lab_momentum_dyn_cm3'],momentum,rtol=4e-14,atol=1e-20)
    np.testing.assert_allclose(r['common_formal_erg_s_cm3'],direct,rtol=4e-14,atol=1e-12)


def test_constant_fields_have_analytic_common_window_heating():
    a=list(fixture(.3));a[0][:]=2;a[3][:]=3;a[4][:]=5
    r=force(*a,(1.5,4.5));mu,w,b=a[5:];d=(1-mu[:,None]*b[None,:])/np.sqrt(1-b*b)[None,:]
    expected=2*np.pi*3*np.sum(w[:,None]*(6*d-5/d**2),axis=0)
    np.testing.assert_allclose(r['common_formal_erg_s_cm3'],expected,rtol=3e-14)


def test_comoving_window_partition_additivity():
    a=fixture(.2);all_=force(*a,(1.5,4.5));left=force(*a,(1.5,2.7));right=force(*a,(2.7,4.5))
    for k in all_:np.testing.assert_allclose(all_[k],left[k]+right[k],rtol=4e-14,atol=1e-20)


def test_window_outside_lab_domain_is_rejected():
    with pytest.raises(ValueError,match='lab domain'):force(*fixture(.35),(.1,4.5))


@pytest.mark.parametrize('value',[-1.,float('nan'),float('inf')])
def test_invalid_physical_intensity_is_rejected(value):
    a=fixture(.2);a[0][0,0,0]=value
    with pytest.raises(ValueError,match='invalid'):force(*a,(1.5,4.5))
