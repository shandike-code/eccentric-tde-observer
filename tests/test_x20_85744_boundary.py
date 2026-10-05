from fractions import Fraction as F
import pytest
from handoff.audit_tools.solve_x20_85744_boundary import surface_model,surface_check,fit

def model():
    # 锚点总量相同但谱形变化；第二对没有谱形变化，第三对含净通量增量。
    f=[[2.,2.],[3.,1.],[3.,1.],[3.,1.],[2.,2.],[4.,2.],[2.,2.],[3.,1.]]
    return surface_model(dict(slabs=[dict(boundary_spectra=f)]))

def test_zero_bolometric_gate_keeps_nonzero_spectral_l1():
    m=model();z=surface_check(m,[F(0)]*3)
    assert z['l1']==F(1,2) and z['bolometric']==0
    assert z['l1_pass'] and z['bolometric_pass']

def test_spectral_cancellation_checked_before_normalization():
    z=surface_check(model(),[F(1,2),F(0),F(0)])
    assert z['l1']==F(1,4) and z['l1_pass']

def test_new_bolometric_change_cannot_pass_zero_anchor():
    z=surface_check(model(),[F(0),F(1,4),F(0)])
    assert not z['bolometric_pass'] and not z['branch_pass']

def test_negative_spectrum_reported_not_floored():
    z=surface_check(model(),[F(3),F(0),F(0)])
    assert not z['spectra_nonnegative']

def test_nonpositive_denominator_rejected():
    m=model();m['den']=[F(0)]*4
    with pytest.raises(ValueError,match='denominator'):surface_check(m,[F(0)]*3)
