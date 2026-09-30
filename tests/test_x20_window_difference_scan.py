from copy import deepcopy
import pytest
from operations.x20_window_difference_scan import require_review


def records():
    return dict(job_id=82273,completed_experiment=True,all_original_zero_gates_passed=True,
                map_counts=dict(accelerated=16,historical=16),reference_calibration_eligible=False,
                accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False), \
           dict(job_id=82273,state='COMPLETED',scontrol='JobState=COMPLETED ExitCode=0:0')


def test_complete_failed_calibration_is_a_diagnostic_source():
    require_review(*records())


@pytest.mark.parametrize('key,value', [
    ('job_id',81769),('completed_experiment',False),('reference_calibration_eligible',None),
    ('reference_calibration_eligible',True),('all_original_zero_gates_passed',False),
    ('map_counts',dict(accelerated=16,historical=8)),('new_material_steps',1),
    ('baseline_replaced',True),('accepted_outer_steps',21),
])
def test_partial_different_or_promoted_source_is_rejected(key,value):
    a,t=records();a[key]=deepcopy(value)
    with pytest.raises(ValueError):require_review(a,t)


@pytest.mark.parametrize('key,value', [('job_id',81769),('state','RUNNING'),('scontrol','ExitCode=1:0')])
def test_incomplete_or_failed_scheduler_source_is_rejected(key,value):
    a,t=records();t[key]=value
    with pytest.raises(ValueError):require_review(a,t)
