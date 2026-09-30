import numpy as np
import pytest
from operations.x20_expanded_candidate import spectral_witness


def spectra():
    # 各输入均为1；锚点输出2，第四对输出1，可单独检验第四方向真实作用。
    f=np.ones((8,3));f[2]=2;return f


def test_fourth_direction_predicts_full_and_half_at_correct_fractions():
    g=np.eye(5);g[0,4]=g[4,0]=-1
    r=spectral_witness(g,spectra(),[0,0,0,.5])
    assert r['endpoints'][0]['l2_ratio']==pytest.approx(.55)
    assert r['endpoints'][1]['l2_ratio']==pytest.approx(.775)
    assert r['selected_coefficients']==[0,0,0,.45]


def test_negative_spectrum_is_rejected_without_a_floor():
    f=spectra();f[6]=0
    r=spectral_witness(np.eye(5),f,[0,0,0,2.])
    assert not r['checks']['full_positive_spectra'] and not r['available_gates_passed']
    assert r['endpoints'][0]['minimum_input']<0


def test_raw_weight_cap_is_checked_before_fraction():
    r=spectral_witness(np.eye(5),spectra(),[0,0,0,10.])
    assert r['raw_weight_l1']==19 and not r['checks']['raw_weight_cap']


def test_nonfinite_coefficient_cannot_become_a_candidate():
    with pytest.raises(ValueError,match='finite'):spectral_witness(np.eye(5),spectra(),[0,0,0,np.nan])
