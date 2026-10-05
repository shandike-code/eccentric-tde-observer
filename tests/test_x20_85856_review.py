import pytest
from handoff.audit_tools.review_x20_85856_basis import terminal_check

def receipt():
    b=dict(job_id='85856',child_exit_status=0,scheduler_terminal_verified=False)
    s=dict(status='basis_complete_requires_review')
    t=dict(job_id=85856,state='COMPLETED',summary=s,batch_exit=b.copy(),scontrol='JobId=85856 JobState=COMPLETED MinMemoryNode=16G ExitCode=0:0 NumCPUs=4 QOS=qos_stu_default TimeLimit=01:00:00')
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

from copy import deepcopy
from handoff.audit_tools.review_x20_85856_basis import field_stats_check,audit_identity

def field_receipt():
    rows=[dict(path=f'source/{i}.dat',inode=i+1,size_bytes=10099884032,mtime_ns=123) for i in range(8)]
    d=dict(git_clean=True,field_stats_before=rows,fields=[dict(path=v['path'],size_bytes=v['size_bytes']) for v in rows])
    return d,dict(all_hashes_verified_before_after=True,field_stats_after=deepcopy(rows))

@pytest.mark.parametrize('key,value',[('inode',999),('mtime_ns',124),('size_bytes',1),('path','wrong.dat')])
def test_changed_file_identity_fails(key,value):
    d,s=field_receipt();s['field_stats_after'][0][key]=value
    with pytest.raises(AssertionError):field_stats_check(d,s)

def test_unchanged_file_identity_passes():field_stats_check(*field_receipt())

def test_scheduler_job_substring_rejected():
    t,b,s=receipt();t['scontrol']=t['scontrol'].replace('JobId=85856','JobId=858560')
    with pytest.raises(AssertionError):terminal_check(t,b,s)

@pytest.mark.parametrize('job,path',[(85821,'20261006-x20-85821-final-review.json'),(84026,'20261005-x20-84026-final-review.json'),(82989,'20261001-x20-82989-final-review.json')])
def test_source_audit_identity(job,path):
    from pathlib import Path
    import json
    a=json.loads((Path('handoff/evidence')/path).read_text());audit_identity(a,job)
    if job==84026:a['scheduler_terminal_verified']=True
    else:a['map_process_receipts']=1215
    with pytest.raises(AssertionError):audit_identity(a,job)
