import json
from types import SimpleNamespace
from copy import deepcopy
import numpy as np
import pytest
from operations import common_feedback_bridge as bridge


def test_hpc_resource_budget_is_explicitly_tightened_without_changing_science():
    historical=bridge.pair._formal_state_gates();historical['each_state_wall_time_strictly_below_s']=7200.
    actual=bridge.bridge_state_gates(historical)
    assert actual['each_state_wall_time_strictly_below_s']==900.
    assert historical['each_state_wall_time_strictly_below_s']==7200.
    bad=dict(historical);bad['atomic_rate_vs_inverse_four_force_global_fraction_below']=.002
    with pytest.raises(RuntimeError):bridge.bridge_state_gates(bad)


def combined():
    q=np.ones(4096)
    d={k:q.copy() for k in (bridge.FORMAL,'source_direct_heating_erg_s_cm3','atomic_rate_heating_erg_s_cm3','source_rate_heating_erg_s_cm3')}
    for k in ('photoionization_s1','spontaneous_recombination_cm3_s','stimulated_recombination_cm3_s','total_recombination_cm3_s'):d[k]=np.ones((4096,3))
    return d


def evaluate(fb,**kwargs):
    rows=[{'minimum_owned_comoving_mean_intensity':0.} for _ in range(76)]
    args={'fb':fb,'records':rows,'ownership':np.ones(9632,int),'wall':800.,'peak':4000.,'gates':bridge.pair._formal_state_gates()};args.update(kwargs)
    return bridge.state_checks(**args)[0]


def test_only_formal_source_changes_and_depth_projection_is_exact():
    old=combined();new=np.linspace(.9,1.1,4096)
    partial=bridge.replace_partial(old,new);fb=bridge.assembled_feedback(partial,np.ones(4096))
    assert np.array_equal(old[bridge.FORMAL],np.ones(4096))
    for k in old:
        if k!=bridge.FORMAL:assert np.array_equal(partial[k],old[k])
    assert np.array_equal(fb['parent_'+bridge.FORMAL],new.reshape(256,16).mean(axis=1))
    assert np.array_equal(fb['half_'+bridge.FORMAL],new.reshape(256,16).mean(axis=1)[:128])


def test_full_gate_recheck_keeps_strict_source_and_resource_limits():
    d=combined();fb=bridge.assembled_feedback(d,np.ones(4096));assert all(evaluate(fb).values())
    d[bridge.FORMAL]*=1.01;bad=bridge.assembled_feedback(d,np.ones(4096))
    assert not evaluate(bad)['formal_global'] and not evaluate(bad)['formal_volume']
    assert not evaluate(fb,wall=900.)['wall'];assert not evaluate(fb,peak=6144.)['memory']
    ownership=np.ones(9632,int);ownership[100]=2;assert not evaluate(fb,ownership=ownership)['frequency_ownership']


def test_mirror_failure_is_not_hidden_by_good_integral():
    d=combined();d[bridge.FORMAL][0]+=1e-3;fb=bridge.assembled_feedback(d,np.ones(4096))
    assert evaluate(fb)['formal_global'];assert not evaluate(fb)['mirror']


def test_failed_or_missing_state_cannot_reach_material_acceptance():
    ok={'status':'complete','state_gate_passed':True};bad={'status':'gate_failed','state_gate_passed':False}
    bridge.require_complete_states({'previous':ok,'final':ok})
    for states in ({'previous':ok},{'previous':ok,'final':bad}):
        with pytest.raises(RuntimeError,match='no material response'):bridge.require_complete_states(states)


def test_response_ledger_rejects_energy_population_or_domain_mismatch():
    book={'remaining':np.array([2.]),'target':np.array([3.]),'new_h':np.array([[.4,.6]]),'new_he':np.array([[.2,.3,.5]])}
    response=SimpleNamespace(target_specific_material_energy_erg_g=book['target'],hydrogen_fraction=book['new_h'],helium_fraction=book['new_he'])
    bridge.verify_response_ledger(book,response)
    for key in book:
        broken=deepcopy(book);broken[key]*=-1
        with pytest.raises(RuntimeError):bridge.verify_response_ledger(broken,response)


def identity_fixture():
    codec=bridge.pair.GroundStateLogSimplexCodec(2)
    x=codec.encode(np.array([1e4,2e4]),np.array([[.9,.1],[.8,.2]]),np.array([[.8,.1,.1],[.7,.2,.1]]))
    r=np.ones_like(x)*.01;rho=np.array([1e-10,2e-10]);base={'encoded_state':x,'base_encoded_state':x,'base_residual':r,'relaxation':np.array(0.),'density_g_cm3':rho,'phase_index':np.array(1),'step_duration_s':np.array(2.)}
    trial={**base,'encoded_state':x+r/64,'finite_direction':r,'relaxation':np.array(1/64)}
    decoded=codec.decode(trial['encoded_state'])
    for key in ('temperature_k','hydrogen_fraction','helium_fraction'):trial[key]=getattr(decoded,key).copy()
    old={'density_g_cm3':np.array([rho,rho]),'step_duration_s':np.array([2.,2.])}
    return trial,base,r,old


def test_exact_candidate_and_physical_time_identity():
    t,b,r,o=identity_fixture();bridge.validate_identity(t,b,r,o)
    for key in ('encoded_state','base_encoded_state','finite_direction','temperature_k','step_duration_s'):
        broken=deepcopy(t);broken[key]=np.nextafter(broken[key],np.inf)
        with pytest.raises(RuntimeError):bridge.validate_identity(broken,b,r,o)


def test_new_origin_manifest_is_required_by_unchanged_adapter(tmp_path):
    m={'protocol_sha256':'new-origin','status':'complete','state_gate_passed':True,'state_path':'state.dat','state_sha256':'rad-sha','feedback_artifact_path':'feedback.npz','feedback_artifact_sha256':'fb-sha'}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(m))
    p={'configuration':{'reuse_completed_feedback_manifests':True,'feedback_origin_protocol_sha256':'new-origin'},'authorization':{'reuse_only_after_bytewise_reproduction_audit':True},'sources':{'previous_feedback_manifest':{'path':'manifest.json'},'previous_feedback_artifact':{'path':'feedback.npz','sha256':'fb-sha'},'previous_radiation':{'path':'state.dat','sha256':'rad-sha'}}}
    assert bridge.pair._load_reused_feedback_manifest(p,'previous',root=tmp_path)==m
    m['protocol_sha256']='old-origin';path.write_text(json.dumps(m))
    with pytest.raises(RuntimeError,match='lineage'):bridge.pair._load_reused_feedback_manifest(p,'previous',root=tmp_path)
