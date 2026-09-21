from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from operations import numbered_confirmation_step as combined


def fresh():
    return {'comparisons':{k:{e:{'candidate_over_base':{'l2':.98,'mass_weighted':.96,'maximum_cell':.995}}
        for e in ('previous','final')} for k in ('previous','final')}}


@pytest.mark.parametrize('fault',['empty','missing','one_failed','nan','domain'])
def test_fresh_control_requires_all_four_complete_finite_contractions(fault):
    c=fresh();assert combined.fresh_contraction(c)
    if fault=='empty':c['comparisons']={}
    if fault=='missing':c['comparisons']['previous'].pop('final')
    if fault=='one_failed':c['comparisons']['previous']['final']['candidate_over_base']['maximum_cell']=1.01
    if fault=='nan':c['comparisons']['final']['previous']['candidate_over_base']['l2']=float('nan')
    if fault=='domain':c['comparisons']['previous']={'physical_domain_error':'unphysical'}
    assert not combined.fresh_contraction(c)


def state(n,pairs=0,active=None,pending=None,status='radiation'):
    return {'status':status,'history':[{}]*n,'active_map':active,
            'diagnostic':{'rounds':[{}]*pairs},'pending_feedback':pending}


def test_budgets_include_active_and_pending_across_both_stages(monkeypatch,tmp_path):
    a={k:state(2,1) for k in combined.confirm.LIMITS}
    b={'control':state(2,1),'full':state(8,2),'half':state(7,1,{}, {'stage':'feedback'})}
    monkeypatch.setattr(combined.confirm,'states',lambda p:a)
    monkeypatch.setattr(combined.batch,'child_states',lambda p:b)
    got=combined.budget(tmp_path)
    assert got['maps_committed_or_active']==24 and got['pairs_completed_or_pending']==8
    b['half']['history'].append({})
    with pytest.raises(RuntimeError,match='budget'):combined.budget(tmp_path)


def test_parent_failure_cannot_turn_into_science_stop(tmp_path):
    p=tmp_path/'confirmation';p.mkdir();(p/'status.json').write_text('{"status":"failed"}')
    with pytest.raises(RuntimeError,match='terminal'):combined.budget(tmp_path)
    combined.mark(tmp_path,'failed',error='preserved')
    with pytest.raises(RuntimeError,match='terminal'):combined.mark(tmp_path,'complete')


def harness(monkeypatch,tmp_path,passed=True):
    events=[];monkeypatch.setattr(combined,'ROOT',tmp_path)
    monkeypatch.setattr(combined,'declare',lambda p:events.append('declare'))
    monkeypatch.setattr(combined.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(combined.reused,'archive',lambda *a:events.append('archive'))
    monkeypatch.setattr(combined.pipeline,'claim',lambda p:{'path':str(p),'sha256':'test','size_bytes':1})
    monkeypatch.setattr(__import__('shutil'),'disk_usage',lambda p:SimpleNamespace(free=10**14))
    monkeypatch.setattr(combined,'run_confirmation',lambda p:events.append('confirm'))
    monkeypatch.setattr(combined,'confirmation_passed',lambda p:passed)
    def run_next(folder,confirmation):
        events.append('next');assert (folder.parent/'transition.json').exists()
        (folder/'status.json').write_text('{"status":"complete"}')
    monkeypatch.setattr(combined,'run_next',run_next)
    return events


def test_confirmed_source_advances_in_same_call_and_persists_transition(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path)
    combined.execute(tmp_path)
    assert events==['declare','confirm','next','archive']
    transition=json.loads((tmp_path/'transition.json').read_text())
    assert transition['next_outer_step_index']==4 and not transition['physical_time_advanced']
    combined.execute(tmp_path)
    assert events==['declare','confirm','next','archive']


def test_unconfirmed_source_never_creates_next_step(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path,False);combined.execute(tmp_path)
    assert events==['declare','confirm','archive']
    assert not (tmp_path/'next-step').exists() and not (tmp_path/'transition.json').exists()
    assert json.loads((tmp_path/'status.json').read_text())['status']=='confirmation_not_passed'


def test_stop_after_confirmation_prevents_dependent_stage(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path)
    calls=[]
    def checkpoint():
        calls.append(1)
        if len(calls)==2:raise combined.reused.Stopped('USR1')
    monkeypatch.setattr(combined.reused,'checkpoint',checkpoint)
    with pytest.raises(combined.reused.Stopped):combined.execute(tmp_path)
    assert events==['declare','confirm'] and not (tmp_path/'next-step').exists()


def test_next_stage_prepare_and_protocol_adapters_are_restored_on_exception(monkeypatch,tmp_path):
    monkeypatch.setattr(combined,'ROOT',tmp_path)
    old_prepare=combined.batch.prepare;old_proto=combined.pipeline.feedback_protocol
    def fail(out):
        assert combined.batch.prepare is not old_prepare
        assert combined.pipeline.feedback_protocol is not old_proto
        raise RuntimeError('injected')
    monkeypatch.setattr(combined.batch,'execute',fail)
    with pytest.raises(RuntimeError,match='injected'):combined.run_next(tmp_path/'next',tmp_path/'confirmation')
    assert combined.batch.prepare is old_prepare and combined.pipeline.feedback_protocol is old_proto


def test_third_step_protocol_has_new_index_and_source_without_mutating_template(monkeypatch,tmp_path):
    legacy=tmp_path/'feedback_protocol.json';legacy.write_text('{"original":true}')
    old=combined.pipeline.feedback_protocol
    original=lambda *a:legacy;monkeypatch.setattr(combined.pipeline,'feedback_protocol',original)
    payload={'outer_iteration':{'index':2,'source':'old','physical_time_advanced':False},'acceptance_gates':{'x':1}}
    monkeypatch.setattr(combined.outer,'rebase_payload',lambda p,c:deepcopy(payload))
    with combined.stage_protocols(3,'new/confirmation/confirm4'):
        result=json.loads(combined.pipeline.feedback_protocol({},{}).read_text())
    assert result['outer_iteration']=={'index':3,'source':'new/confirmation/confirm4','physical_time_advanced':False}
    assert result['acceptance_gates']==payload['acceptance_gates']
    assert json.loads(legacy.read_text())=={'original':True}
    assert combined.pipeline.feedback_protocol is original


@pytest.fixture(autouse=True)
def configure_numbered_globals(monkeypatch):
    monkeypatch.setattr(combined,'ACCEPTED_INDEX',3)
    monkeypatch.setattr(combined,'SOURCE','outputs/hpc/source-step3')
    monkeypatch.setattr(combined,'FORMAL_SOURCE','outputs/hpc/confirmed-step2/confirm4')


@pytest.mark.parametrize('index',[3,4,5,6])
def test_confirmation_and_next_protocols_use_bound_indices(monkeypatch,tmp_path,index):
    monkeypatch.setattr(combined,'ROOT',tmp_path)
    monkeypatch.setattr(combined,'ACCEPTED_INDEX',index)
    from contextlib import contextmanager
    seen=[]
    @contextmanager
    def capture(i,s):
        seen.append((i,s));yield
    monkeypatch.setattr(combined,'stage_protocols',capture)
    monkeypatch.setattr(combined.confirm,'execute',lambda p:None)
    monkeypatch.setattr(combined.batch,'execute',lambda p:None)
    combined.run_confirmation(tmp_path/'confirmation')
    combined.run_next(tmp_path/'next',tmp_path/'confirmation')
    assert seen==[(index,combined.FORMAL_SOURCE),(index+1,'confirmation/confirm4')]


@pytest.mark.parametrize('fault',['none','index','time','hash','fresh'])
def test_source_configure_verifies_real_protocol_not_directory_label(monkeypatch,tmp_path,fault):
    from operations.prepare_half_step_after_audit import REQUIRED_GATES
    monkeypatch.setattr(combined,'ROOT',tmp_path)
    folder=tmp_path/'outputs/hpc/source';rd=folder/'full/feedback-round2';rd.mkdir(parents=True)
    state={'status':'one_material_trial_accepted','history':[{}]*8,'active_map':None,'pending_feedback':None}
    summary={'protocol_sha256':'hash','gate_checks':{k:True for k in REQUIRED_GATES},
        'decision':{'finite_trial_accepted_as_one_nonlinear_step':True}}
    proto={'outer_iteration':{'index':4 if fault=='index' else 3,
        'physical_time_advanced':fault=='time','source':'actual-base'}}
    values={folder/'status.json':{'status':'formal_acceptance_requires_review','candidate':'full'},
        folder/'full/state.json':state,rd/'feedback_summary.json':summary,
        rd/'round_summary.json':{'protocol_sha256':'hash'},rd/'feedback_protocol.json':proto,
        rd/'fresh_control_comparison.json':fresh() if fault!='fresh' else {'comparisons':{}}}
    for p,d in values.items():p.write_text(json.dumps(d))
    monkeypatch.setattr(combined.pipeline,'claim',lambda p:{'sha256':'bad' if fault=='hash' else 'hash'})
    if fault=='none':
        combined.configure('outputs/hpc/source',3)
        assert combined.FORMAL_SOURCE=='actual-base' and combined.ACCEPTED_INDEX==3
    else:
        with pytest.raises(RuntimeError):combined.configure('outputs/hpc/source',3)


def test_preparation_refuses_changed_source_on_resume(monkeypatch,tmp_path):
    monkeypatch.setattr(combined.reused,'verify',lambda p:None)
    (tmp_path/'declaration.json').write_text(json.dumps({'pinned':[],'source':'wrong',
        'accepted_outer_step_index':3,'formal_source':combined.FORMAL_SOURCE}))
    with pytest.raises(RuntimeError,match='source changed'):combined.prepare_confirmation(tmp_path)
