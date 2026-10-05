from copy import deepcopy
import pytest
from handoff.audit_tools.review_x20_85859_prediction import measured_scope,identity_scope,JOB,COMMIT

def negative_prediction():
    row=dict(group_count=32,squared_l2=[1.,1.,1.],linf=[1.,1.,1.],scales=[1.,1.,1.],
        minima=[0.,0.,0.,0.],boundary_flux=[1.]*6,boundary_l1_numerator=[1.]*3,boundary_signed=[1.]*3)
    rows=[dict(deepcopy(row),first_group=32*j) for j in range(301)]
    rows[296]['minima'][2]=-5e-324
    p=dict(slabs=rows,passed=False,checks=dict(full_field_nonnegative=False),status='negative_field_rejected',other_gates_evaluated=False)
    return p,dict(passed=False,checks=p['checks'].copy())

def test_smallest_subnormal_negative_is_preserved():
    z=measured_scope(*negative_prediction())
    assert z['negative_slabs']==[dict(first_group=9472,minima=[0.,0.,-5e-324,0.])]
    assert set(z['checks'])=={'full_field_nonnegative'} and not z['passed']

def test_uncomputed_gates_cannot_be_reported_evaluated():
    p,s=negative_prediction();p['other_gates_evaluated']=True
    with pytest.raises(AssertionError):measured_scope(p,s)

def test_missing_or_duplicate_slab_rejected():
    p,s=negative_prediction();p['slabs'][297]=p['slabs'][296].copy()
    with pytest.raises(AssertionError):measured_scope(p,s)


def identity_fixture():
    order=[f'{j}H{n}_{e}' for j,n in ((85821,16),(85821,8),(84026,16),(82989,16)) for e in ('previous','final')]
    fields=[dict(path=f'{i}.dat',size_bytes=10099884032,sha256='a'*64) for i in range(8)]
    stats=[dict(path=f'{i}.dat',size_bytes=10099884032,inode=i+1,mtime_ns=100+i) for i in range(8)]
    d=dict(job_id=str(JOB),git_commit=COMMIT,source_job=85856,source_feedback_jobs=[85821,84026,82989],source_scheduler_terminal_verified=True,source_85821_scheduler_terminal_verified=True,source_84026_scheduler_terminal_verified=False,git_clean=True,maximum_statistic_scans=1,field_order=order,fields=fields,field_stats_before=stats)
    s=dict(git_clean_after=True,git_commit_after=COMMIT,all_hashes_verified_before_after=True,field_stats_after=deepcopy(stats))
    return d,s,dict(field_order=order,fields=fields)


def test_new_identity_retains_unknown_source_scheduler():
    result=identity_scope(*identity_fixture())
    assert result['field_stats_verified'] and not result['source_84026_scheduler_terminal_verified']


@pytest.mark.parametrize('key,value', [('source_job',85744),('source_84026_scheduler_terminal_verified',True),('source_85821_scheduler_terminal_verified',False),('git_commit','37cdd3d'),('git_clean',False),('maximum_statistic_scans',2)])
def test_wrong_or_unverified_identity_rejected(key,value):
    d,s,source=identity_fixture();d[key]=value
    with pytest.raises(AssertionError):identity_scope(d,s,source)


@pytest.mark.parametrize('damage', ['order','inode','mtime','size','hash_post','git_post'])
def test_source_mutation_or_missing_post_verification_rejected(damage):
    d,s,source=identity_fixture()
    if damage=='order':d['field_order']=list(reversed(d['field_order']))
    elif damage in ('inode','mtime','size'):
        key={'inode':'inode','mtime':'mtime_ns','size':'size_bytes'}[damage];s['field_stats_after'][0][key]+=1
    elif damage=='hash_post':s['all_hashes_verified_before_after']=False
    else:s['git_commit_after']='ecc4fa4'
    with pytest.raises(AssertionError):identity_scope(d,s,source)
