import hashlib
import json
import os
import signal
import numpy as np
import pytest
from operations import x20_85889_chord_resource as r
from handoff.audit_tools.review_x20_85889_chord_resource import review


def fixture(tmp_path):
    a=np.arange(33*2*3,dtype=float).reshape(33,2,3)/8+1
    values=[a,.5*a+4,.25*a+6,a+2,.5*(a+2)+4,.25*(a+2)+6]
    claims=[]
    for i,v in enumerate(values):
        p=tmp_path/f'{i}.bin';p.write_bytes(v.tobytes())
        claims.append(dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    return claims


def test_probe_and_no_tail_read(tmp_path):
    claims=fixture(tmp_path)
    # 首片以外修改不影响片SHA；结果必须明确没有核全场SHA。
    with open(claims[0]['path'],'r+b') as f:f.seek(32*2*3*8);f.write(np.array([123.]).tobytes())
    out=r.probe(claims,[33,2,3],r.core.Guard())
    assert out['field_bytes_read']==12*32*2*3*8
    assert out['slab']['count']==32*2*3 and not out['full_field_sha_refreshed']
    assert not out['full_scan_authorized'] and len(out['slab']['pairs'])==4
    assert review(json.loads(json.dumps(out)))['combinations']==4
    out['full_field_sha_refreshed']=True
    with pytest.raises(ValueError):review(out)


def test_duplicate(tmp_path):
    c=fixture(tmp_path);c[-1]=c[0]
    with pytest.raises(ValueError):r.probe(c,[33,2,3],r.core.Guard())


def test_mid_probe_change(tmp_path,monkeypatch):
    c=fixture(tmp_path);original=r.core.slab_statistics
    def modified(*args):
        out=original(*args)
        with open(c[0]['path'],'r+b') as f:f.write(np.array([9.]).tobytes())
        return out
    monkeypatch.setattr(r.core,'slab_statistics',modified)
    with pytest.raises(ValueError):r.probe(c,[33,2,3],r.core.Guard())


def env():
    return dict(SLURM_JOB_ID='123',SLURM_CPUS_PER_TASK='4',SLURM_NTASKS='1',SLURM_MEM_PER_NODE='16384',
                OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')


@pytest.mark.parametrize('key',list(env()))
def test_allocation_reject(key):
    e=env();e[key]='bad'
    with pytest.raises(ValueError):r.allocation(e)


def test_allocation():r.allocation(env())


def test_actual_scheduler_allocation():
    text='JobId=12 JobState=RUNNING NumCPUs=4 NumTasks=1 Partition=Students QOS=qos_stu_default TimeLimit=00:15:00 MinMemoryNode=16G'
    assert r.scheduler_allocation(12,text)['job_id']=='12'
    for old,new in [('NumCPUs=4','NumCPUs=32'),('MinMemoryNode=16G','MinMemoryNode=8G'),('TimeLimit=00:15:00','TimeLimit=01:00:00'),('JobId=12','JobId=13')]:
        with pytest.raises(ValueError):r.scheduler_allocation(12,text.replace(old,new))


@pytest.mark.parametrize('change',['matrix','missing_pair','bytes','stat','scope','nan'])
def test_review_corruption(tmp_path,change):
    out=r.probe(fixture(tmp_path),[33,2,3],r.core.Guard())
    out=json.loads(json.dumps(out))
    if change=='matrix':out['slab']['pairs'][0]['moments']['value'][0][1]='-123'
    elif change=='missing_pair':out['slab']['pairs'].pop()
    elif change=='bytes':out['field_bytes_read']+=1
    elif change=='stat':out['source_stats_after'][0][1]+=1
    elif change=='scope':out['full_scan_authorized']=True
    else:out['slab']['gram']['value'][0][0]='NaN'
    with pytest.raises(ValueError):review(out)


def test_complete_exclusive(tmp_path):
    p=tmp_path/'run';assert r.execute(p,lambda guard,out:{'ok':True})==0
    assert json.loads((p/'finished.json').read_text())['scheduler_terminal_verified'] is False
    with pytest.raises(FileExistsError):r.execute(p,lambda guard,out:{})


@pytest.mark.parametrize('kind',['exception','signal','budget'])
def test_failed_lifecycle(tmp_path,kind):
    def work(guard,out):
        if kind=='exception':raise ValueError('test')
        if kind=='signal':os.kill(os.getpid(),signal.SIGUSR1)
        if kind=='budget':guard.seconds=0
        guard.check()
    p=tmp_path/'run';assert r.execute(p,work)==1
    assert (p/'failure.json').is_file() and not (p/'finished.json').exists()
    assert not (p/'result.json').exists()


def test_probe_resource_stop(tmp_path):
    c=fixture(tmp_path)
    with pytest.raises(MemoryError):r.probe(c,[33,2,3],r.core.Guard(rss=lambda:100,rss_bytes=100))
