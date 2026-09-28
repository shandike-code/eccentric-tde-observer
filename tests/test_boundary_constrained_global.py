from copy import deepcopy
import numpy as np
import pytest
from operations import validate_boundary_constrained_global as valid


def evidence():
    a=dict(job_id=80005,source_job_id=79878,accepted_outer_steps=20,new_material_steps=0,
        all_predicted_checks_passed=True,independent_small_statistic_reduction=True,actual_map_required=True,
        coefficients=dict(a=.4,b=1.))
    s=dict(status='complete_requires_review',source_unchanged=True,all_predicted_checks_passed=True,
        new_maps=0,new_feedback_pairs=0,production_candidate_written=False,operator_recomputed=False,
        coefficients=dict(a=.4,b=1.))
    return a,s


@pytest.mark.parametrize('key,value',[('job_id',79878),('source_job_id',79631),('all_predicted_checks_passed',False),
    ('independent_small_statistic_reduction',False),('actual_map_required',False),('new_material_steps',1)])
def test_unreviewed_or_changed_prediction_is_rejected(key,value):
    a,s=evidence();assert valid.require_proposal(a,s)==(.4,1.)
    a[key]=value
    with pytest.raises(RuntimeError):valid.require_proposal(a,s)


def test_coefficients_cannot_change_after_array_scan():
    a,s=evidence();s['coefficients']['a']=.5
    with pytest.raises(RuntimeError):valid.require_proposal(a,s)


def test_streamed_candidate_matches_declared_combination_and_original_half(tmp_path):
    shape=(6400,2,3);x=np.ones(shape);x[-1]=np.nextafter(0.,1.)
    q=x.copy();q[4352:6144]=2.;u=q.copy();u[2560:4352]=3.
    paths=[]
    for i,z in enumerate((x,q,u)):
        p=tmp_path/f'{i}.dat';z.tofile(p);paths.append(p)
    full,half=tmp_path/'full.dat',tmp_path/'half.dat'
    valid.fields.write_candidates(paths,full,half,shape,.4,1.)
    z=np.fromfile(full).reshape(shape);h=np.fromfile(half).reshape(shape)
    np.testing.assert_array_equal(z[4352:6144],np.full((1792,2,3),1.4))
    np.testing.assert_array_equal(z[2560:4352],u[2560:4352])
    assert np.array_equal(h[2560:6144],.5*x[2560:6144]+.5*z[2560:6144])
    assert not np.array_equal(h,.5*q+.5*z) and np.array_equal(h[6144:],x[6144:])
    op=lambda v:.25*v+.05*np.roll(v,1,axis=0)+1.
    measured=[]
    for i,v in enumerate((x,op(x),z,op(z),h,op(h),q,op(q))):
        p=tmp_path/f'map{i}.dat';v.tofile(p);measured.append(p)
    original,prior_q=valid.fields.validate(measured[:6],measured[6:],shape)
    assert original['fixed_scale_l2_ratios'][3]<1e-14 and original['selected_blocks']==list(range(20,48))
    assert len(prior_q['fixed_scale_l2_ratios'])==3 and not prior_q['affinity_tested_here']
    with pytest.raises(FileExistsError):valid.fields.write_candidates(paths,full,half,shape,.4,1.)


def test_twenty_one_gates_have_only_the_true_original_half_affinity():
    primary=dict(fixed_scale_l2_ratios=[1.,.5,.75,1e-10],fixed_scale_linf_ratios=[1.,.9,.9,1e-10])
    secondary=dict(fixed_scale_l2_ratios=[1.,.6,.8],fixed_scale_linf_ratios=[1.,.9,.9])
    row=dict(residual=1e-6,boundary_l1=1e-7,boundary_bolometric=1e-8)
    checks=valid.fields.checks(primary,secondary,row,row,row,row)
    assert len(checks)==21 and all(checks.values()) and checks['original_independent_half_affinity']
    assert 'prior_q_independent_half_affinity' not in checks
    changed={**row,'boundary_bolometric':1.1e-8}
    assert not valid.fields.checks(primary,secondary,row,row,changed,row)['original_full_boundary_bolometric']


def test_actual_global_failure_prevents_all_feedback():
    assert valid.sequence(lambda:False,lambda *_:pytest.fail('unvalidated feedback'))=='stopped_at_full_half_validation'
    order=[]
    assert valid.sequence(lambda:True,lambda name,n:(order.append((name,n)) or 'pass'))=='population_global_windows_complete_requires_review'
    assert order==[('control',2),('population',2),('control',10),('population',10)]
