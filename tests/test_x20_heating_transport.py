import numpy as np
import pytest
from handoff.audit_tools.diagnose_x20_heating_transport import diagnose


def test_known_scalar_contraction_and_stationary_secant():
    a=np.array([2.,4.]);h=np.array([6.,12.]);m=np.array([1.,3.])
    z=diagnose(a,.8*a,h,.8*h,m)
    assert z['mapped_difference_over_difference']==pytest.approx(.8)
    assert z['ray_projection']==pytest.approx(.8)
    assert z['unconstrained_observed_heating_alpha']==pytest.approx(-.5)
    assert z['predicted_heating_defect_ratio']<1e-14
    assert not z['full_field_positivity_checked'] and not z['true_map_evaluated']


def test_orthogonal_defects_cannot_be_fitted_away():
    z=diagnose([0.,0.],[1.,0.],[3.,4.],[4.,6.],[1.,1.])
    assert z['defect_cosine']==0
    assert z['unconstrained_observed_heating_alpha']==0
    assert z['predicted_heating_defect_ratio']==1


def test_equal_histories_do_not_manufacture_rate_or_fit():
    z=diagnose([1.,2.],[2.,4.],[1.,2.],[2.,4.],[1.,1.])
    assert z['mapped_difference_over_difference'] is None
    assert z['unconstrained_observed_heating_alpha'] is None


def test_unit_scale_changes_norms_but_not_ratios():
    values=[np.array([2.,5.]),np.array([2.1,5.2]),np.array([4.,7.]),np.array([3.9,6.7])]
    a=diagnose(*values,[1.,2.]);b=diagnose(*(x*1e12 for x in values),[1.,2.])
    assert b['mass_norm_d_erg_g']==pytest.approx(a['mass_norm_d_erg_g']*1e12)
    for k in ('ray_projection','unconstrained_observed_heating_alpha','predicted_heating_defect_ratio'):
        assert b[k]==pytest.approx(a[k])


def test_invalid_mass_rejected():
    with pytest.raises(ValueError):
        diagnose([1.],[2.],[3.],[4.],[0.])
