from copy import deepcopy
import pytest
from handoff.audit_tools.review_step21_wide_validation import field_checks


def example():
    slabs=[dict(start=i,stop=i+16,error_max=1e-15,field_scale=1.,actual_change_max=7e-6,
                error_relative_to_local_field=1e-15,actual_local_residual=7e-6) for i in range(0,9632,16)]
    checks=dict(actual_maximum_norm_improves=True,actual_boundary_spectrum_pass=True,actual_boundary_bolometric_pass=True,
        worker_memory_pass=True,strict_inner_pass=True,full_field_prediction_error_small=True,
        prediction_error_below_tenth_actual_change=True,actual_cost_gain_pass=True)
    v=dict(field_comparison=dict(slabs=slabs,max_error_over_field=1e-15,max_error_over_actual_change=1e-15/7e-6,
        actual_global_residual=7e-6,full_intensity_prediction_error_evaluated=True,l2_error_over_actual_field=1e-15,l2_error_over_actual_change=1e-10),
        actual_map={'maximum_worker_rss_mib':3000.},checks=checks,validated=True)
    aggregate=dict(residual=7e-6,boundary_l1=1e-6,boundary_bolometric=1e-6)
    return v,aggregate,1e-5


def test_recompute_gates_and_disclose_missing_l2_sums():
    r=field_checks(*example());assert r['actual_over_prior']==pytest.approx(.7)
    assert r['full_field_l2_recomputed_on_mac'] is False


@pytest.mark.parametrize('kind',['gap','duplicate','error','gate','nonfinite'])
def test_tampered_field_evidence_rejected(kind):
    v,a,latest=example()
    if kind=='gap':v['field_comparison']['slabs'].pop()
    if kind=='duplicate':v['field_comparison']['slabs'][1]=deepcopy(v['field_comparison']['slabs'][0])
    if kind=='error':v['field_comparison']['max_error_over_field']=1e-20
    if kind=='gate':v['checks']['actual_cost_gain_pass']=False
    if kind=='nonfinite':v['field_comparison']['slabs'][0]['field_scale']=float('nan')
    with pytest.raises(AssertionError):field_checks(v,a,latest)


def test_a_real_failed_cost_gate_is_not_masked():
    v,a,latest=example();latest=a['residual']/.9;v['checks']['actual_cost_gain_pass']=False;v['validated']=False
    r=field_checks(v,a,latest);assert not r['checks']['actual_cost_gain_pass']
