import json
from copy import deepcopy
import numpy as np
import pytest
from handoff.audit_tools import review_x20_85875_matched_feedback as a


def write_pair(root,name,n,**kw):
    folder=root/name/f'pair{n:02d}';folder.mkdir(parents=True)
    d=dict(physical_response_failures={},zero_pair_stable=True,continuation_pass=True,**kw)
    (folder/'decision.json').write_text(json.dumps(d))


def test_first_pair_is_partial_without_inventing_other_branch(tmp_path):
    write_pair(tmp_path,'accelerated',8)
    assert a.settled_entries(tmp_path)==[('accelerated',8)]
    assert a.qualification({'accelerated8':{}},{},False) is None
    with pytest.raises(AssertionError):a.qualification({'accelerated8':{}},{},True)


def test_missing_earlier_window_cannot_look_complete(tmp_path):
    write_pair(tmp_path,'accelerated',8);write_pair(tmp_path,'accelerated',16)
    with pytest.raises(AssertionError):a.settled_entries(tmp_path)


@pytest.mark.parametrize('field,value',[('physical_response_failures',{'cell43':'nonpositive'}),('zero_pair_stable',False),('continuation_pass',False)])
def test_hard_failure_requests_failure_audit_instead_of_success(tmp_path,field,value):
    write_pair(tmp_path,'accelerated',8)
    p=tmp_path/'accelerated/pair08/decision.json';d=json.loads(p.read_text());d[field]=value;p.write_text(json.dumps(d))
    with pytest.raises(ValueError,match='dedicated failure audit'):a.settled_entries(tmp_path)


def test_final_qualification_requires_both_windows_and_cross_rates():
    pairs={name+str(n):{'eight_map_window':{'passed':True}} for name,n in a.ORDER}
    cross={str(n):dict(residual_comparison={'passed':True},cross_rate_pass=True) for n in (8,16)}
    assert a.qualification(pairs,cross,True)
    for name in ('accelerated','historical'):
        bad=deepcopy(pairs);bad[name+'16']['eight_map_window']['passed']=False
        assert not a.qualification(bad,cross,True)
    cross['16']['cross_rate_pass']=False
    assert not a.qualification(pairs,cross,True)


def test_zero_vector_has_no_arbitrary_localization_floor():
    z=a.localization(np.zeros(512),np.ones(128))
    assert z['mass_norm_squared']==0 and z['component_fractions'] is None and z['cell_fractions'] is None
    with pytest.raises(ValueError):a.localization(np.zeros(511),np.ones(128))
    with pytest.raises(ValueError):a.localization(np.full(512,np.nan),np.ones(128))


def test_python_exit_does_not_invent_slurm_success():
    job=99999;summary={'status':'paired_seed_windows_complete_requires_review'}
    batch=dict(job_id=str(job),child_exit_status=0,scheduler_terminal_verified=False)
    term=dict(job_id=job,summary=summary,batch_exit=batch,state='UNKNOWN',scontrol='')
    assert not a.execution_evidence(term,batch,summary,job)['scheduler_terminal_verified']
    term.update(state='COMPLETED',scontrol='JobId=99999 JobState=COMPLETED ExitCode=0:0 NumCPUs=32 QOS=qos_stu_cpu_long TimeLimit=06:00:00')
    assert a.execution_evidence(term,batch,summary,job)['scheduler_terminal_verified']
    for old,new in [('06:00:00','04:00:00'),('0:0','1:0'),('99999','85875')]:
        bad=deepcopy(term);bad['scontrol']=bad['scontrol'].replace(old,new)
        with pytest.raises(AssertionError):a.execution_evidence(bad,batch,summary,job)
    batch['child_exit_status']=False
    with pytest.raises(AssertionError):a.execution_evidence(term,batch,summary,job)


def test_declared_budget_seeds_and_history_flags_cannot_be_substituted():
    seeds={name:dict(path=a.run.SOURCES[name][0]+f'/{name}/endpoints-map16/mapped_final.dat',size_bytes=10099884032,sha256=a.run.SEED_SHA[name]) for name in ('accelerated','historical')}
    stats=[dict(path=q['path'],size_bytes=q['size_bytes'],inode=i+1,mtime_ns=i+1) for i,q in enumerate(seeds.values())]
    d=dict(maximum_maps=32,maximum_feedback_pairs=4,cadence=[8,16],child_limits=dict(accelerated=16,historical=16),case_order=['accelerated','historical'],seeds=seeds,
        accepted_outer_steps=20,new_material_steps=0,source_jobs=a.run.SOURCE_JOBS,
        source_85821_scheduler_terminal_verified=True,source_85875_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,
        git_commit='test-commit',git_clean=True,matched_new_two_branch_experiment=True,reference_recomputed=True,reference_calibration_eligible=False,
        wall_limit_s=21600,minimum_free_fields=24,parent_worker_rss_limit_bytes=6*1024**3,seed_stats_before=stats,source_field_stats_before=stats,claims=list(seeds.values()),
        prior_feedback_origins=dict(accelerated='82518 accelerated pair16',historical='85875 historical pair16'),
        window_r20_tolerance=.001,window_signal_tolerance=.1,first_window_cross_history_is_measurement_only=True,drift_failure_does_not_skip_other_matched_case=True,
        both_branches_identical_x20=True,historical_failures_retained=True,automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,
        environment=dict(git_commit='test-commit',tracked_worktree_dirty=False,scheduler=dict(SLURM_JOB_ID='99999',SLURM_CPUS_PER_TASK='32',SLURM_MEM_PER_NODE='131072')))
    a.verify_plan(d,seeds,99999)
    for key,value in [('maximum_maps',64),('reference_recomputed',False),('minimum_free_fields',14),('source_84026_scheduler_terminal_verified',True),('source_jobs',[82518,85821]),('window_signal_tolerance',.2),('prior_feedback_origins',{'historical':'84026 historical pair16'}),('source_field_stats_before',[]),('baseline_replacement_authorized',True)]:
        bad=deepcopy(d);bad[key]=value
        with pytest.raises(AssertionError):a.verify_plan(bad,seeds,99999)
    with pytest.raises(AssertionError):a.verify_plan(d,seeds,85875)


def test_saved_a_source_paths_are_not_resolved_as_current_h():
    from pathlib import Path
    expected={'x20-global-boundary-validation-20261001':'x20-global-boundary-validation-82515-received',
        'x20-global-boundary-prediction-20261001':'x20-global-prediction-82512-received',
        'x20-window-difference-20260930':'x20-window-difference-82396-received',
        'x20-latest-window-basis-20261001':'x20-latest-basis-82441-received'}
    for src,folder in expected.items():
        assert a.claim_path('outputs/hpc/'+src+'/declaration.json',Path('new'))==a.ROOT/folder/'declaration.json'
        assert a.claim_path('outputs/hpc/'+src+'/archives/snapshot.tar.gz',Path('new'))==a.ROOT/'snapshot.tar.gz'
