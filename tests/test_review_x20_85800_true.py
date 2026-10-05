import copy
import pytest
from handoff.audit_tools import review_x20_85800_true as review


def evidence(state='COMPLETED'):
    b=dict(job_id='85800',child_exit_status=0,scheduler_terminal_verified=False)
    s=dict(status='true_maps_validated_requires_review')
    t=dict(job_id=85800,state=state,summary=s,batch_exit=b,scontrol='JobState='+state+' ExitCode=0:0')
    return t,b,s


def test_child_exit_does_not_become_scheduler_success():
    t,b,s=evidence('UNKNOWN')
    result=review.execution_evidence(t,b,s)
    assert result['numerical_artifacts_complete']
    assert result['scheduler_terminal_verified'] is False and result['scheduler_terminal_state'] is None


def test_real_scheduler_terminal_keeps_separate_child_evidence():
    t,b,s=evidence()
    result=review.execution_evidence(t,b,s)
    assert result['scheduler_terminal_verified'] and result['scheduler_terminal_state']=='COMPLETED'


@pytest.mark.parametrize('damage',['job','child_failure','boolean_child','forged_terminal','summary','batch'])
def test_rejects_broken_execution_evidence(damage):
    t,b,s=evidence()
    if damage=='job':t['job_id']=83514
    elif damage=='child_failure':b['child_exit_status']=1
    elif damage=='boolean_child':b['child_exit_status']=False
    elif damage=='forged_terminal':t['scontrol']='JobState=RUNNING ExitCode=0:0'
    elif damage=='summary':t['summary']={}
    else:t['batch_exit']={}
    with pytest.raises(AssertionError):review.execution_evidence(t,b,s)


@pytest.mark.parametrize('damage',['source_job','coefficient','basis','source_scheduler'])
def test_rejects_source_identity_changes(monkeypatch,damage):
    fields=[dict(path=str(i),sha256=str(i)) for i in range(8)]
    monkeypatch.setattr(review,'source_fields',lambda:fields)
    c=review.COEFFICIENTS
    d=dict(basis=copy.deepcopy(fields),global_coefficients=c.copy(),selected_coefficients=[c.copy() for _ in range(76)],source_84026_scheduler_terminal_verified=False)
    pred=dict(fields=fields,global_coefficients=c)
    prev=dict(job_id=85778,independent_slab_reduction=True,source_and_code_verified=True,scheduler_terminal_verified=True,small_qp_certificate_verified=True,result=dict(passed=True,checks={k:True for k in review.EXPECTED_PREDICTION_GATES}),fields=fields,coefficients=c)
    origin=dict(job_id=84026,numerical_artifacts_complete=True,scheduler_terminal_verified=False,scheduler_terminal_state=None)
    review.source_binding(d,pred,prev,origin)
    if damage=='source_job':prev['job_id']=83131
    elif damage=='coefficient':d['selected_coefficients'][2][1]+=1
    elif damage=='basis':d['basis'][0],d['basis'][1]=d['basis'][1],d['basis'][0]
    else:origin['scheduler_terminal_verified']=True
    with pytest.raises(AssertionError):review.source_binding(d,pred,prev,origin)
