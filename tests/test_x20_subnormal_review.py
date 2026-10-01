from handoff.audit_tools.review_x20_subnormal_audit import integer_certificate


def test_integer_denominators_preserve_subnormal_negative_half():
    t = float.fromhex('0x0.0000000000001p-1022')
    r = integer_certificate([v.hex() for v in [0., t, 0., 0.]], [-1., 0., 0.])
    assert r['full'] == dict(sign=-1, numerator='-1', denominator_power_of_two=1074)
    assert r['half'] == dict(sign=-1, numerator='-1', denominator_power_of_two=1075)


def test_integer_cancellation_and_half_energy():
    r = integer_certificate([v.hex() for v in [1., 2., 0., 0.]], [-1., 0., 0.])
    assert r['full'] == dict(sign=0, numerator='0', denominator_power_of_two=0)
    assert r['half'] == dict(sign=1, numerator='1', denominator_power_of_two=1)
