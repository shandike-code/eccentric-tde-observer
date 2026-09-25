import copy
import json
import numpy as np
import pytest
from handoff.audit_tools import review_step21_control_windows as a


def endpoints(x):return {'previous':np.asarray(x,float),'final':np.asarray(x,float)}


def test_independent_norms_have_analytic_mass_weighting():
    n=a.independent_norms([3,4,0,0,0,0,0,2],[1,3])
    np.testing.assert_allclose(n,[np.sqrt(29),np.sqrt(37/4),5],rtol=1e-15)


def test_equal_norm_opposite_vectors_are_not_stationary():
    x=np.ones(8);r=a.recompute_window(endpoints(x),endpoints(-x),x,[1,1])
    assert not r['passed']
    np.testing.assert_equal(list(r['vector_difference_over_frozen_r20_norms'].values()),np.full((4,3),2.))


def test_cross_endpoints_and_frozen_denominator_are_used():
    x=np.ones(8);old=endpoints(100*x);new=endpoints(100*x);new['previous']=101*x
    r=a.recompute_window(new,old,x,[1,1]);assert not r['passed']
    np.testing.assert_allclose(r['vector_difference_over_frozen_r20_norms']['previous_vs_final'],[1,1,1])


@pytest.mark.parametrize('kind',['missing','nan','zero_mass','zero_reference'])
def test_invalid_inputs_are_rejected(kind):
    x=np.ones(8);current=endpoints(x);old=endpoints(x);mass=[1,1];r=x.copy()
    if kind=='missing':current.pop('previous')
    if kind=='nan':current['final'][0]=np.nan
    if kind=='zero_mass':mass=[0,1]
    if kind=='zero_reference':r[:]=0
    with pytest.raises(ValueError):a.recompute_window(current,old,r,mass)


def test_forged_pass_or_changed_denominator_values_are_rejected():
    x=np.ones(8);r=a.recompute_window(endpoints(x),endpoints(-x),x,[1,1])
    for change in ('passed','ratio'):
        saved=copy.deepcopy(r)
        if change=='passed':saved['passed']=True
        else:saved['vector_difference_over_frozen_r20_norms']['final_vs_final'][0]/=100
        with pytest.raises(AssertionError):a.verify_window(r,saved)


@pytest.mark.parametrize('field,value',[('automatic_promotion',True),('baseline_replacement_authorized',True),('maximum_maps',32),('cadence',[4,8]),('seed',{'sha256':'wrong'})])
def test_changed_experiment_declaration_is_rejected(field,value):
    seed={'sha256':'frozen'}
    d={'maximum_maps':16,'cadence':[8,16],'maximum_feedback_pairs':2,'window_tolerance':.001,'accepted_outer_steps':20,'automatic_promotion':False,'baseline_replacement_authorized':False,'cases':{'control':{}},'seed':seed}
    a.verify_declaration(d,seed);d[field]=value
    with pytest.raises(AssertionError):a.verify_declaration(d,seed)


def test_manifest_rejects_unlisted_files(tmp_path):
    (tmp_path/'ARCHIVE_MANIFEST.json').write_text(json.dumps({'files':[]}))
    a.verified_inventory(tmp_path)
    (tmp_path/'unexpected.json').write_text('{}')
    with pytest.raises(AssertionError):a.verified_inventory(tmp_path)
