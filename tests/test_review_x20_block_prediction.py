import numpy as np
import pytest

from handoff.audit_tools.review_x20_block_window_prediction import expected_from_basis
from handoff.audit_tools.review_x20_window_prediction import reduce_prediction


def test_independent_gram_and_boundary_use_each_blocks_rounded_coefficients():
    rows = []
    fields = np.array([2., 2.1, 3., 3.15, 4., 4.2, 5., 5.25])
    residuals = fields[1::2] - fields[::2]
    basis = np.r_[residuals[0], residuals[1:] - residuals[0]]
    for n in range(5):
        rows.append(dict(first_group=n*32, group_count=32, block=n//4,
                         gram=(32*np.outer(basis, basis)).tolist(),
                         boundary_spectra=np.repeat(fields[:, None], 32, axis=1).tolist()))
    c = [[.1, .2, -.1], [-.3, .4, .2]]
    actual = expected_from_basis(rows, c)
    expected_sq = np.zeros(3)
    expected_flux = np.zeros(6)
    for n in range(5):
        for i, factor in enumerate((0, 1, .5)):
            x = fields[0] + factor*np.dot(c[n//4], fields[2::2]-fields[0])
            y = fields[1] + factor*np.dot(c[n//4], fields[3::2]-fields[1])
            expected_sq[i] += 32*(y-x)**2
            expected_flux[2*i:2*i+2] += 32*np.array([x, y])
    np.testing.assert_allclose(actual['squared_l2'], expected_sq, rtol=1e-13)
    np.testing.assert_allclose(actual['boundary_flux'], expected_flux, rtol=1e-13)
    rows[4]['block'] = 0
    with pytest.raises(AssertionError):
        expected_from_basis(rows, c)


def test_negative_field_is_rejected_without_assigning_other_gates():
    row = dict(first_group=0, group_count=32, squared_l2=[1., .1, .3],
               linf=[1., .1, .3], scales=[1., 1., 1.], minima=[-1., 0., 0., 0.],
               boundary_flux=[1.]*6, boundary_l1_numerator=[.1]*3, boundary_signed=[0.]*3)
    result = reduce_prediction([row])
    assert result == dict(passed=False, checks=dict(full_field_nonnegative=False))


def test_positive_candidate_can_fail_a_science_gate():
    row = dict(first_group=0, group_count=32, squared_l2=[1., .81, .9],
               linf=[1., .9, .95], scales=[1e5]*3, minima=[0.]*4,
               boundary_flux=[1.]*6, boundary_l1_numerator=[1e-5]*3, boundary_signed=[0.]*3)
    result = reduce_prediction([row])
    assert result['checks']['full_field_nonnegative'] is True
    assert result['checks']['full_l2_benefit'] is False
    assert result['passed'] is False
