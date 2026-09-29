from copy import deepcopy
import numpy as np
import pytest
from operations import calibrate_x20_radiation_histories as c


def test_equal_scalar_norms_cannot_hide_changed_vector():
    r=np.ones(8);a={'previous':r.copy(),'final':r.copy()};b={k:-v for k,v in a.items()}
    assert c.vector_comparison(a,a,r,np.ones(2),np.ones(3))['passed']
    q=c.vector_comparison(a,b,r,np.ones(2),np.ones(3))
    assert not q['passed'] and all(x==[2.,2.,2.] for x in q['frozen_r20']['vector_difference_over_frozen_r20_norms'].values())


def test_signal_gate_remains_independent_of_reference_gate():
    r=np.ones(8);a={k:r.copy() for k in ('previous','final')};b={k:v+1e-5 for k,v in a.items()}
    q=c.vector_comparison(a,b,r,np.ones(2),np.full(3,1e-8))
    assert q['frozen_r20']['passed'] and not q['signal_pass'] and not q['passed']
    assert not q['baseline_replaced'] and not q['strict_error_bound']


@pytest.mark.parametrize('scale',[[1,0,1],[1,np.nan,1],[1,1],[-1,1,1]])
def test_no_signal_floor_or_missing_component(scale):
    r=np.ones(8);a={k:r for k in ('previous','final')}
    with pytest.raises(ValueError):c.vector_comparison(a,a,r,np.ones(2),scale)


@pytest.mark.parametrize('stop_at',range(4))
def test_failure_stops_before_dispatching_later_work(stop_at):
    visited=[]
    def evaluate(name,n):
        visited.append((name,n));return 'failure' if len(visited)==stop_at+1 else 'pass'
    assert c.sequence(evaluate).endswith('_failure')
    assert visited==[('historical',16),('late',16),('historical',24),('late',24)][:stop_at+1]


def seed_data():
    rows=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,11)]
    h=dict(path='old/final.dat',sha256='old',size_bytes=c.pipeline.STATE_BYTES)
    late=dict(path='retained/mapped.dat',sha256='10',size_bytes=c.pipeline.STATE_BYTES)
    return {'sources':{'final_radiation':h}},dict(history=rows,active_map=None,current_sha256='10'),dict(history_rows=rows[-2:],endpoints={'mapped_final':late})


def test_seed_requires_settled_ten_maps_and_distinct_histories():
    p,s,r=seed_data();assert c.source_seed(p,s,r)['historical']==p['sources']['final_radiation']
    s['active_map']={}
    with pytest.raises(RuntimeError):c.source_seed(p,s,r)
    s['active_map']=None;p['sources']['final_radiation']['sha256']='10'
    with pytest.raises(RuntimeError):c.source_seed(p,s,r)
    p,s,r=seed_data();s['history'][5]['input_sha256']='broken'
    with pytest.raises(RuntimeError):c.source_seed(p,s,r)


def test_map_budget_does_not_inherit_old_sixteen_map_cap(tmp_path,monkeypatch):
    state=dict(history=[{}]*16,status='radiation');driver=c.old.recovery.original.driver
    def fake(folder,cfg,st,path):
        st['history'].append({});work=folder/'map0017';work.mkdir()
        for i in range(76):c.pipeline.write_json(work/f'block{i:02d}.process-1.json',dict(returncode=0,memory_guard_passed=True,native_observed_peak_kib=1024))
        return True
    monkeypatch.setattr(driver,'run_one_map',fake);monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    c.map_once(tmp_path,{},state,24);assert len(state['history'])==17
    state['history']=[{}]*24
    with pytest.raises(RuntimeError):c.map_once(tmp_path,{},state,24)
    with pytest.raises(RuntimeError):c.map_once(tmp_path,{},state,25)


def test_partial_map_never_becomes_a_committed_map(tmp_path,monkeypatch):
    monkeypatch.setattr(c.old.recovery.original.driver,'run_one_map',lambda *args:False)
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    with pytest.raises(c.reused.Stopped):c.map_once(tmp_path,{},dict(history=[]),24)


def test_actual_replay_required_and_no_rebase():
    a=c.pipeline.read(c.ROOT/'handoff/evidence/20260929-response-replay-review.json')
    s=dict(status='complete_requires_review',all_replays_passed=True,new_maps=0,new_feedback_integrations=0,baseline_replaced=False)
    c.require_replay(a,s)
    for key,value in [('baseline_replaced',True),('all_ten_endpoints_bitwise_equal',False),('job_id',80195)]:
        bad=deepcopy(a);bad[key]=value
        with pytest.raises(RuntimeError):c.require_replay(bad,s)


def test_real_mac_inputs_and_zero_protocol_factory(tmp_path):
    root=c.ROOT/'outputs/review-20260925/boundary-response-80195-received'
    accepted=c.ROOT/'outputs/review-20260924/common-confirmation20-76727-received/confirm2'
    if not root.exists():pytest.skip('Mac extraction only; batch verifies school archives')
    read=c.pipeline.read
    p=read(accepted/'common-feedback/feedback_protocol.json');state=read(root/'control/state.json');ret=read(root/'control/endpoints-map10/manifest.json')
    assert c.source_seed(p,state,ret)['historical']['sha256']=='96322faea9c1a4d57b6ebde26db7e27160794c9cd412bb45ab62813d747aac07'
    finite=read(root/'population/pair10/feedback_protocol.json');zero=read(root/'control/pair10/feedback_protocol.json')
    proto=c.directions.make_protocol(finite,zero,c.ROOT/'outputs/test-history-control',ret,zero['sources']['trial_material'],
        zero['sources']['retained_manifest'],zero['sources']['refreshed_direction_declaration'],'control')
    assert not proto['authorization']['accept_material_step'] and proto['authorization']['zero_displacement_control']
    assert proto['acceptance_gates']==zero['acceptance_gates']
