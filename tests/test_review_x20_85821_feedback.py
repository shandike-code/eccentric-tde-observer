from copy import deepcopy
from pathlib import Path
import json
import pytest
from handoff.audit_tools import review_x20_85821_feedback as r


def live_plan():
    # This is a copied, unreviewed declaration, used only for component checks.
    root=Path('outputs/review-20260925/x20-85821-review-preflight')
    if not root.exists():root=Path('outputs/hpc/x20-85800-seed-feedback-20261006')
    return r.read(root/'declaration.json'),r.read(root/'seed-claims.json')


def test_frozen_current_plan_and_wrong_scope():
    d,seeds=live_plan();r.verify_plan(d,seeds,85821)
    for field,value in [('maximum_maps',32),('reference_calibration_eligible',True),('matched_new_two_branch_experiment',True),
                        ('source_jobs',[76727,80195,82518,82989,83514]),('source_84026_scheduler_terminal_verified',True)]:
        b=deepcopy(d);b[field]=value
        with pytest.raises(AssertionError):r.verify_plan(b,seeds,85821)
    with pytest.raises(AssertionError):r.verify_plan(d,seeds,84026)


def source():
    a=r.read('handoff/evidence/20261006-x20-85778-true-85800-review.json')
    origin=r.read('handoff/evidence/20261005-x20-84026-final-review.json')
    full=deepcopy(a['actual_maps']['full'])
    seeds=dict(historical=dict(path=full['output_path'],sha256=full['output_sha256'],size_bytes=10099884032))
    return a,origin,seeds,full


@pytest.mark.parametrize('damage',['none','old_true_job','source_gate','source_numerical_commit','candidate_as_seed',
                                   'wrong_origin','invented_origin_terminal','new_material_step'])
def test_real_source_and_origin_are_distinct(damage):
    a,o,seeds,full=source()
    if damage=='old_true_job':a['job_id']=83514
    elif damage=='source_gate':a['actual']['checks']['full_l2_benefit']=False
    elif damage=='source_numerical_commit':a['numerical_commit']='0'*40
    elif damage=='candidate_as_seed':seeds['historical']['sha256']=full['input_sha256']
    elif damage=='wrong_origin':o['job_id']=82989
    elif damage=='invented_origin_terminal':o['scheduler_terminal_verified']=True
    elif damage=='new_material_step':a['new_material_steps']=1
    if damage=='none':r.source_binding(a,o,seeds,full)
    else:
        with pytest.raises(AssertionError):r.source_binding(a,o,seeds,full)


def evidence(state='COMPLETED'):
    b=dict(job_id='85821',child_exit_status=0,scheduler_terminal_verified=False)
    s=dict(status='historical_seed_windows_complete_requires_review')
    raw=('JobId=85821 JobState='+state+' ExitCode=0:0 NumCPUs=32 QOS=qos_stu_cpu_long TimeLimit=04:00:00') if state!='UNKNOWN' else ''
    t=dict(job_id=85821,state=state,summary=s,batch_exit=b,scontrol=raw)
    return t,b,s


@pytest.mark.parametrize('state',['COMPLETED','UNKNOWN','RUNNING','COMPLETING'])
def test_child_success_and_scheduler_evidence_are_separate(state):
    t,b,s=evidence(state);x=r.execution_evidence(t,b,s,85821)
    assert x['numerical_artifacts_complete'] and x['child_exit_status']==0
    assert x['scheduler_terminal_verified']==(state=='COMPLETED')
    assert x['scheduler_terminal_state']==('COMPLETED' if state=='COMPLETED' else None)


@pytest.mark.parametrize('damage',['job','raw_job','child_failure','boolean_child','state','exit_code','resources','summary','fake_batch_terminal'])
def test_execution_evidence_rejects_false_success(damage):
    t,b,s=evidence()
    if damage=='job':t['job_id']=85800
    elif damage=='raw_job':t['scontrol']=t['scontrol'].replace('85821','858210')
    elif damage=='child_failure':b['child_exit_status']=1
    elif damage=='boolean_child':b['child_exit_status']=False
    elif damage=='state':t['scontrol']=t['scontrol'].replace('JobState=COMPLETED','JobState=RUNNING')
    elif damage=='exit_code':t['scontrol']=t['scontrol'].replace('ExitCode=0:0','ExitCode=1:0')
    elif damage=='resources':t['scontrol']=t['scontrol'].replace('NumCPUs=32','NumCPUs=4')
    elif damage=='summary':t['summary']={}
    else:b['scheduler_terminal_verified']=True
    with pytest.raises(AssertionError):r.execution_evidence(t,b,s,85821)


def test_prior_origin_saved_reference_and_current_files_do_not_alias(tmp_path):
    assert callable(r.review)
    current=r.claim_path('outputs/hpc/x20-85800-seed-feedback-20261006/declaration.json',tmp_path)
    origin=r.claim_path('outputs/hpc/x20-83514-seed-feedback-20261002/declaration.json',tmp_path)
    seed=r.claim_path('outputs/hpc/x20-85778-true-validation-20261006/declaration.json',tmp_path)
    reference=r.claim_path('outputs/hpc/x20-global-window-feedback-20261001/declaration.json',tmp_path)
    assert current==tmp_path/'declaration.json' and len({current,origin,seed,reference})==4
    assert origin.parent.name=='x20-83514-feedback-84026-received'
    assert seed.parent.name=='x20-85778-true-85800-received'
    assert reference.parent.name=='x20-global-feedback-82518-complete-received'


@pytest.mark.parametrize('n',[8,16])
def test_saved_cross_failure_is_not_original_pair_failure(n):
    d=r.read(r.ROOT/f'x20-83514-feedback-84026-received/historical/pair{n:02d}/decision.json')
    assert not d['vs_saved_reference']['cross_rate_pass'];r.verify_pair(d,'historical',n)
    d['original_zero_gates']['physical_response_pass']=False
    with pytest.raises(AssertionError):r.verify_pair(d,'historical',n)


def test_hard_failed_pair_never_enters_success_audit(tmp_path):
    p=tmp_path/'historical/pair08';p.mkdir(parents=True)
    (p/'decision.json').write_text(json.dumps(dict(physical_response_failures={'bad_cell':1},zero_pair_stable=False,continuation_pass=False)))
    with pytest.raises(ValueError,match='dedicated failure audit'):r.settled_entries(tmp_path)
