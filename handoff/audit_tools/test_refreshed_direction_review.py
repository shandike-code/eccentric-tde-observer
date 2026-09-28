from copy import deepcopy
import numpy as np
import pytest
from handoff.audit_tools import review_refreshed_directions as a


def pair(x):return dict(previous=np.asarray(x,float),final=np.asarray(x,float))


def test_full_vector_signal_with_equal_opposite_norms_and_analytic_mass():
    x=np.array([3.,4,0,0,0,0,0,2]);p=pair(x);q=pair(-x)
    report,signals=a.independent_signals(p,q,[1,3])
    expected=[2*np.sqrt(29),np.sqrt(37),10]
    assert len(signals)==4 and all(np.array_equal(s,2*x) for s in signals.values())
    for row in report['signal_norms'].values():np.testing.assert_allclose(list(row.values()),expected,rtol=1e-15)
    for row in report['finite_response_norms'].values():np.testing.assert_allclose(list(row.values()),np.array(expected)*256,rtol=1e-15)
    assert report['endpoint_signal_resolved'] and not report['strict_error_bound'] and not report['exact_jacobian']


def test_zero_signal_remains_null_and_unresolved():
    p=pair(np.ones(8));report,_=a.independent_signals(p,p,[1,1])
    assert not report['endpoint_signal_resolved']
    assert list(report['endpoint_spread_over_signal'].values())==[None]*3


def test_small_endpoint_spread_does_not_prove_longer_signal_persistence():
    c=pair(np.ones(8));p=pair(np.ones(8)*1.1)
    _,old=a.independent_signals(p,c,[1,1])
    report,_=a.independent_signals(pair(np.ones(8)*1.2),c,[1,1],old)
    assert report['endpoint_signal_resolved'] and not report['eight_map_signal_persistent']
    np.testing.assert_allclose(list(report['eight_map_signal_drift_over_signal'].values()),.5)


def test_all_endpoint_combinations_and_original_control_scale():
    c=pair(np.ones(8));p=pair(np.ones(8)*.8);p['previous']*=2
    report=a.independent_cross(p,c,[1,1])
    assert len(report['ratios'])==4 and not report['passed']
    assert report['ratios']['previous_vs_final']['l2']==1.6


@pytest.mark.parametrize('bad',['missing','nan','shape','mass','earlier'])
def test_invalid_signal_data_cannot_be_interpreted_as_resolved(bad):
    c=pair(np.ones(8));p=pair(np.ones(8));mass=[1,1];earlier=None
    if bad=='missing':p.pop('final')
    if bad=='nan':p['previous'][0]=np.nan
    if bad=='shape':p['previous']=np.ones(4)
    if bad=='mass':mass=[0,1]
    if bad=='earlier':earlier={}
    with pytest.raises(ValueError):a.independent_signals(p,c,mass,earlier)


@pytest.mark.parametrize('bad',['pass','null','value','key'])
def test_saved_signal_claim_is_not_trusted(bad):
    actual,_=a.independent_signals(pair(np.ones(8)),pair(np.ones(8)),[1,1]);saved=deepcopy(actual)
    if bad=='pass':saved['endpoint_signal_resolved']=True
    if bad=='null':saved['endpoint_spread_over_signal']['l2']=0.
    if bad=='value':saved['signal_norms']['final_vs_final']['l2']=1.
    if bad=='key':saved.pop('exact_jacobian')
    with pytest.raises((AssertionError,TypeError)):a.same_record(actual,saved)


def plan():
    return dict(source_job=78594,source='outputs/hpc/step21-stationarity-confirmation-20260927',seed={'sha256':'frozen'},
        maximum_maps=48,maximum_feedback_pairs=6,limits=dict(control=16,thermal=16,population=16),cadence=[8,16],
        case_order=list(a.NAMES),cases={k:{} for k in a.NAMES},amplitudes=dict(control=0.,thermal=1/256,population=1/256),
        matched_initial_radiation=True,signal_tolerance=.1,control_window_tolerance=.001,accepted_outer_steps=20,
        automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False)


@pytest.mark.parametrize('field,value',[('maximum_maps',49),('maximum_feedback_pairs',7),('cadence',[4,8]),
    ('source_job',78548),('baseline_replacement_authorized',True),('automatic_promotion',True),('physical_dt_changed',True),
    ('case_order',['thermal','control','population']),('amplitudes',dict(control=0.,thermal=1/128,population=1/256))])
def test_wrong_protocol_and_budget_rejected(field,value):
    p=plan();a.verify_plan(p,{'sha256':'frozen'});p[field]=value
    with pytest.raises(AssertionError):a.verify_plan(p,{'sha256':'frozen'})
