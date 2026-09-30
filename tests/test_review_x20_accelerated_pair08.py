from copy import deepcopy
import pytest
from handoff.audit_tools import review_x20_accelerated_pair08 as a


def load():
    if not a.OUT.exists():pytest.skip('Mac received first-pair archive')
    return a.read(a.OUT/'declaration.json'),a.read(a.OUT/'seed-claims.json'),a.read(a.OUT/'accelerated/pair08/decision.json')


def test_first_pair_does_not_require_old_feedback_difference_to_pass():
    d,seeds,dec=load();a.verify_plan(d,seeds);a.verify_pair_scope(dec)
    assert not dec['from_prior_feedback']['passed']


@pytest.mark.parametrize('field,value',[('maximum_maps',33),('window_r20_tolerance',.01),('physical_dt_changed',True),('baseline_replacement_authorized',True)])
def test_changed_scope_is_rejected(field,value):
    d,seeds,_=load();d[field]=value
    with pytest.raises(AssertionError):a.verify_plan(d,seeds)


@pytest.mark.parametrize('damage',['physical','original_gate','promotion','fake_window'])
def test_feedback_or_promotion_fault_cannot_hide_behind_continuation(damage):
    _,_,dec=load();dec=deepcopy(dec)
    if damage=='physical':dec['physical_response_failures']={'cell':43}
    elif damage=='original_gate':dec['original_zero_gates']['last_two_formal_heating_pass']=False
    elif damage=='promotion':dec['accepted_material_step']=True
    else:dec['eight_map_window']={'passed':True}
    with pytest.raises(AssertionError):a.verify_pair_scope(dec)
