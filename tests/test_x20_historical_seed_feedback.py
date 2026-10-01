from copy import deepcopy
import numpy as np
import pytest
from operations import x20_historical_seed_feedback as c


def source_roots():
    root=c.ROOT/'outputs/review-20260925'
    true=root/'x20-historical-half-validation-82765-received'
    saved=root/'x20-global-feedback-82518-complete-received'
    if not true.exists():true=c.ROOT/'outputs/hpc/x20-historical-half-validation-20261001'
    if not saved.exists():saved=c.ROOT/'outputs/hpc/x20-global-window-feedback-20261001'
    assert true.exists() and saved.exists(), 'real audited inputs required'
    return true,saved


def test_single_new_branch_two_windows_and_hard_stop():
    calls=[]
    assert c.sequence(lambda name,n:calls.append((name,n)) or 'pass')=='historical_seed_windows_complete_requires_review'
    assert calls==[('historical',8),('historical',16)] and c.LIMITS=={'historical':16}
    calls=[]
    assert c.sequence(lambda name,n:calls.append((name,n)) or 'physical_domain_rejected').endswith('physical_domain_rejected')
    assert calls==[('historical',8)]


def test_true_output_and_frozen_reference_real_identity():
    true,saved=source_roots()
    audit=c.pipeline.read(c.ROOT/'handoff/evidence/20261001-x20-historical-half-validation-82765-review.json')
    c.require_validation(audit,c.pipeline.read(true/'summary.json'))
    c.require_saved_reference(c.pipeline.read(c.ROOT/'handoff/evidence/20261001-x20-82518-final-review.json'),c.pipeline.read(saved/'summary.json'))
    claim=c.seed_claim(c.pipeline.read(true/'validation.json'),c.pipeline.read(true/'full/state.json'))
    assert claim['sha256']=='2ee3248be34189d57fbc28340a858d8018e81691c0d3e9b36c47382aeda2bcf0'
    assert claim['sha256']!=c.pipeline.read(true/'candidate-claims.json')['full']['sha256']
    for name in ('historical','accelerated'):
        c.seed_operator_config(c.pipeline.read(true/'full/config.json'),c.pipeline.read(saved/name/'config.json'))
        c.fixed.same_trial(c.v.load_arrays(true/'full/trial_material.npz'),c.v.load_arrays(saved/name/'trial_material.npz'))


@pytest.mark.parametrize('damage',['wrong_job','missing_gate','failed_gate','unreviewed'])
def test_requires_all_82765_gates(damage):
    true,_=source_roots();a=c.pipeline.read(c.ROOT/'handoff/evidence/20261001-x20-historical-half-validation-82765-review.json')
    if damage=='wrong_job':a['job_id']=82515
    if damage=='missing_gate':a['actual']['checks'].pop('full_l2_affinity')
    if damage=='failed_gate':a['actual']['checks']['full_l2_affinity']=False
    if damage=='unreviewed':a['true_maps_independently_validated']=False
    with pytest.raises(ValueError):c.require_validation(a,c.pipeline.read(true/'summary.json'))


@pytest.mark.parametrize('damage',['active','input_instead_of_output','wrong_current'])
def test_rejects_unsettled_or_wrong_seed(damage):
    true,_=source_roots();s=c.pipeline.read(true/'full/state.json');actual=c.pipeline.read(true/'validation.json')
    if damage=='active':s['active_map']={}
    if damage=='input_instead_of_output':s['history'][0]['output_sha256']=s['history'][0]['input_sha256']
    if damage=='wrong_current':s['current_sha256']='bad'
    with pytest.raises(ValueError):c.seed_claim(actual,s)


def test_saved_reference_is_not_promoted_or_unstable():
    _,saved=source_roots();a=c.pipeline.read(c.ROOT/'handoff/evidence/20261001-x20-82518-final-review.json');s=c.pipeline.read(saved/'summary.json')
    s['cases']['accelerated']['16']['eight_map_window']['passed']=False
    with pytest.raises(ValueError):c.require_saved_reference(a,s)


def test_four_comparisons_use_complete_vector_difference():
    from operations.calibrate_x20_radiation_histories import vector_comparison
    x=np.ones(512);r=np.ones(512);mass=np.ones(128)
    same={'previous':x,'final':x};opposite={'previous':-x,'final':-x}
    assert vector_comparison(same,same,r,mass,np.ones(3))['passed']
    q=vector_comparison(same,opposite,r,mass,np.ones(3))
    assert not q['passed'] and len(q['vector_difference_over_frozen_80195_signal'])==4
    assert all(max(row)>0 for row in q['vector_difference_over_frozen_80195_signal'].values())


def test_four_saved_feedback_combinations_and_labels():
    _,saved=source_roots()
    vec={e:c.v.load_arrays(saved/f'accelerated/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    fb={e:c.v.load_arrays(saved/f'accelerated/pair16/{e}_feedback.npz') for e in ('previous','final')}
    protocol=c.pipeline.read(saved/'accelerated/pair16/feedback_protocol.json')
    # 自身比较仍包含previous/final两个不同端点；只断言组合数、来源标签与原率门。
    result=c.compare_saved(vec,fb,vec,fb,np.ones(512),np.ones(128),np.ones(3),protocol['acceptance_gates'])
    assert len(result['all_four_rate_gate_checks'])==4 and result['cross_rate_pass']
    assert result['saved_reference_job']==82518 and not result['reference_recomputed']
