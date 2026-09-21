from pathlib import Path
import signal
import subprocess
import sys
import time
import json
import numpy as np
import pytest
from operations import constrained_hybrid_fields as f
from operations import constrained_hybrid_batch as b


def test_linf_interval_and_safety_selection():
    raw=np.array([1.,.2,-.4]);change=np.array([0.,4.,-2.])
    upper=f.feasible_upper(raw,change,1.)
    assert upper==pytest.approx(.2)
    choice=f.choose_fraction(10.,3.,-2.,upper)
    assert choice['fraction']==pytest.approx(.18)
    assert np.max(abs(raw+choice['fraction']*change))<=1
    assert choice['feasible']


def test_no_descent_or_zero_interval_is_not_a_candidate():
    assert not f.choose_fraction(1.,2.,1.,1.)['feasible']
    assert not f.choose_fraction(1.,2.,-1.,0.)['feasible']
    assert f.feasible_upper(np.array([1.]),np.array([1.]),1.)==0
    with pytest.raises(ValueError):f.choose_fraction(0.,1.,-1.,1.)


def test_subnormal_unselected_values_stay_bitwise_unchanged(tmp_path):
    shape=(1920,1,1);x=np.ones(shape);x[0]=np.nextafter(0.,1.);u=x.copy();u[1792:]+=1
    a=tmp_path/'x.dat';z=tmp_path/'u.dat';x.tofile(a);u.tofile(z)
    out=tmp_path/'chosen.dat';half=tmp_path/'half.dat'
    f.write_convex(a,z,out,.18,shape);f.write_convex(a,out,half,.5,shape)
    chosen=np.fromfile(out,dtype='<f8').reshape(shape);h=np.fromfile(half,dtype='<f8').reshape(shape)
    assert np.array_equal(chosen[:1792],x[:1792]) and h[0]==x[0]
    assert np.array_equal(h[1792:],.5*x[1792:]+.5*chosen[1792:])


def test_short_or_negative_fields_rejected(tmp_path):
    p=tmp_path/'x.dat';np.ones(4).tofile(p)
    with pytest.raises(ValueError,match='truncated'):list(f.chunks([p],(5,1,1)))
    (-np.ones(4)).tofile(p)
    with pytest.raises(ValueError,match='negative'):list(f.chunks([p],(4,1,1)))


def test_scan_checks_all_components_and_boundaries(tmp_path):
    shape=(1920,1,1);x=np.ones(shape)*4;u=x.copy();u[1792:]+=1
    y=x+.2;v=y.copy();v[1792:]=u[1792:]+.01
    paths=[]
    for i,a in enumerate((x,y,u,v)):
        p=tmp_path/f'{i}.dat';a.tofile(p);paths.append(p)
    result=f.scan(paths,shape,lambda a,start:a[:,0,0],{'boundary_l1':1.,'boundary_bolometric':1.})
    assert result['fraction']>0
    assert result['prediction_is_not_validation'] is True
    assert result['checks']['selected_radiation'] is False # large true reference defect fails strict gate


def test_independent_half_detects_nonaffinity(tmp_path):
    shape=(1920,1,1);x=np.ones(shape)*2;u=x.copy();u[1792:]+=1;h=.5*x+.5*u
    op=lambda z: .5*z+2
    arrays=(x,op(x),u,op(u),h,op(h));paths=[]
    for i,a in enumerate(arrays):
        p=tmp_path/f'{i}.dat';a.tofile(p);paths.append(p)
    r=f.validate(paths,shape);assert r['fixed_scale_l2_ratios'][3]==0
    (op(h)+.01).tofile(paths[-1]);assert f.validate(paths,shape)['fixed_scale_l2_ratios'][3]>1e-6


def state(n=0,status='radiation',active=None,**extra):
    return dict(history=[{}]*n,status=status,active_map=active,**extra)


def test_accounting_survives_resource_failure(tmp_path):
    states={'B-base':state(1,'resource_gate_failed')}
    assert b.counts(states)['completed_maps']==1
    with pytest.raises(RuntimeError,match='fault'):b.validate_budget(states)
    folder=tmp_path/'B-base';folder.mkdir();b.pipeline.write_json(folder/'state.json',states['B-base'])
    b.mark(tmp_path,'failed');assert b.pipeline.read(tmp_path/'status.json')['completed_maps']==1


def test_seven_map_inventory_and_pending_pair_budget():
    states={k:state(n) for k,n in b.LIMITS.items()};states['B-base']['pending_feedback']={'stage':'ledger'}
    assert b.validate_budget(states)['completed_maps']==7
    states['B-base']['diagnostic']={'rounds':[{}]}
    with pytest.raises(RuntimeError,match='pair'):b.validate_budget(states)


def test_pilot_map_cannot_borrow_an_extra_map():
    with pytest.raises(RuntimeError,match='child map'):b.validate_budget({'P-trial':state(1,active={})})


def test_proxy_only_wraps_native_worker_commands():
    class Original:
        def Popen(self,cmd,*a,**k):return cmd
    proxy=b.RelayProcesses(Original())
    cmd=[sys.executable,'hpc/pipeline.py','worker','--report','outputs/block.json']
    wrapped=proxy.Popen(cmd)
    assert Path(wrapped[1]).name=='native_worker_relay.py' and wrapped[-len(cmd):]==cmd
    assert proxy.Popen(['git','status'])==['git','status']


def mock_execute(tmp_path,monkeypatch,feasible=True):
    events=[]
    monkeypatch.setattr(b,'setup',lambda out:({},{}))
    monkeypatch.setattr(b,'settle_all',lambda out:events.append('settle'))
    monkeypatch.setattr(b.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(b.reused,'archive',lambda *x:None)
    import shutil
    monkeypatch.setattr(shutil,'disk_usage',lambda out:type('D',(),{'free':10**14})())
    monkeypatch.setattr(b,'raw_pair',lambda out,label,*a:events.append('basis-'+label) or {})
    monkeypatch.setattr(b,'selection',lambda out,label,*a:{'feasible':feasible})
    monkeypatch.setattr(b,'validate_selected',lambda out,label,*a:events.append('validate-'+label) or {'passed':True})
    monkeypatch.setattr(b,'continue_feedback',lambda *a:events.append('feedback') or True)
    monkeypatch.setattr(b.reused,'stage_c',lambda *a:events.append('ledger'))
    p=tmp_path/'B-trial';p.mkdir();b.pipeline.write_json(p/'state.json',state(2,'one_material_trial_accepted'))
    return events


def test_success_immediately_chains_both_states_and_feedback(tmp_path,monkeypatch):
    events=mock_execute(tmp_path,monkeypatch);b.execute(tmp_path)
    assert events==['settle','basis-base','validate-base','basis-trial','validate-trial','feedback','ledger']
    assert b.pipeline.read(tmp_path/'status.json')['accepted_material_step']


def test_no_feasible_base_step_stops_before_trial_pilot(tmp_path,monkeypatch):
    events=mock_execute(tmp_path,monkeypatch,False);b.execute(tmp_path)
    assert events==['settle','basis-base']
    assert b.pipeline.read(tmp_path/'status.json')['status']=='science_rejected'


def test_pending_round_settles_before_any_other_stage(tmp_path,monkeypatch):
    folder=tmp_path/'B-base';folder.mkdir();b.pipeline.write_json(folder/'state.json',state(2,pending_feedback={'stage':'ledger'}))
    b.pipeline.write_json(folder/'config.json',{})
    called=[];monkeypatch.setattr(b.reused,'settle',lambda *args:called.append(args[-1]))
    b.settle_all(tmp_path);assert called==['base']


@pytest.mark.skipif(not Path('/proc/self/status').exists(),reason='Linux resource observations')
@pytest.mark.parametrize('code,expected',[(0,0),(7,7)])
def test_relay_propagates_exit_and_records_native_proc(tmp_path,code,expected):
    receipt=tmp_path/'relay.json'
    cmd=[sys.executable,str(b.ROOT/'operations/native_worker_relay.py'),'--receipt',str(receipt),'--',sys.executable,'-c',f'import time;time.sleep(.3);raise SystemExit({code})']
    p=subprocess.run(cmd);assert p.returncode==expected
    r=json.loads(receipt.read_text());assert r['returncode']==code and r['proc_sample_count']>0


@pytest.mark.skipif(not Path('/proc/self/status').exists(),reason='Linux process signal test')
def test_relay_usr1_finishes_worker_and_term_is_forwarded(tmp_path):
    for sig,expected in ((signal.SIGUSR1,0),(signal.SIGTERM,143)):
        receipt=tmp_path/f'{sig}.json';ready=tmp_path/f'{sig}.ready'
        code=f'import pathlib,time;pathlib.Path({str(ready)!r}).touch();time.sleep(.5)'
        p=subprocess.Popen([sys.executable,str(b.ROOT/'operations/native_worker_relay.py'),'--receipt',str(receipt),'--',sys.executable,'-c',code])
        for _ in range(100):
            if ready.exists():break
            time.sleep(.01)
        assert ready.exists();p.send_signal(sig);assert p.wait(timeout=3)==expected
        r=json.loads(receipt.read_text());assert int(sig) in r['signals']


@pytest.mark.skipif(not Path('/proc/self/status').exists(),reason='Linux independent memory gate')
def test_relay_never_hides_independent_memory_failure(tmp_path):
    receipt=tmp_path/'low-limit.json'
    p=subprocess.run([sys.executable,str(b.ROOT/'operations/native_worker_relay.py'),'--receipt',str(receipt),
        '--limit-kib','1','--',sys.executable,'-c','import time;time.sleep(.3)'])
    assert p.returncode==96
    assert json.loads(receipt.read_text())['memory_guard_passed'] is False


def test_physical_response_failure_keeps_ledgers_and_rejects_science(tmp_path,monkeypatch):
    events=mock_execute(tmp_path,monkeypatch)
    def response(*a):raise b.reused.pair.PhysicalDomainError('no positive gas heat')
    monkeypatch.setattr(b.reused,'stage_c',response)
    b.execute(tmp_path)
    assert b.pipeline.read(tmp_path/'status.json')['status']=='science_rejected'
    assert b.pipeline.read(tmp_path/'C-domain-rejection.json')['residual_comparison_complete'] is False
