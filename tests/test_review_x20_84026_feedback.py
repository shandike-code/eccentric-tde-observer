from copy import deepcopy
from pathlib import Path
import json,tarfile
import pytest
from handoff.audit_tools import review_x20_84026_feedback as r
ARC=Path('outputs/review-20260925/complete-1790960272454395309.tar.gz')
if not ARC.exists():ARC=Path('outputs/hpc/x20-83514-seed-feedback-20261002/archives/complete-1790960272454395309.tar.gz')
def load(name):
    with tarfile.open(ARC) as t:return json.load(t.extractfile(name))

def test_correct_new_plan_and_reject_old_or_promoted_scope():
    d,s=load('declaration.json'),load('seed-claims.json');r.verify_plan(d,s,84026)
    for field,value in [('maximum_maps',32),('reference_calibration_eligible',True),('matched_new_two_branch_experiment',True),('source_jobs',[76727,80195,82518,82765])]:
        b=deepcopy(d);b[field]=value
        with pytest.raises(AssertionError):r.verify_plan(b,s,84026)

@pytest.mark.parametrize('n',[8,16])
def test_cross_reference_failure_is_not_a_failed_original_pair(n):
    d=load(f'historical/pair{n:02d}/decision.json');r.verify_pair(d,'historical',n)
    assert not d['vs_saved_reference']['cross_rate_pass']
    d['original_zero_gates']['physical_response_pass']=False
    with pytest.raises(AssertionError):r.verify_pair(d,'historical',n)

@pytest.mark.parametrize('damage',['none','completed','claimed_verified','accounting_has_result','preexit_not_running'])
def test_scheduler_gap_remains_explicit(damage):
    a=r.read('handoff/evidence/20261005-x20-84026-execution-observation.json')
    if damage=='none':r.verify_execution_observation(a,84026);return
    if damage=='completed':a['state']='COMPLETED'
    elif damage=='claimed_verified':a['scheduler_terminal_verified']=True
    elif damage=='accounting_has_result':a['observations'][1]['stdout']='COMPLETED'
    else:a['pre_exit_scontrol']=a['pre_exit_scontrol'].replace('JobState=RUNNING','JobState=COMPLETED')
    with pytest.raises(AssertionError):r.verify_execution_observation(a,84026)
