import json
from types import SimpleNamespace
import pytest
from operations import bounded_outer_sequence as seq


def harness(monkeypatch,tmp_path,fail_cycle=None,ready=True,final_pass=True):
    monkeypatch.setattr(seq,'ROOT',tmp_path)
    monkeypatch.setattr(seq,'declare',lambda p:None)
    monkeypatch.setattr(seq,'budget',lambda p:{'maps_committed_or_active':0,'pairs_completed_or_pending':0})
    monkeypatch.setattr(seq.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(seq.reused,'archive',lambda *a:None)
    monkeypatch.setattr(__import__('shutil'),'disk_usage',lambda p:SimpleNamespace(free=10**15))
    events=[]
    monkeypatch.setattr(seq.stage,'configure',lambda source,index:events.append(('source',index,source)))
    monkeypatch.setattr(seq,'transition',lambda out,index,source:(out/f'accepted-step{index}.json').write_text('{}'))
    def execute(folder):
        i=int(folder.name[4:]);events.append(('cycle',i))
        assert (folder.parent/f'accepted-step{i-1}.json').exists()
        seq.pipeline.write_json(folder/'status.json',{'status':'science_stopped' if i==fail_cycle else 'formal_acceptance_requires_review',
            'fresh_control_corroborated':True})
    monkeypatch.setattr(seq.stage,'execute',execute)
    monkeypatch.setattr(seq,'continuation_ready',lambda p:ready)
    monkeypatch.setattr(seq.stage,'run_confirmation',lambda p:events.append(('tail',6)))
    monkeypatch.setattr(seq.stage,'confirmation_passed',lambda p:final_pass)
    return events


def test_three_conditional_steps_and_tail_in_one_call_then_terminal(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path)
    seq.execute(tmp_path)
    assert [x for x in events if x[0]=='cycle']==[('cycle',4),('cycle',5),('cycle',6)]
    assert events[-1]==('tail',6)
    assert [x[1] for x in events if x[0]=='source']==[3,4,5,6]
    d=seq.pipeline.read(tmp_path/'status.json');assert d['status']=='complete_requires_review'
    assert d['new_accepted_steps']==3 and d['coupled_column_accepted'] is False
    n=len(events);seq.execute(tmp_path);assert len(events)==n


@pytest.mark.parametrize('fail_cycle',[4,5,6])
def test_science_stop_never_dispatches_later_stage(monkeypatch,tmp_path,fail_cycle):
    events=harness(monkeypatch,tmp_path,fail_cycle=fail_cycle);seq.execute(tmp_path)
    assert [x[1] for x in events if x[0]=='cycle']==list(range(4,fail_cycle+1))
    assert not any(x[0]=='tail' for x in events)
    assert seq.pipeline.read(tmp_path/'status.json')['status']=='science_stopped'


def test_half_or_early_acceptance_preserved_without_unsupported_auto_resume(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path,ready=False);seq.execute(tmp_path)
    assert [x for x in events if x[0]=='cycle']==[('cycle',4)]
    assert seq.pipeline.read(tmp_path/'status.json')['status']=='accepted_shape_requires_review'


def test_final_confirmation_failure_does_not_claim_completed_column(monkeypatch,tmp_path):
    harness(monkeypatch,tmp_path,final_pass=False);seq.execute(tmp_path)
    assert seq.pipeline.read(tmp_path/'status.json')['status']=='science_stopped'


def test_signal_between_cycles_dispatches_no_next_step(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path)
    def check():
        if ('cycle',4) in events:raise seq.reused.Stopped('signal')
    monkeypatch.setattr(seq.reused,'checkpoint',check)
    with pytest.raises(seq.reused.Stopped):seq.execute(tmp_path)
    assert not any(x==('cycle',5) for x in events)


def test_program_fault_propagates_without_later_stage(monkeypatch,tmp_path):
    events=harness(monkeypatch,tmp_path)
    def fail(p):raise RuntimeError('worker failure')
    monkeypatch.setattr(seq.stage,'execute',fail)
    with pytest.raises(RuntimeError,match='worker failure'):seq.execute(tmp_path)
    assert len([x for x in events if x[0]=='source'])==1


def test_global_budget_counts_three_cycles_plus_final_pending(monkeypatch,tmp_path):
    monkeypatch.setattr(seq.stage,'budget',lambda p:{'maps_committed_or_active':24,'pairs_completed_or_pending':8})
    monkeypatch.setattr(seq.stage.confirm,'budget',lambda p:None)
    monkeypatch.setattr(seq.stage.confirm,'states',lambda p:{})
    tail={'completed_maps':5,'active_maps':1,'completed_pairs':2,'pending_pairs':1}
    monkeypatch.setattr(seq.stage,'counts',lambda p:tail)
    assert seq.budget(tmp_path)['maps_committed_or_active']==78
    assert seq.budget(tmp_path)['pairs_completed_or_pending']==27
    tail['active_maps']=2
    with pytest.raises(RuntimeError,match='budget'):seq.budget(tmp_path)


def test_cycle_failure_precedes_global_budget(monkeypatch,tmp_path):
    p=tmp_path/'step4';p.mkdir();seq.pipeline.write_json(p/'status.json',{'status':'failed'})
    with pytest.raises(RuntimeError,match='failure'):seq.budget(tmp_path)
    seq.mark(tmp_path,'failed',error='preserved')
    with pytest.raises(RuntimeError,match='terminal'):seq.mark(tmp_path,'running')


@pytest.mark.parametrize('maps,candidate,active,pending,expected',[
    (8,'full',None,None,True),(4,'full',None,None,False),
    (8,'half',None,None,False),(8,'full',{},None,False),(8,'full',None,{'stage':'ledger'},False)])
def test_source_shape_contract(tmp_path,maps,candidate,active,pending,expected):
    (tmp_path/'full').mkdir()
    seq.pipeline.write_json(tmp_path/'status.json',{'status':'formal_acceptance_requires_review','candidate':candidate})
    seq.pipeline.write_json(tmp_path/'full/state.json',{'history':[{}]*maps,'active_map':active,
        'pending_feedback':pending,'diagnostic':{'rounds':[{},{}]}})
    assert seq.continuation_ready(tmp_path) is expected


def test_resume_refuses_mutated_sequence_budget(monkeypatch,tmp_path):
    monkeypatch.setattr(seq.reused,'verify',lambda p:None)
    seq.pipeline.write_json(tmp_path/'declaration.json',{'pinned':[],'source':seq.SOURCE,'maximum_maps':1000})
    with pytest.raises(RuntimeError,match='contract changed'):seq.declare(tmp_path)
