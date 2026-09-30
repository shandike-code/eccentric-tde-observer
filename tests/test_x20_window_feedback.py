from copy import deepcopy
import pytest
from operations import x20_window_feedback as c


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


def test_independent_actual_validation_required():
    a=c.pipeline.read(c.ROOT/'handoff/evidence/20260930-x20-window-validation-review.json')
    s=dict(status='true_maps_validated_requires_review',new_maps=2,new_feedback_pairs=0,new_material_steps=0,validated=True,baseline_replaced=False)
    c.require_validation(a,s)
    for key,value in [('true_maps_independently_validated',False),('baseline_replaced',True),('job_id',81647),('new_material_steps',1)]:
        bad=deepcopy(a);bad[key]=value
        with pytest.raises(ValueError):c.require_validation(bad,s)


def test_actual_mac_seed_lineage_and_zero_protocol():
    root=c.ROOT/'outputs/review-20260925/x20-window-82214-received'
    if not root.exists():pytest.skip('Mac receipt; school validates real files before dispatch')
    actual=c.pipeline.read(root/'validation.json');full=c.pipeline.read(root/'full/state.json')
    rows=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,17)]
    history=dict(history=rows,active_map=None,current_sha256='16')
    ret=dict(history_rows=rows[-2:],endpoints={name:dict(path=name+'.dat',sha256=str(n),size_bytes=c.pipeline.STATE_BYTES) for name,n in [('final',15),('mapped_final',16)]})
    claims=c.seed_claims(actual,full,history,ret)
    assert claims['accelerated']['sha256']=='66d55283ee2e6c6cd52b38559deeb9ad994c693d258294ffc896e252745e524a'
    full['active_map']={}
    with pytest.raises(ValueError):c.seed_claims(actual,full,history,ret)


def test_source_operator_may_only_differ_in_seed_paths_and_budget():
    actual=dict(maximum_maps=1,run='a',warm_seed='a',sources=['a'],frequency_groups=9632)
    history=dict(maximum_maps=16,run='b',warm_seed='b',sources=['b'],frequency_groups=9632)
    c.seed_operator_config(actual,history)
    actual['frequency_groups']=1024
    with pytest.raises(ValueError):c.seed_operator_config(actual,history)


def test_real_82214_and_81769_sources_match_without_old_24_anchor():
    root=c.ROOT/'outputs/review-20260925'
    true=root/'x20-window-82214-received';prior=root/'x20-feedback-81769-complete-received'
    if not true.exists() or not prior.exists():pytest.skip('large-source archives are Mac review artifacts')
    seeds=c.seed_claims(c.pipeline.read(true/'validation.json'),c.pipeline.read(true/'full/state.json'),
        c.pipeline.read(prior/'historical/state.json'),c.pipeline.read(prior/'historical/endpoints-map16/manifest.json'))
    assert seeds['historical']==c.pipeline.read(true/'declaration.json')['basis'][3]
    c.seed_operator_config(c.pipeline.read(true/'full/config.json'),c.pipeline.read(prior/'historical/config.json'))
    c.fixed.same_trial(c.v.load_arrays(true/'full/trial_material.npz'),c.v.load_arrays(prior/'historical/trial_material.npz'))
    bad=c.pipeline.read(prior/'historical/config.json');bad['maximum_maps']=24
    with pytest.raises(ValueError):c.seed_operator_config(c.pipeline.read(true/'full/config.json'),bad)
