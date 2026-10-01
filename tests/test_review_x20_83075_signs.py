from handoff.audit_tools.review_x20_83075_signs import integer_bound,integer_certificate


def test_independent_integer_bound_and_exact_signs():
    h=[float(x).hex() for x in (1,2,0,0)]
    assert integer_bound(h,[-4.,0.,0.])==dict(numerator='1',denominator='4',float=.25)
    assert integer_certificate(h,[-4.,0.,0.])['half']['sign']==-1
    assert integer_bound(h,[1.,0.,0.]) is None


def test_zero_anchor_forbids_positive_step_along_negative_direction():
    h=[float(x).hex() for x in (0,1,0,0)]
    assert integer_bound(h,[-1.,0.,0.])==dict(numerator='0',denominator='1',float=0.)
