from fractions import Fraction
import numpy as np
import pytest
from operations import diagnose_step21_affine_tail as tail


def unpack(record):
    return Fraction(int(record['numerator']), int(record['denominator']))


def test_exact_sign_survives_a_negative_result_below_float64_range():
    tiny = np.nextafter(0., 1.)
    record = tail.exact_cell([0., tiny, 0., tiny], [-1., 0.], .125, 'q')
    assert unpack(record['value']) == -Fraction.from_float(tiny)/8
    assert record['value']['sign'] == -1 and float(unpack(record['value'])) == 0.
    assert record['no_positive_eta_on_this_ray']
    assert unpack(record['positive_eta_upper_bound']) == 0


def test_exact_bound_has_known_analytic_value():
    record = tail.exact_cell([0., 0., 2., 3.], [2., 0.], 1., 'q')
    assert unpack(record['value']) == -2 and unpack(record['positive_eta_upper_bound']) == Fraction(1, 2)
    assert not record['no_positive_eta_on_this_ray']
    boundary = tail.exact_cell([0., 0., 2., 3.], [2., 0.], .5, 'q')
    assert boundary['value']['sign'] == 0


def test_prediction_witness_uses_shifted_basis_and_hex_is_lossless():
    record = tail.exact_cell([1., 2., 3., 4.], [.5, .25], .5, 'p')
    assert unpack(record['value']) == Fraction(7, 2)
    assert list(map(float.fromhex, record['inputs_hex'])) == [1., 2., 3., 4.]
    assert list(map(float.fromhex, record['uv_hex'])) == [.5, .25]


def test_slab_negative_counts_and_exact_witnesses_preserve_inputs():
    values = [np.full((2, 4, 3), v) for v in (0., 0., 2., 3.)]
    before = [x.tobytes() for x in values]
    report = tail.inspect_slab(values, [2., 0.], 1., 9424)
    assert report['fields']['q']['native_negative_count'] == 24
    assert report['fields']['q']['extended_negative_count'] == 24
    assert report['fields']['q']['exact_witnesses'][0]['value']['sign'] == -1
    assert report['fields']['q']['exact_witnesses'][0]['index'] == [9424, 0, 0]
    assert report['fields']['p']['native_negative_count'] == 0
    assert [x.tobytes() for x in values] == before


@pytest.mark.parametrize('bad', ['nan', 'negative', 'label', 'eta'])
def test_invalid_witness_rejected(bad):
    values = [1., 2., 3., 4.]; label = 'q'; eta = 1.
    if bad == 'nan': values[0] = np.nan
    if bad == 'negative': values[0] = -1
    if bad == 'label': label = 'wrong'
    if bad == 'eta': eta = 0.
    with pytest.raises(ValueError):
        tail.exact_cell(values, [1., 1.], eta, label)


def test_mismatched_slabs_rejected():
    with pytest.raises(ValueError):
        tail.inspect_slab([np.ones((2, 4, 3))]*3+[np.ones((1, 4, 3))], [1., 1.], 1., 0)
