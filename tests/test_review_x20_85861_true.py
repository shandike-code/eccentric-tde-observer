import copy
import pytest
from handoff.audit_tools import review_x20_85861_true as review


def evidence(state='COMPLETED'):
    b=dict(job_id='85861',child_exit_status=0,scheduler_terminal_verified=False)
    s=dict(status='true_maps_validated_requires_review')
    t=dict(job_id=85861,state=state,summary=s,batch_exit=b,scontrol='JobState='+state+' ExitCode=0:0')
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


def source_fixture():
    prev=review.read('handoff/evidence/20261006-x20-boundary-prediction-85859-review.json')
    pred=review.read(review.ROOT/'x20-boundary-prediction-85859-received/declaration.json')
    origin=review.read('handoff/evidence/20261006-x20-85821-final-review.json')
    terminal=review.read('handoff/evidence/20261006-x20-85821-terminal.json')
    d=dict(basis=copy.deepcopy(review.source_fields()),global_coefficients=review.COEFFICIENTS.copy(),
           selected_coefficients=[review.COEFFICIENTS.copy() for _ in range(76)],
           source_85821_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False)
    return d,pred,prev,origin,terminal


def test_current_source_chain():
    review.source_binding(*source_fixture())


@pytest.mark.parametrize('damage',['source_job','coefficient','basis','source_scheduler','older_scheduler','prediction_gate','stats','commit','origin_receipts','origin_child','raw_terminal','field_order'])
def test_rejects_source_identity_changes(damage):
    d,pred,prev,origin,t=source_fixture()
    if damage=='source_job':prev['job_id']=85778
    elif damage=='coefficient':d['selected_coefficients'][2][1]+=1
    elif damage=='basis':d['basis'][0],d['basis'][1]=d['basis'][1],d['basis'][0]
    elif damage=='source_scheduler':origin['scheduler_terminal_verified']=False
    elif damage=='older_scheduler':origin['source_84026_scheduler_terminal_verified']=True
    elif damage=='prediction_gate':prev['result']['checks']['full_l2_benefit']=False
    elif damage=='stats':prev['field_stats_verified']=False
    elif damage=='commit':prev['commit']='different'
    elif damage=='origin_receipts':origin['map_process_receipts']=608
    elif damage=='origin_child':origin['child_exit_status']=False
    elif damage=='raw_terminal':t['scontrol']='JobState=RUNNING ExitCode=0:0'
    else:pred['field_order'].reverse()
    with pytest.raises(AssertionError):review.source_binding(d,pred,prev,origin,t)


def field_fixture():
    d=source_fixture()[0]
    d.update(git_commit=review.COMMIT,git_clean=True,environment=dict(git_commit=review.COMMIT,tracked_worktree_dirty=False),
             field_stats_before=[dict(path=f['path'],size_bytes=f['size_bytes'],inode=i+1,mtime_ns=i+1) for i,f in enumerate(d['basis'])])
    s=dict(git_commit_after=review.COMMIT,git_clean_after=True,all_hashes_verified_before_after=True,field_stats_after=copy.deepcopy(d['field_stats_before']))
    return d,s


def test_field_identity():
    assert review.field_identity(*field_fixture())['field_stats_verified']


@pytest.mark.parametrize('damage',['inode','mtime','size','order','clean','head','hash','invalid_stat'])
def test_rejects_field_or_checkout_change(damage):
    d,s=field_fixture()
    if damage=='inode':s['field_stats_after'][0]['inode']+=1
    elif damage=='mtime':s['field_stats_after'][0]['mtime_ns']+=1
    elif damage=='size':s['field_stats_after'][0]['size_bytes']-=1
    elif damage=='order':s['field_stats_after'].reverse()
    elif damage=='clean':s['git_clean_after']=False
    elif damage=='head':s['git_commit_after']='different'
    elif damage=='hash':s['all_hashes_verified_before_after']=False
    else:
        d['field_stats_before'][0]['inode']=False
        s['field_stats_after'][0]['inode']=False
    with pytest.raises(AssertionError):review.field_identity(d,s)
