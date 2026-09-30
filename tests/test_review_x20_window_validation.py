import copy,math
import pytest
from handoff.audit_tools.review_x20_window_validation import actual_numbers


def data(error=1e-7):
    rows=[dict(first_group=32*i,group_count=32,block=i//4,selected_input=True,output_change_linf=.1,
               squared_l2=[1.,.36,.64,1e-14],linf=[1.,.6,.8,1e-7]) for i in range(301)]
    pred=[dict(first_group=32*i,group_count=32,squared_l2=[1.,error**2,1e-14],linf=[1.,error,1e-7]) for i in range(301)]
    original=dict(residual=1e-6,boundary_l1=1e-5,boundary_bolometric=1e-6)
    checks={k:True for k in ('full_l2_benefit','full_linf_nonincrease','half_l2_nonincrease','half_linf_nonincrease',
            'full_radiation','full_boundary_l1','full_boundary_bolometric','half_radiation','half_boundary_l1','half_boundary_bolometric',
            'independent_half_affinity','independent_half_linf_affinity')}
    pc=dict(full_l2_affinity=error<=1e-6,full_linf_affinity=error<=1e-6,half_l2_affinity=True,half_linf_affinity=True);checks.update(pc)
    v=dict(field_comparison=dict(slabs=rows,all_groups_evaluated=9632,selected_blocks=list(range(76)),
            original_defect_l2=math.sqrt(301),original_defect_linf=1.,fixed_scale_l2_ratios=[1,.6,.8,1e-7],fixed_scale_linf_ratios=[1,.6,.8,1e-7]),
        prediction_affinity=dict(slabs=pred,l2_ratios=[1,error,1e-7],linf_ratios=[1,error,1e-7],checks=pc,passed=all(pc.values())),
        actual_maps={n:dict(original) for n in ('full','half')},checks=checks,validated=all(checks.values()),baseline_replaced=False,material_step_promoted=False)
    return v,original


def test_full_set_of_sixteen_gates_recomputed():
    v,o=data();r=actual_numbers(v,o)
    assert r['validated'] and len(r['checks'])==16


def test_direct_prediction_failure_cannot_hide_behind_good_map_gain():
    v,o=data(2e-6);r=actual_numbers(v,o)
    assert not r['validated'] and r['checks']['full_l2_benefit'] and not r['checks']['full_l2_affinity']


def test_missing_slab_is_rejected():
    v,o=data();v['prediction_affinity']['slabs'].pop()
    with pytest.raises(AssertionError):actual_numbers(v,o)
