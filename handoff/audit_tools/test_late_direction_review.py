from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from handoff.audit_tools import review_late_direction_windows as audit


def vectors(value):return dict(previous=np.ones(8)*value,final=np.ones(8)*value)


def test_history_fail_is_retained_while_small_local_window_passes():
    m=audit.control_metrics(vectors(1.002),vectors(1.0019),vectors(1.0018),vectors(1),np.ones(8),[1,1],True)
    assert m['control_pass'] and not m['historical_78594_cumulative_pass']
    assert not m['original_78594_cumulative_stability_claim'] and not m['historical']['passed']


def test_small_last_control_window_cannot_hide_total_drift():
    m=audit.control_metrics(vectors(1.002),vectors(1.0019),vectors(1),vectors(1),np.ones(8),[1,1],True)
    assert m['window']['passed'] and not m['cumulative']['passed'] and not m['control_pass']


def test_cumulative_direction_failure_survives_small_last_window():
    c=vectors(1);_,start=audit.previous.independent_signals(vectors(2),c,[1,1])
    _,last=audit.previous.independent_signals(vectors(2.11),c,[1,1])
    result,_=audit.direction_metrics(vectors(2.2),c,[1,1],last,start)
    assert result['response_measurement']['eight_map_signal_persistent']
    assert not result['from_78950_map16_signal']['eight_map_signal_persistent']
    assert not result['late_direction_pass']


@pytest.mark.parametrize('index',range(6))
def test_stop_after_any_first_failure_is_valid_but_continuation_is_rejected(index):
    order=[(n,k) for n in (8,16) for k in audit.NAMES];events=order[:index+1]
    n,k=events[-1];passed=[True]*index+[False]
    audit.verify_schedule(events,passed,True,f'stopped_at_{k}_map{n:02d}_late_window_not_confirmed')
    if index<5:
        with pytest.raises(AssertionError):audit.verify_schedule(order[:index+2],passed+[True],False,'feedback')
    with pytest.raises(AssertionError):audit.verify_schedule(events,passed,True,'late_direction_windows_complete_requires_review')


def test_partial_cannot_be_mislabeled_complete():
    audit.verify_schedule([(8,'control')],[True],False,'feedback')
    with pytest.raises(AssertionError):audit.verify_schedule([(8,'control')],[True],True,'late_direction_windows_complete_requires_review')


def plan():
    seeds={k:dict(path=k,sha256=k,size_bytes=10099884032) for k in audit.NAMES}
    return dict(source_job=78950,source='outputs/hpc/step21-refreshed-directions-20260928',seeds=seeds,
        maximum_maps=48,maximum_feedback_pairs=6,limits=dict.fromkeys(audit.NAMES,16),cadence=[8,16],
        source_maps_per_case=16,absolute_feedback_maps=[24,32],case_order=list(audit.NAMES),cases=dict.fromkeys(audit.NAMES,{}),
        amplitudes=dict(control=0.,thermal=1/256,population=1/256),control_window_tolerance=.001,signal_tolerance=.1,
        cumulative_anchor='78950 map16',accepted_outer_steps=20,own_successor_continuation=True,
        stop_on_first_failed_late_window=True,historical_78594_drift_reported=True,old_8_to_16_verdicts_retained=True,
        matched_initial_radiation=False,historical_78594_gate_controls_dispatch=False,automatic_promotion=False,
        baseline_replacement_authorized=False,physical_dt_changed=False,strict_error_bound=False),seeds


@pytest.mark.parametrize('field,value',[('maximum_maps',49),('absolute_feedback_maps',[8,16]),('cumulative_anchor','new'),
    ('historical_78594_drift_reported',False),('stop_on_first_failed_late_window',False),('automatic_promotion',True),
    ('baseline_replacement_authorized',True),('matched_initial_radiation',True),('old_8_to_16_verdicts_retained',False)])
def test_changed_scope_or_budget_rejected(field,value):
    d,seeds=plan();audit.verify_plan(d,seeds);d[field]=value
    with pytest.raises(AssertionError):audit.verify_plan(d,seeds)


@pytest.mark.parametrize('name',['thermal','population'])
def test_real_source_vectors_reproduce_old_failure_and_resolve_late_endpoints(name,monkeypatch):
    from operations import remeasure_step21_directions as production
    def forbidden(*a,**k):raise AssertionError('production reduction reused')
    monkeypatch.setattr(production,'response_measurement',forbidden)
    root=Path('outputs/review-20260925/refreshed-directions-78950-complete-received')
    if not root.exists():pytest.skip('requires Mac complete archive')
    old=Path('outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz')
    mass=audit.arrays(old)['cell_mass_g_cm2']
    def pair(k,n):return {e:audit.arrays(root/k/f'pair{n:02d}/{e}_response.npz')['residual'] for e in ('previous','final')}
    _,earlier=audit.previous.independent_signals(pair(name,8),pair('control',8),mass)
    _,origin=audit.previous.independent_signals(pair(name,16),pair('control',16),mass)
    report,_=audit.direction_metrics(pair(name,16),pair('control',16),mass,earlier,origin)
    saved=audit.read(root/name/'pair16/decision.json')['response_measurement']
    audit.previous.same_record(report['response_measurement'],saved)
    assert not report['late_direction_pass'] and report['from_78950_map16_signal']['eight_map_signal_persistent']
    same,_=audit.direction_metrics(pair(name,16),pair('control',16),mass,origin,origin)
    assert same['late_direction_pass']
