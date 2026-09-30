import numpy as np
import pytest
from handoff.audit_tools.review_x20_matched_proposal import quadratic_minimum,boundary


def test_unbounded_line_can_exclude_all_coefficients():
    r=quadratic_minimum([[1.,.1],[.1,1.]])
    assert r['unconstrained_alpha']==pytest.approx(-.1) and r['all_real_alpha_cannot_reach_0_8']


def test_perfect_predicted_correction_is_not_excluded():
    r=quadratic_minimum([[1.,1.],[1.,1.]])
    assert r['unconstrained_minimum_l2_ratio']==0 and not r['all_real_alpha_cannot_reach_0_8']


def test_impossible_gram_rejected():
    with pytest.raises(ValueError):quadratic_minimum([[1.,2.],[2.,1.]])


def test_spectral_cancellation_is_not_l1_zero():
    r=boundary(np.array([2.,2.]),np.array([3.,1.]))
    assert r['boundary_bolometric']==0 and r['boundary_l1']==.5
