import pytest
from handoff.audit_tools.review_x20_85744_basis import terminal_check

def receipt():
    b=dict(job_id='85744',child_exit_status=0,scheduler_terminal_verified=False)
    s=dict(status='basis_complete_requires_review')
    t=dict(job_id=85744,state='COMPLETED',summary=s,batch_exit=b.copy(),scontrol='ExitCode=0:0 NumCPUs=4 QOS=qos_stu_default TimeLimit=01:00:00')
    return t,b,s

def test_child_receipt_alone_cannot_prove_scheduler_completion():
    t,b,s=receipt();t['state']='UNKNOWN'
    with pytest.raises(AssertionError):terminal_check(t,b,s)

def test_mismatched_child_receipt_rejected():
    t,b,s=receipt();b['job_id']='84026'
    with pytest.raises(AssertionError):terminal_check(t,b,s)

def test_failed_child_cannot_pass_completed_audit():
    t,b,s=receipt();b['child_exit_status']=1
    with pytest.raises(AssertionError):terminal_check(t,b,s)

def test_real_scheduler_and_child_receipt_are_distinct():
    terminal_check(*receipt())
