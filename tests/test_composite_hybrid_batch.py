"""Synthetic protocol/control tests: no Slurm, no physical workload."""
from pathlib import Path
from copy import deepcopy
import numpy as np
import pytest
from operations import composite_hybrid_batch as b
from operations import composite_hybrid_audit as a


def state(n=0,active=False,**kw):
    return {'history':[{} for _ in range(n)],'active_map':{} if active else None,'status':'radiation',**kw}


def test_budget_counts_active_and_completed_without_reset():
    assert b.budget({'A-base-full':state(active=True),'B-base':state(1,True)})['maps_committed_or_active']==3
    with pytest.raises(RuntimeError,match='budget'):b.budget({'A-base-full':state(1,True)})


def test_budget_includes_pending_pair_and_rejects_second():
    s=state(2,pending_feedback={'stage':'ledger'})
    assert b.budget({'B-base':s})['feedback_pairs_completed_or_pending']==1
    s['diagnostic']={'rounds':[{}]}
    with pytest.raises(RuntimeError):b.budget({'B-base':s})


def test_failure_precedes_exhaustion():
    s=state(2);s['status']='resource_gate_failed'
    with pytest.raises(RuntimeError,match='fault'):b.budget({'B-base':s})


def test_signal_reaches_actual_dispatch_flag(monkeypatch):
    monkeypatch.setattr(b.pipeline,'STOP',False);monkeypatch.setattr(b.driver,'STOP',False)
    b.stop(None,None)
    assert b.pipeline.STOP and b.driver.STOP
    with pytest.raises(b.Stopped):b.checkpoint()


def test_immutable_refuses_changes(tmp_path):
    p=tmp_path/'plan.json';b.immutable(p,{'maps':8});b.immutable(p,{'maps':8})
    with pytest.raises(RuntimeError):b.immutable(p,{'maps':9})


def test_terminal_cannot_be_overwritten(tmp_path):
    b.mark(tmp_path,'failed')
    with pytest.raises(RuntimeError,match='terminal'):b.mark(tmp_path,'complete')


def test_partial_maps_stop_before_more_work(tmp_path,monkeypatch):
    s=state();cfg={};events=[]
    monkeypatch.setattr(b,'child',lambda *x:(tmp_path,cfg,s))
    monkeypatch.setattr(b,'child_states',lambda *x:{'A-base-full':s})
    monkeypatch.setattr(b,'settle',lambda *x:events.append('settle'))
    monkeypatch.setattr(b,'checkpoint',lambda:None)
    monkeypatch.setattr(b.driver,'run_one_map',lambda *x:events.append('map') or False)
    with pytest.raises(b.Stopped):b.maps(tmp_path,'A-base-full','base',{}, {})
    assert events==['settle','map']


def test_pending_feedback_settled_before_map(tmp_path,monkeypatch):
    s=state(1,pending_feedback={'stage':'ledger'});events=[]
    monkeypatch.setattr(b,'child',lambda *x:(tmp_path,{},s))
    monkeypatch.setattr(b,'child_states',lambda *x:{'B-trial':s})
    def settle(*args):events.append('feedback');s.pop('pending_feedback')
    def mapped(*args):events.append('map');s['history'].append({});return True
    monkeypatch.setattr(b,'settle',settle);monkeypatch.setattr(b,'checkpoint',lambda:None)
    monkeypatch.setattr(b.driver,'run_one_map',mapped)
    b.maps(tmp_path,'B-trial','trial',{},{});assert events==['feedback','map']


def mock_execute(monkeypatch,tmp_path,passed=True):
    events=[]
    monkeypatch.setattr(b,'prepare',lambda out:{})
    monkeypatch.setattr(b,'checkpoint',lambda:None)
    monkeypatch.setattr(b.shutil,'disk_usage',lambda out:type('D',(),{'free':10**14})())
    monkeypatch.setattr(b,'corrections',lambda out:events.append('corrections'))
    monkeypatch.setattr(b,'stage_a',lambda *args:events.append('A') or {'passed':passed})
    monkeypatch.setattr(b,'stage_b',lambda *args:events.append('B') or True)
    monkeypatch.setattr(b,'stage_c',lambda *args:events.append('C'))
    monkeypatch.setattr(b,'archive',lambda *args:None)
    folder=tmp_path/'B-trial';folder.mkdir();s=state(2);s['status']='one_material_trial_accepted';b.pipeline.write_json(folder/'state.json',s)
    return events


def test_success_chains_all_stages_same_invocation(tmp_path,monkeypatch):
    events=mock_execute(monkeypatch,tmp_path);b.execute(tmp_path)
    assert events==['corrections','A','B','C']
    assert b.pipeline.read(tmp_path/'status.json')['accepted_material_step'] is True


def test_a_failure_never_runs_b_or_c(tmp_path,monkeypatch):
    events=mock_execute(monkeypatch,tmp_path,False);b.execute(tmp_path)
    assert events==['corrections','A']
    assert b.pipeline.read(tmp_path/'status.json')['status']=='science_rejected'


def test_hybrid_keeps_every_untouched_group(tmp_path):
    shape=(256,2,2);x=np.arange(np.prod(shape),dtype=float).reshape(shape)+1
    src=tmp_path/'x.dat';x.tofile(src);target=x[:128]*1.1
    repl=tmp_path/'r.npy';np.save(repl,target)
    out=tmp_path/'h.dat';a.hybrid(src,out,{0:repl},.5,shape)
    got=np.memmap(out,mode='r',dtype='<f8',shape=shape)
    assert np.array_equal(got[:128],.5*x[:128]+.5*target)
    assert np.array_equal(got[128:],x[128:])
    with pytest.raises(FileExistsError):a.hybrid(src,out,{0:repl},.5,shape)


def test_negative_correction_is_rejected_without_floor(tmp_path):
    shape=(128,1,1);src=tmp_path/'x.dat';np.ones(shape).tofile(src)
    r=tmp_path/'r.npy';np.save(r,-np.ones(shape))
    with pytest.raises(ValueError,match='negative'):a.hybrid(src,tmp_path/'y.dat',{0:r},1.,shape)


def field_fixture(tmp_path,nonlinear=False):
    shape=(256,1,1);x=np.ones(shape)*2;u=x.copy();u[:128]+=1;h=.5*x+.5*u
    f=lambda z:.5*z+2
    arrays=[x,f(x),u,f(u),h,f(h)]
    if nonlinear:arrays[-1]=arrays[-1]+.01
    paths=[]
    for i,v in enumerate(arrays):
        p=tmp_path/f'{i}.dat';v.tofile(p);paths.append(p)
    return a.audit(paths,shape,corrected=(0,))


def test_full_field_probe_tests_internal_half_not_duplicate_endpoint(tmp_path):
    r=field_fixture(tmp_path);assert r['fixed_scale_l2_ratios'][3]==0
    assert len(r['blocks'])==2 and r['all_groups_evaluated']==256


def test_nonlinearity_fails_predeclared_gate(tmp_path):
    r=field_fixture(tmp_path,True);row={'residual':1e-5,'boundary_l1':1e-5,'boundary_bolometric':1e-5}
    assert a.checks(r,row,row,row)['independent_half_affinity'] is False


def test_no_substitution_of_strict_radiation_gate(tmp_path):
    r=field_fixture(tmp_path);row={'residual':2e-4,'boundary_l1':1e-5,'boundary_bolometric':1e-5}
    assert a.checks(r,row,row,row)['full_radiation'] is False


def test_feedback_stop_finishes_current_batch_and_commits_before_next(monkeypatch):
    events=[]
    monkeypatch.setattr(b.pipeline,'STOP',False)
    class P:
        def Popen(self,*args,**kw):
            events.append('start')
            b.pipeline.STOP=True
            return object()
    original_processes=P()
    def evaluator(protocol,*args):
        for batch in range(2):
            for _ in range(2):b.pair.subprocess.Popen('worker')
            events.append('commit')
    monkeypatch.setattr(b.pair,'subprocess',original_processes)
    monkeypatch.setattr(b.pair,'_run_feedback_state',evaluator)
    with pytest.raises(b.Stopped):
        with b.feedback_stop_guard():
            b.pair._run_feedback_state({'configuration':{'maximum_concurrent_processes':2}})
    assert events==['start','start','commit']
    assert b.pair._run_feedback_state is evaluator
    assert b.pair.subprocess is original_processes


def test_resumed_pending_ledger_precedes_all_stage_work(tmp_path,monkeypatch):
    events=mock_execute(monkeypatch,tmp_path)
    path=tmp_path/'B-trial/state.json';s=b.pipeline.read(path)
    s.update(status='diagnosis_incomplete',pending_feedback={'stage':'ledger'})
    b.pipeline.write_json(path,s);b.pipeline.write_json(tmp_path/'B-trial/config.json',{})
    def settle(folder,cfg,state,path,label):
        events.append('owed-ledger');state.pop('pending_feedback');state['status']='radiation';b.pipeline.write_json(path,state)
    monkeypatch.setattr(b,'settle',settle)
    b.execute(tmp_path)
    assert events==['owed-ledger','corrections','A','B','C']


def test_capture_keeps_native_timing_scope_and_restores_adapter(tmp_path,monkeypatch):
    events=[];original=b.local.evaluate_direction
    monkeypatch.setattr(b,'ROOT',tmp_path)
    monkeypatch.setattr(b.pipeline,'claim',lambda p:{'path':p.name,'sha256':b.pipeline.sha256(p),'size_bytes':p.stat().st_size})
    def evaluation(*args):return np.ones(2),np.ones(2),{}
    monkeypatch.setattr(b.local,'evaluate_direction',evaluation)
    def worker(out,label,index):
        b.local.evaluate_direction(None,None,np.ones(2),None)
        assert not list(out.glob('*.npy')) # array I/O must follow native cost measurement
        b.pipeline.write_json(out/'base-block14.json',{'eligible_for_further_block_review':True})
        events.append('native-finished')
    monkeypatch.setattr(b.local,'worker',worker)
    b.capture_worker(tmp_path,'base',14)
    assert b.local.evaluate_direction is evaluation
    receipt=b.pipeline.read(tmp_path/'base-block14-receipt.json')
    assert set(receipt['arrays'])=={'candidate','direction'} and receipt['passed']
    assert events==['native-finished']
