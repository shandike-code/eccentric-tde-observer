from copy import deepcopy
import numpy as np
import pytest
from operations import response_direction_batch as batch


def zero_source():
    codec=batch.GroundStateLogSimplexCodec(2)
    b=codec.encode(np.array([2e4,3e4]),np.array([[.3,.7],[.4,.6]]),np.array([[.2,.3,.5],[.3,.3,.4]]))
    v=codec.decode(b)
    source={k:np.array(getattr(v,k)) for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    source.update(encoded_state=b.copy(),base_encoded_state=b.copy(),finite_direction=np.ones(8),base_residual=np.ones(8),
                  density_g_cm3=np.array([1e-9,2e-9]),step_duration_s=np.array(889.419892762322),phase_index=np.array(1367),relaxation=np.array(0.))
    return source


def test_new_direction_is_explicit_and_frozen_physics_unchanged():
    s=zero_source();before=deepcopy(s);d=np.arange(8.)/8;t=batch.make_trial(s,d,1/256)
    assert np.array_equal(t['encoded_state'],s['base_encoded_state']+d/256)
    assert np.array_equal(t['finite_direction'],d)
    for k in ('base_encoded_state','base_residual','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(t[k],s[k])
    batch.identical_material(s,before)


@pytest.mark.parametrize('d,a',[(np.ones(8),1/128),(np.zeros(8),1/256),(np.full(8,np.nan),1/256),(np.ones(7),1/256),(np.ones(8)*1000,1/256)])
def test_undeclared_or_invalid_direction_is_rejected(d,a):
    with pytest.raises(ValueError):batch.make_trial(zero_source(),d,a)


def test_nonzero_material_cannot_be_used_as_the_baseline():
    s=zero_source();s['relaxation']=np.array(.01)
    with pytest.raises(ValueError,match='zero control'):batch.make_trial(s,np.ones(8),1/256)


def test_budget_counts_active_and_pending_work():
    s={'status':'radiation','history':[{}]*8,'active_map':{},'diagnostic':{'rounds':[]}}
    with pytest.raises(RuntimeError,match='budget'):batch.check_budget({'full':s})
    s={'status':'radiation','history':[],'diagnostic':{'rounds':[{},{}]},'pending_feedback':{'stage':'ledger'}}
    with pytest.raises(RuntimeError,match='budget'):batch.check_budget({'half':s})


def harness(monkeypatch,tmp_path,n=0,pending=False,accepted=False):
    s={'status':'radiation','history':[{} for _ in range(n)],'active_map':None,'diagnostic':{'rounds':[]}}
    if pending:s['pending_feedback']={'stage':'feedback'}
    events=[]
    monkeypatch.setattr(batch.reused,'child',lambda *a:(tmp_path,{},s))
    monkeypatch.setattr(batch,'child_states',lambda *a:{'full':s})
    monkeypatch.setattr(batch,'mark',lambda *a,**k:None)
    monkeypatch.setattr(batch.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(batch.reused,'archive',lambda *a:None)
    monkeypatch.setattr(batch,'round_review',lambda *a:{})
    monkeypatch.setattr(batch.pipeline,'read',lambda p:{})
    def run(*a):
        events.append('map');s['history'].append({});return True
    def start(*a):
        events.append('start'+str(len(s['history'])));s['pending_feedback']={'stage':'feedback'}
    def settle(*a):
        events.append('settle');s.pop('pending_feedback');s['diagnostic']['rounds'].append({'ledger':'mock/ledger.json'})
        if accepted:s['status']='one_material_trial_accepted'
    monkeypatch.setattr(batch.driver,'run_one_map',run)
    monkeypatch.setattr(batch.driver,'start_round',start)
    monkeypatch.setattr(batch.reused,'settle',settle)
    return s,events


def test_single_allocation_settles_at_four_and_eight_maps(monkeypatch,tmp_path):
    s,e=harness(monkeypatch,tmp_path)
    assert batch.process_case(tmp_path,'full','full',{'seed':{}})=='budget_complete'
    assert e==['map']*4+['start4','settle']+['map']*4+['start8','settle']


def test_owed_feedback_is_settled_before_new_maps(monkeypatch,tmp_path):
    s,e=harness(monkeypatch,tmp_path,n=4,pending=True)
    batch.process_case(tmp_path,'full','full',{'seed':{}})
    assert e[0]=='settle' and e.count('map')==4


def test_accepted_step_stops_before_another_map(monkeypatch,tmp_path):
    s,e=harness(monkeypatch,tmp_path,accepted=True)
    assert batch.process_case(tmp_path,'full','full',{'seed':{}})=='accepted'
    assert e.count('map')==4


def test_resource_fault_is_not_budget_completion(monkeypatch,tmp_path):
    s,e=harness(monkeypatch,tmp_path,n=8);s['status']='resource_gate_failed'
    with pytest.raises(RuntimeError,match='child fault'):batch.process_case(tmp_path,'full','full',{'seed':{}})


def test_current_batch_interruption_preserves_partial_state(monkeypatch,tmp_path):
    s,e=harness(monkeypatch,tmp_path)
    monkeypatch.setattr(batch.driver,'run_one_map',lambda *a:False)
    with pytest.raises(batch.reused.Stopped):batch.process_case(tmp_path,'full','full',{'seed':{}})


def test_stable_feedback_does_not_hide_unphysical_baseline(monkeypatch,tmp_path):
    monkeypatch.setattr(batch.pipeline,'pair_ready',lambda *a:True)
    monkeypatch.setattr(batch.pipeline,'read',lambda *a:{})
    monkeypatch.setattr(batch,'load_arrays',lambda *a:{})
    def fail(*a):raise batch.reused.pair.PhysicalDomainError('nonpositive gas heat')
    monkeypatch.setattr(batch.reused.pair,'_material_response_residual',fail)
    r=batch.control_check(tmp_path,{'history':[]},{'heating_stability':{'metrics':{'heat':{'ratio':.0001}}}})
    assert r['inner_and_feedback_stability_pass'] and not r['physical_response_pass']
    assert set(r['response_failures'])=={'previous','final'}
