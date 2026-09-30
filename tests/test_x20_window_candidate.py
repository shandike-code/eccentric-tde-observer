import numpy as np
import pytest
from operations.x20_window_candidate import spectral_witness


def spectra():
    f=np.ones((8,3));f[2]=2;return f


def test_last_direction_full_half_fractions():
    g=np.eye(4);g[0,3]=g[3,0]=-1
    r=spectral_witness(g,spectra(),[0,0,.5])
    assert r['endpoints'][0]['l2_ratio']==pytest.approx(.55)
    assert r['endpoints'][1]['l2_ratio']==pytest.approx(.775)


def test_negative_spectrum_retained_as_failure():
    f=spectra();f[6]=0
    r=spectral_witness(np.eye(4),f,[0,0,2.])
    assert r['endpoints'][0]['minimum_input']<0
    assert not r['available_gates_passed']


def test_raw_cap_checked_before_safety_fraction():
    r=spectral_witness(np.eye(4),spectra(),[0,0,10.])
    assert r['raw_weight_l1']==19 and not r['checks']['raw_weight_cap']


def test_nonfinite_coefficient_rejected():
    with pytest.raises(ValueError,match='finite'):spectral_witness(np.eye(4),spectra(),[0,0,np.nan])
