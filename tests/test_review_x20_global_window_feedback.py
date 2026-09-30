import json
from copy import deepcopy
import numpy as np
import pytest
from handoff.audit_tools import review_x20_global_window_feedback as a


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


def test_real_frozen_source_trial_and_r20_on_mac():
    root=a.ROOT/'x20-global-boundary-validation-82515-received'
    base_path=a.ROOT/'common-step21-76808-received/inputs/outer_base_material.npz'
    if not root.exists():
        root=a.Path('outputs/hpc/x20-global-boundary-validation-20261001')
        base_path=a.Path('outputs/hpc/common-step21-20260924/inputs/outer_base_material.npz')
    assert root.exists() and base_path.exists(), 'real frozen source required'
    trial=a.arrays(root/'full/trial_material.npz');base=a.arrays(base_path)
    assert set(trial)==set(base) and all(np.array_equal(trial[k],base[k]) for k in trial)
    assert int(trial['phase_index'])==1367 and float(trial['step_duration_s'])==889.419892762322


def test_old_job_anchor_or_changed_gate_is_rejected():
    d=dict(maximum_maps=32,maximum_feedback_pairs=4,cadence=[8,16],child_limits=dict(accelerated=16,historical=16),case_order=['accelerated','historical'],seeds={},accepted_outer_steps=20,new_material_steps=0,source_jobs=[76727,80195,82273,82515],window_r20_tolerance=.001,window_signal_tolerance=.1,first_window_cross_history_is_measurement_only=True,drift_failure_does_not_skip_other_matched_case=True,both_branches_identical_x20=True,historical_failures_retained=True,automatic_promotion=False,baseline_replacement_authorized=False,physical_dt_changed=False,environment=dict(scheduler=dict(SLURM_JOB_ID='99999',SLURM_CPUS_PER_TASK='32',SLURM_MEM_PER_NODE='131072')))
    a.verify_plan(d,{},99999)
    for k,v in [('source_jobs',[76727,80195,80554,81679]),('maximum_maps',64),('window_r20_tolerance',.01),('baseline_replacement_authorized',True)]:
        bad=deepcopy(d);bad[k]=v
        with pytest.raises(AssertionError):a.verify_plan(bad,{},99999)
