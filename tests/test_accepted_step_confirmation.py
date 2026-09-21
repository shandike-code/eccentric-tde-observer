from copy import deepcopy
import pytest
from operations import accepted_step_confirmation as batch


def source():
    return ({'status':'one_material_trial_accepted','history':[{}]*8},
        {'gate_checks':{k:True for k in batch.REQUIRED_GATES},'decision':{'finite_trial_accepted_as_one_nonlinear_step':True}})


def test_exact_all_gate_accepted_source_required():
    s,r=source();batch.accepted_source(s,r)


@pytest.mark.parametrize('change',['failed_gate','missing_gate','pending','active','wrong_length','false_decision','wrong_status'])
def test_stale_or_incomplete_acceptance_refused(change):
    s,r=source()
    if change=='failed_gate':r['gate_checks']['inner_noise_resolved_pass']=False
    if change=='missing_gate':r['gate_checks'].pop('inner_noise_resolved_pass')
    if change=='pending':s['pending_feedback']={'stage':'ledger'}
    if change=='active':s['active_map']={'iteration':9}
    if change=='wrong_length':s['history'].append({})
    if change=='false_decision':r['decision']['finite_trial_accepted_as_one_nonlinear_step']=False
    if change=='wrong_status':s['status']='radiation'
    with pytest.raises(ValueError):batch.accepted_source(s,r)


def test_accepted_child_is_not_recomputed(monkeypatch,tmp_path):
    s={'status':'one_material_trial_accepted','history':[{},{}],'diagnostic':{'rounds':[{}]}}
    monkeypatch.setattr(batch.reused,'child',lambda *a:(tmp_path,{},s))
    monkeypatch.setattr(batch,'budget',lambda *a:None)
    monkeypatch.setattr(batch.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(batch.reused,'settle',lambda *a:None)
    monkeypatch.setattr(batch.reused,'archive',lambda *a:None)
    monkeypatch.setattr(batch,'round_review',lambda *a:None)
    monkeypatch.setattr(batch.driver,'run_one_map',lambda *a:pytest.fail('unexpected map'))
    assert batch.run_case(tmp_path,'confirm2','trial',{}, {}) is s


def test_pending_feedback_settled_without_running_a_new_map(monkeypatch,tmp_path):
    s={'status':'radiation','history':[{},{}],'pending_feedback':{'stage':'ledger'}};events=[]
    monkeypatch.setattr(batch.reused,'child',lambda *a:(tmp_path,{},s))
    monkeypatch.setattr(batch,'budget',lambda *a:None)
    monkeypatch.setattr(batch.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(batch.reused,'archive',lambda *a:None)
    monkeypatch.setattr(batch,'round_review',lambda *a:None)
    def settle(*a):
        events.append('ledger');s.pop('pending_feedback');s['diagnostic']={'rounds':[{}]}
    monkeypatch.setattr(batch.reused,'settle',settle)
    monkeypatch.setattr(batch.driver,'run_one_map',lambda *a:pytest.fail('unexpected map'))
    batch.run_case(tmp_path,'confirm2','trial',{},{});assert events==['ledger']


def test_resource_fault_has_priority_over_completed_budget(monkeypatch,tmp_path):
    monkeypatch.setattr(batch,'states',lambda *a:{'confirm2':{'status':'resource_gate_failed','history':[{},{}]}})
    with pytest.raises(RuntimeError,match='child fault'):batch.budget(tmp_path)


def test_active_map_and_pending_pair_count_toward_budget(monkeypatch,tmp_path):
    s={'status':'radiation','history':[{},{}],'active_map':{}}
    monkeypatch.setattr(batch,'states',lambda *a:{'confirm2':s})
    with pytest.raises(RuntimeError,match='map'):batch.budget(tmp_path)
    s={'status':'radiation','history':[],'diagnostic':{'rounds':[{}]},'pending_feedback':{'stage':'ledger'}}
    monkeypatch.setattr(batch,'states',lambda *a:{'confirm4':s})
    with pytest.raises(RuntimeError,match='pair'):batch.budget(tmp_path)
