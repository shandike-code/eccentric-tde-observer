import copy
import json
import os
import signal
from types import SimpleNamespace
import numpy as np
import pytest
from tests.test_x20_85889_chord_resource import fixture
from operations import x20_85889_chord_resource_v2 as r
from operations.x20_85889_chord_live import check_native_arrays
from handoff.audit_tools.review_x20_85889_chord_resource_v2 import review


def test_complete(tmp_path):
    c=fixture(tmp_path);stages=[]
    out=r.authenticated_probe(c,[33,2,3],r.core.Guard(),lambda k,v:stages.append(k))
    assert stages==['field-hash-before','probe','field-hash-after']
    assert out['field_bytes_read']==37440
    assert review(json.loads(json.dumps(out)))['full_field_sha_refreshed'] is True
    assert out['probe']['full_field_sha_refreshed'] is False


def test_unseen_tail_corruption_rejected_before_probe(tmp_path):
    c=fixture(tmp_path);stages=[]
    with open(c[0]['path'],'r+b') as f:f.seek(32*2*3*8);f.write(np.array([123.]).tobytes())
    with pytest.raises(ValueError,match='SHA'):
        r.authenticated_probe(c,[33,2,3],r.core.Guard(),lambda k,v:stages.append(k))
    assert stages==[]


@pytest.mark.parametrize('stage',['field-hash-before','probe'])
def test_between_phase_change(tmp_path,stage):
    c=fixture(tmp_path)
    def progress(k,v):
        if k==stage:
            with open(c[0]['path'],'r+b') as f:f.seek(32*2*3*8);f.write(np.array([123.]).tobytes())
    with pytest.raises(ValueError):r.authenticated_probe(c,[33,2,3],r.core.Guard(),progress)


@pytest.mark.parametrize('change',['hash','bytes','nested_claim','timing','scope','maps','post_stat'])
def test_corrupt_proof(tmp_path,change):
    out=r.authenticated_probe(fixture(tmp_path),[33,2,3],r.core.Guard());out=json.loads(json.dumps(out))
    if change=='hash':out['full_sha256_after'][0]='0'*64
    elif change=='bytes':out['field_bytes_read']-=1
    elif change=='nested_claim':out['probe']['source_claims'][0]['sha256']='0'*64
    elif change=='timing':out['full_hash_seconds_before']=float('nan')
    elif change=='scope':out['full_scan_authorized']=True
    elif change=='maps':out['new_maps']=1
    else:out['source_stats_after'][0][1]+=1
    with pytest.raises(ValueError):review(out)


@pytest.mark.parametrize('change',['duplicate','shape','sha'])
def test_input_rejection(tmp_path,change):
    c=fixture(tmp_path);shape=[33,2,3]
    if change=='duplicate':c[-1]=c[0]
    elif change=='shape':shape=[33,2]
    else:c[0]['sha256']='broken'
    with pytest.raises(ValueError):r.authenticated_probe(c,shape,r.core.Guard())


@pytest.mark.parametrize('kind',['signal','time','rss'])
def test_lifecycle_stop(tmp_path,kind):
    def work(guard,out):
        if kind=='signal':os.kill(os.getpid(),signal.SIGUSR1)
        elif kind=='time':guard.seconds=0
        else:guard.rss_bytes=1
        guard.check()
    run=tmp_path/'run';assert r.execute(run,work)==1
    assert (run/'failure.json').exists() and not (run/'finished.json').exists()
    assert not (run/'result.json').exists()


def test_scheduler_v2():
    text='JobId=12 JobState=RUNNING NumCPUs=4 NumTasks=1 NumNodes=1 Partition=Students QOS=qos_stu_default TimeLimit=00:30:00 MinMemoryNode=16G'
    assert r.scheduler_allocation('12',text)['job_id']=='12'
    with pytest.raises(ValueError):r.scheduler_allocation('12',text.replace('00:30:00','00:15:00'))


def native_fixture():
    trial={k:np.arange(6,dtype=float).reshape(3,2) for k in ('density_g_cm3','temperature_k','hydrogen_fraction','helium_fraction')}
    mat={k.replace('_g_cm3','').replace('_k','').replace('_fraction','')+'_parent':np.concatenate((v,v[::-1])) for k,v in trial.items()}
    blocks=[SimpleNamespace(core_group_start=i,core_group_stop=min(i+128,9632)) for i in range(0,9632,128)]
    return trial,mat,dict(phase=1367,duration_s=889.419892762322,mu=np.zeros(32),beta=np.zeros(4096),blocks=blocks)


def test_native_identity():check_native_arrays(*native_fixture())


@pytest.mark.parametrize('change',['dtype','shape','signed_zero','phase','dt','group','missing_group'])
def test_native_failure(change):
    trial,mat,ctx=native_fixture()
    if change=='dtype':mat['density_parent']=mat['density_parent'].astype('f4')
    elif change=='shape':mat['density_parent']=mat['density_parent'].ravel()
    elif change=='signed_zero':mat['density_parent'][0,0]=-0.0
    elif change=='phase':ctx['phase']=1368
    elif change=='dt':ctx['duration_s']+=1
    elif change=='group':ctx['blocks'][1].core_group_start+=1
    else:ctx['blocks'].pop()
    with pytest.raises(ValueError):check_native_arrays(trial,mat,ctx)


def test_conflicting_dependency_claims():
    from operations.x20_85889_chord_live import merge_claims
    c=dict(path='template.json',size_bytes=1,sha256='a'*64)
    assert len(merge_claims([c,c]))==1
    with pytest.raises(ValueError):merge_claims([c,dict(c,sha256='b'*64)])


def test_v2_archive_has_hash_stages(tmp_path):
    from operations import x20_85889_chord_receipt_v2 as receipt
    import tarfile
    run=tmp_path/'run';run.mkdir()
    for name in ('field-hash-before','field-hash-after','probe','live-before','live-after'):
        (run/(name+'.json')).write_text('{}')
    out=receipt.archive(run,tmp_path/'proof.tar.gz',[])
    assert len(out['files'])==5 and not out['scheduler_terminal_verified']
    with tarfile.open(tmp_path/'proof.tar.gz') as tar:assert len(tar.getnames())==5


def test_v2_watch_bounded_and_terminal(tmp_path,monkeypatch):
    from operations import x20_85889_chord_receipt_v2 as receipt
    with pytest.raises(ValueError):receipt.observe('12',tmp_path/'invalid',seconds=2401)
    class P:returncode=0;stdout='JobId=12 JobState=COMPLETED ExitCode=0:0';stderr=''
    monkeypatch.setattr(receipt.subprocess,'run',lambda *a,**kw:P())
    assert receipt.observe('12',tmp_path/'watch',seconds=2400)['successful']


@pytest.mark.parametrize('kind',['partial','failure'])
def test_production_reviewer_never_accepts_partial(tmp_path,kind):
    from handoff.audit_tools.review_x20_85889_chord_resource_v2 import review_run
    (tmp_path/'result.json').write_text('{}')
    if kind=='failure':
        (tmp_path/'finished.json').write_text('{}');(tmp_path/'failure.json').write_text('{}')
    with pytest.raises(ValueError,match='failed or incomplete'):review_run(tmp_path,'x',{}, {})
