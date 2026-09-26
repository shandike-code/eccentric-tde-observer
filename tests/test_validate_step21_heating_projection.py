from copy import deepcopy
import numpy as np
import pytest
from operations import validate_step21_heating_projection as valid
from test_recover_step21_control_windows import templates,endpoints


def reference():
    q=np.array([[10.,20.,30.],[10.4,20.3,30.2],[11.,21.,31.],[11.3,21.2,31.15]])
    u=np.array([3.,4.,5.]);rho=np.array([2.,3.,4.]);mass=np.array([1.,2.,3.])
    proxy=valid.probe.heating_projection(q,2.,rho,u,mass)
    return valid.freeze_heating(q,u,2.,rho,mass,proxy['alpha'])


def test_exact_affine_heating_and_fixed_source_denominator():
    ref=reference();result=valid.heating_checks(ref,ref['predicted_q'],ref['predicted_p'])
    assert result['validated'] and result['actual_proxy_ratio']<.8
    assert result['source_proxy_norm']==ref['source_proxy_norm']
    np.testing.assert_allclose(result['actual_proxy_ratio'],ref['proxy']['proxy_ratio'],rtol=1e-12)


@pytest.mark.parametrize('case',['common_bias','difference_error','bad_cost','nan','wrong_shape'])
def test_heating_failures_cannot_hide_in_proxy_norm(case):
    ref=reference();q=np.array(ref['predicted_q']);p=np.array(ref['predicted_p']);scale=np.array(ref['scale'])
    if case=='common_bias':q+=.01/scale;p+=.01/scale
    if case=='difference_error':p+=.01/scale
    if case=='bad_cost':p=q+np.array(ref['source_late_s'])/scale
    if case=='nan':
        q[0]=np.nan
        with pytest.raises(ValueError,match='nonfinite'):valid.heating_checks(ref,q,p)
        return
    if case=='wrong_shape':
        with pytest.raises(ValueError,match='shape'):valid.heating_checks(ref,q[:-1],p)
        return
    result=valid.heating_checks(ref,q,p)
    assert not result['validated']
    if case=='common_bias':
        assert result['checks']['actual_heating_cost_pass']
        assert not result['checks']['previous_prediction_error_pass']
    if case=='bad_cost':assert not result['checks']['actual_heating_cost_pass']


def test_changed_normalization_refused():
    ref=reference();ref['source_proxy_norm']*=100
    with pytest.raises(RuntimeError,match='normalization'):valid.heating_checks(ref,ref['predicted_q'],ref['predicted_p'])


def test_schedule_is_exactly_ten_maps_and_pairs_two_ten():
    events=[]
    def first():events.append(('map',1));return True
    result=valid.conditional_sequence(first,lambda n:events.append(('map',n)),lambda n:events.append(('pair',n)) or True)
    assert events==[('map',1),('map',2),('pair',2)]+[('map',n) for n in range(3,11)]+[('pair',10)]
    assert result=='heating_projection_validation_complete_requires_review'


def test_bad_first_map_or_heating_stops_conditional_batch():
    bad=lambda *_:pytest.fail('unexpected downstream work')
    assert valid.conditional_sequence(lambda:False,bad,bad)=='true_map_not_validated'
    maps=[];pairs=[]
    assert valid.conditional_sequence(lambda:True,maps.append,lambda n:pairs.append(n) or False)=='first_control_or_heating_not_validated'
    assert maps==[2] and pairs==[2]


def test_interrupted_map_cannot_trigger_feedback():
    def stop(_):raise valid.reused.Stopped('partial')
    with pytest.raises(valid.reused.Stopped):valid.conditional_sequence(lambda:True,stop,lambda _:pytest.fail('partial feedback'))


def test_last_feedback_failure_not_successful_budget_end():
    assert valid.conditional_sequence(lambda:True,lambda n:None,lambda n:n==2)=='second_control_pair_not_stable'


def test_real_protocol_factory_never_grants_acceptance():
    finite,zero=templates();es,rows=endpoints();saved=deepcopy(zero)
    p=valid.recovery.control_protocol(finite,zero,valid.ROOT/'outputs/hpc/test-heating',es,rows,{'path':'right-trial'}, {}, {})
    assert p['sources']['trial_material']['path']=='right-trial' and zero==saved
    assert p['authorization']['zero_displacement_control'] is True
    for k in ('accept_material_step','accept_finite_trial_only_if_all_acceptance_gates_pass',
              'accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass'):assert p['authorization'][k] is False


def test_map_limit_enforced_before_dispatch(monkeypatch):
    monkeypatch.setattr(valid.recovery.original,'map_once',lambda *args:pytest.fail('over-budget'))
    with pytest.raises(RuntimeError,match='ten-map'):valid.map_once(None,None,{'history':[{}]*10})


def test_negative_actual_field_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(valid.reused,'checkpoint',lambda:None)
    shape=(1,1,1);paths=[]
    for i,value in enumerate([1.,2.,2.,1.5,2.5,2.5,2.,-1.]):
        p=tmp_path/f'{i}.dat';np.full(shape,value).tofile(p);paths.append(p)
    with pytest.raises((ValueError,ArithmeticError)):valid.compare_fields(paths,shape,[0.,0.])


def test_select_candidate_rejects_changed_basis_and_unreviewed_guard():
    proxy={'alpha':-.5,'proxy_ratio':.7};basis=[{'path':str(i)} for i in range(6)]
    g={k:True for k in ('positive','coefficient_l1','coefficient_sum','strict_inner','maximum_improves','boundary_l1','boundary_bolometric')}
    pred=dict(eligible_for_independent_review=True,field={'uv':[0.,-.5],'gates':g},
        gates={**g,'heating_proxy_cost_pass':True},proxy=proxy,actual_map_performed=False,
        actual_candidate_heating_computed=False,accepted_material_step=False)
    audit=dict(eligible_for_independent_review=True,gates=pred['gates'],**proxy)
    declaration=dict(basis=basis,proxy=proxy,uv=[0.,-.5])
    assert valid.select_candidate(declaration,pred,audit,basis,proxy)==[0.,-.5]
    bad=deepcopy(basis);bad[0]['path']='other'
    with pytest.raises(RuntimeError,match='source'):valid.select_candidate(declaration,pred,audit,bad,proxy)
    audit['eligible_for_independent_review']=False
    with pytest.raises(RuntimeError,match='eligible'):valid.select_candidate(declaration,pred,audit,basis,proxy)
