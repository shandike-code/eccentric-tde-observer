from copy import deepcopy
from types import SimpleNamespace
import signal
import pytest
from operations import pilot_step21_heating_blocks as pilot


def pair():
    rows=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,11)]
    return dict(history=rows,active_map=None),dict(history_rows=rows[-2:],endpoints={'final':dict(sha256='9'),'mapped_final':dict(sha256='10')})


def test_selects_last_actual_input_and_successor_not_previous_feedback():
    st,r=pair();assert pilot.settled_pair(st,r)==({'sha256':'9'},{'sha256':'10'})


@pytest.mark.parametrize('kind',['active','count','lineage','retained','input','output'])
def test_corrupt_or_partial_source_refused(kind):
    st,r=pair();st=deepcopy(st);r=deepcopy(r)
    if kind=='active':st['active_map']={}
    if kind=='count':st['history'].pop()
    if kind=='lineage':st['history'][3]['input_sha256']='other'
    if kind=='retained':r['history_rows'][0]['iteration']=0
    if kind=='input':r['endpoints']['final']['sha256']='old'
    if kind=='output':r['endpoints']['mapped_final']['sha256']='old'
    with pytest.raises(RuntimeError):pilot.settled_pair(st,r)


def test_stop_terminates_process_group_and_refuses_success(monkeypatch):
    calls=[]
    proc=SimpleNamespace(pid=123,returncode=0,poll=lambda:None,wait=lambda **kw:calls.append(('wait',kw)))
    monkeypatch.setattr(pilot.subprocess,'Popen',lambda *a,**kw:proc)
    monkeypatch.setattr(pilot.pipeline,'STOP',True)
    monkeypatch.setattr(pilot.os,'killpg',lambda pid,sig:calls.append((pid,sig)))
    with pytest.raises(RuntimeError,match='stopped'):pilot.bounded_process(['mock'],None,None)
    assert calls[0]==(123,signal.SIGTERM)


def test_worker_failure_is_not_scientific_completion(monkeypatch):
    proc=SimpleNamespace(returncode=7,poll=lambda:7)
    monkeypatch.setattr(pilot.subprocess,'Popen',lambda *a,**kw:proc)
    with pytest.raises(RuntimeError,match='failed'):pilot.bounded_process(['mock'],None,None)
