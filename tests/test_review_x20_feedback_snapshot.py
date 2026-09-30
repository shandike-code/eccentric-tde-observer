from copy import deepcopy
import pytest
from handoff.audit_tools.review_x20_feedback_snapshot import qualification,verify_pair


def pair(n=8,name='accelerated'):
    r=dict(feedback_evaluated=True,zero_pair_stable=True,physical_response_failures={},original_zero_gates={str(i):True for i in range(7)},baseline_replaced=False,accepted_material_step=False,continuation_pass=True,reason='pass')
    if n==16:r['eight_map_window']={'passed':False}
    if name=='historical':r['cross_history']={'cross_rate_pass':False}
    return r


def test_partial_evidence_never_claims_final_qualification():
    assert qualification({}, {}, False) is None
    with pytest.raises(AssertionError):qualification({}, {}, True)


def test_all_windows_and_final_cross_are_required():
    pairs={name+str(n):{'eight_map_window':{'passed':True}} for name in ('accelerated','historical') for n in (8,16)}
    cross={str(n):dict(residual_comparison={'passed':True},cross_rate_pass=True) for n in (8,16)}
    assert qualification(pairs,cross,True)
    cross['8']['cross_rate_pass']=False
    assert qualification(pairs,cross,True)
    pairs['historical16']['eight_map_window']['passed']=False
    assert not qualification(pairs,cross,True)
    pairs['historical16']['eight_map_window']['passed']=True;cross['16']['cross_rate_pass']=False
    assert not qualification(pairs,cross,True)


def test_drift_failure_does_not_turn_into_original_quality_failure():
    verify_pair(pair(16,'historical'),'historical',16)


@pytest.mark.parametrize('damage',['quality','domain','promotion','missing_window','unexpected_cross'])
def test_malformed_or_hard_failure_pair_is_rejected(damage):
    r=deepcopy(pair(16))
    if damage=='quality':r['original_zero_gates']['0']=False
    elif damage=='domain':r['physical_response_failures']={'cell':43}
    elif damage=='promotion':r['accepted_material_step']=True
    elif damage=='missing_window':del r['eight_map_window']
    else:r['cross_history']={}
    with pytest.raises(AssertionError):verify_pair(r,'accelerated',16)
