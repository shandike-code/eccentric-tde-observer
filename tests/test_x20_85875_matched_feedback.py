from copy import deepcopy
import pytest
from operations import x20_85875_matched_feedback as c


def test_sequence_completes_both_matched_windows():
    visited=[]
    def evaluate(name,n):
        visited.append((name,n));return 'pass'
    assert c.sequence(evaluate)=='paired_seed_windows_complete_requires_review'
    assert visited==[('accelerated',8),('historical',8),('accelerated',16),('historical',16)]


@pytest.mark.parametrize('stop_at',range(4))
def test_hard_gate_stops_before_later_work(stop_at):
    visited=[]
    def evaluate(name,n):
        visited.append((name,n));return 'physical_domain_rejected' if len(visited)==stop_at+1 else 'pass'
    assert c.sequence(evaluate).endswith('_physical_domain_rejected')
    assert len(visited)==stop_at+1


def experiment():
    row=dict(feedback_evaluated=True,zero_pair_stable=True,physical_response_failures={},original_zero_gates={str(i):True for i in range(7)},eight_map_window={'passed':True})
    return {name:{str(n):deepcopy(row) for n in (8,16)} for name in c.LIMITS},{str(n):dict(residual_comparison={'passed':True},cross_rate_pass=True) for n in (8,16)}


def test_all_windows_and_original_quality_required_without_rebase():
    reports,cross=experiment();terminal='paired_seed_windows_complete_requires_review'
    assert c.calibration_eligible(terminal,reports,cross)
    cross['8']['residual_comparison']['passed']=False
    assert c.calibration_eligible(terminal,reports,cross) # first window is measurement
    reports['accelerated']['16']['eight_map_window']['passed']=False
    assert not c.calibration_eligible(terminal,reports,cross)
    reports,cross=experiment();cross['16']['cross_rate_pass']=False
    assert not c.calibration_eligible(terminal,reports,cross)
    reports,cross=experiment();reports['historical']['8']['original_zero_gates']['0']=False
    assert not c.calibration_eligible(terminal,reports,cross)
    reports,cross=experiment();reports['accelerated']['16']['physical_response_failures']={'cell':43}
    assert not c.calibration_eligible(terminal,reports,cross)
    assert not c.calibration_eligible('interrupted',reports,cross)


def test_missing_pair_cannot_become_eligible():
    reports,cross=experiment();del reports['historical']['16']
    with pytest.raises(ValueError):c.calibration_eligible('paired_seed_windows_complete_requires_review',reports,cross)


def make_receipts(tmp_path,st,peak=1024,delta=1,active=None):
    st['history'] += [{}]*delta;st['active_map']=active
    work=tmp_path/f"map{len(st['history']):04d}";work.mkdir()
    for i in range(76):c.pipeline.write_json(work/f'block{i:02d}.process-1.json',dict(returncode=0,memory_guard_passed=True,native_observed_peak_kib=peak))
    return True


def test_sixteen_map_cap_and_exact_kib_boundary(tmp_path,monkeypatch):
    st=dict(history=[{}]*15,status='radiation',active_map=None)
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(c.old.recovery.original.driver,'run_one_map',lambda folder,cfg,state,path:make_receipts(folder,state,6*1024**2-1))
    c.map_once(tmp_path,{},st,16)
    assert len(st['history'])==16
    with pytest.raises(RuntimeError):c.map_once(tmp_path,{},st,16)
    with pytest.raises(RuntimeError):c.map_once(tmp_path,{},dict(history=[]),17)


@pytest.mark.parametrize('peak,delta,active',[(6*1024**2,1,None),(1024,0,None),(1024,2,None),(1024,1,{})])
def test_resource_and_commit_faults_stop(tmp_path,monkeypatch,peak,delta,active):
    st=dict(history=[],status='radiation',active_map=None)
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(c.old.recovery.original.driver,'run_one_map',lambda folder,cfg,state,path:make_receipts(folder,state,peak,delta,active))
    with pytest.raises(RuntimeError):c.map_once(tmp_path,{},st,16)


def test_partial_map_is_not_feedback_ready(tmp_path,monkeypatch):
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(c.old.recovery.original.driver,'run_one_map',lambda *args:False)
    with pytest.raises(c.reused.Stopped):c.map_once(tmp_path,{},dict(history=[]),16)


def sources():
    folders=dict(accelerated='x20-global-feedback-82518-complete-received',historical='x20-85861-feedback-85875-received')
    for name,folder in folders.items():
        p=c.ROOT/'outputs/review-20260925'/folder
        if not (p/name/'state.json').exists():p=c.ROOT/c.SOURCES[name][0]
        yield name,p


def test_real_sources_trial_operator_and_mapped_output():
    cfgs=[];trials=[]
    for name,p in sources():
        _,_,ap,tp=c.SOURCES[name]
        c.require_source(c.pipeline.read(c.ROOT/'handoff/evidence'/ap),c.pipeline.read(p/'summary.json'),name)
        state=c.pipeline.read(p/name/'state.json');manifest=c.pipeline.read(p/name/'endpoints-map16/manifest.json')
        seed=c.seed_claim(name,state,manifest)
        assert seed['sha256']==c.SEED_SHA[name] and seed!=manifest['endpoints']['final']
        cfgs.append(c.pipeline.read(p/name/'config.json'));trials.append(c.v.load_arrays(p/name/'trial_material.npz'))
        for damage in ('final','sha','history','partial'):
            bad=deepcopy(manifest);st=deepcopy(state)
            if damage=='final':bad['endpoints']['mapped_final']=bad['endpoints']['final']
            if damage=='sha':bad['endpoints']['mapped_final']['sha256']='0'*64
            if damage=='history':st['history'][-1]['output_sha256']='0'*64
            if damage=='partial':st['active_map']={}
            with pytest.raises(ValueError):c.seed_claim(name,st,bad)
    c.core.same_operator_config(*cfgs);c.fixed.same_trial(*trials)
    bad=deepcopy(cfgs[0]);bad['maximum_maps']=24
    with pytest.raises(ValueError):c.core.same_operator_config(bad,cfgs[1])
    bad=deepcopy(trials[0]);bad['step_duration_s']=bad['step_duration_s']*2
    with pytest.raises(Exception):c.fixed.same_trial(bad,trials[1])


@pytest.mark.parametrize('key,value',[('completed_experiment',False),('independent_vector_reduction',False),('map_process_receipts',0),('reference_calibration_eligible',True),('new_material_steps',1),('all_original_zero_gates_passed',False)])
def test_source_review_negative_paths(key,value):
    for name,p in sources():
        audit=c.pipeline.read(c.ROOT/'handoff/evidence'/c.SOURCES[name][2]);audit[key]=value
        with pytest.raises(ValueError):c.require_source(audit,c.pipeline.read(p/'summary.json'),name)


@pytest.mark.parametrize('key,value',[('source_84026_scheduler_terminal_verified',True),('source_85821_scheduler_terminal_verified',False),('scheduler_terminal_verified',False),('child_exit_status',False),('numerical_commit','old')])
def test_85875_ancestry_and_real_exit_cannot_be_invented(key,value):
    name,p=list(sources())[1];audit=c.pipeline.read(c.ROOT/'handoff/evidence'/c.SOURCES[name][2]);audit[key]=value
    with pytest.raises(ValueError):c.require_source(audit,c.pipeline.read(p/'summary.json'),name)


def test_actual_80195_four_vector_signal_reduction():
    import numpy as np
    from handoff.audit_tools.review_step21_control_windows import independent_norms
    root=c.ROOT/'outputs/review-20260925/boundary-response-80195-received'
    if not (root/'control/pair10/final_response.npz').exists():root=c.ROOT/c.prior.CURRENT
    protocol=c.pipeline.read(root/'control/pair10/feedback_protocol.json')
    oldpath=c.ROOT/protocol['sources']['physical_old_time_level']['path']
    if not oldpath.exists():oldpath=c.ROOT/'outputs/review-20260921/common-feedback-bridge-75943-received/inputs/physical_old_time_level.npz'
    mass=c.v.load_arrays(oldpath)['cell_mass_g_cm2']
    vec={name:{e:c.v.load_arrays(root/f'{name}/pair10/{e}_response.npz')['residual'] for e in ('previous','final')} for name in ('control','population')}
    scale=np.min([c.directions.norm_vector(p-q,mass) for p in vec['population'].values() for q in vec['control'].values()],axis=0)
    independent=np.min([independent_norms(p-q,mass) for p in vec['population'].values() for q in vec['control'].values()],axis=0)
    np.testing.assert_allclose(scale,independent,rtol=1e-12,atol=0)
    for _,folder in sources():
        d=c.pipeline.read(folder/'declaration.json')
        np.testing.assert_allclose(scale,[d['frozen_signal_scale'][k] for k in c.NORMS],rtol=1e-12,atol=0)
