"""Synthetic source identities; no production fields are read."""
import copy
import hashlib
import json
import pytest
from handoff.audit_tools import bind_x20_86304_radiation as b


def fixture():
    branch='accelerated';hashes=[hashlib.sha256(str(i).encode()).hexdigest() for i in range(9)]
    seed=dict(path=f'{b.OLD_RUN}/{branch}/endpoints-map16/mapped_final.dat',size_bytes=10099884032,sha256=hashes[0])
    h=[dict(iteration=i+1,input_sha256=hashes[i],output_sha256=hashes[i+1]) for i in range(8)]
    s=dict(history=h,active_map=None,trial_sha256=b.TRIAL,current_sha256=hashes[-1],config_sha256='config')
    c=dict(run=f'{b.RUN}/{branch}',maximum_maps=8,shape=[9632,32,4096],warm_seed=seed)
    e={k:dict(path=f'{b.RUN}/{branch}/endpoints-map08/{k}.dat',size_bytes=10099884032,sha256=hashes[6+i]) for i,k in enumerate(b.ENDS)}
    m=dict(new_map_count=8,history_rows=h[-2:],endpoints=e)
    p=dict(sources={k+'_radiation':e[k] for k in b.ENDS[:2]})
    rs={n:[dict(block_index=i,core_group_start=i*128,core_group_stop=min((i+1)*128,9632),input_state_sha256=hashes[n-1],protocol_sha256='config') for i in range(76)] for n in (7,8)}
    return [branch,s,c,m,p,seed,copy.deepcopy(seed),rs]


def test_valid():
    args=fixture();before=copy.deepcopy(args)
    assert b.validate_branch(*args)==args[3]['endpoints'];assert args==before


@pytest.mark.parametrize('case',list(range(17)))
def test_bad_identity(case):
    a=fixture()
    if case==0:a[0]='wrong'
    if case==1:a[2]['maximum_maps']=16
    if case==2:a[1]['history'][0]['iteration']=True
    if case==3:a[1]['history'][2]['input_sha256']='bad'
    if case==4:a[1]['trial_sha256']='bad'
    if case==5:a[1]['active_map']={}
    if case==6:a[3]['new_map_count']=16
    if case==7:a[3]['endpoints']['previous']['sha256']='bad'
    if case==8:a[3]['endpoints']['final']['path']=a[3]['endpoints']['previous']['path']
    if case==9:a[6]['sha256']='fake seed'
    if case==10:a[7][7].pop()
    if case==11:a[7][7][1]['core_group_start']=0
    if case==12:a[7][8][1]['input_state_sha256']='wrong'
    if case==13:a[7][8][2]['protocol_sha256']='wrong'
    if case==14:a[7][8][0]['block_index']=False
    if case==15:a[2]['run']=a[2]['run'].replace('accelerated','historical')
    if case==16:a[4]['sources']['final_radiation']=copy.deepcopy(a[3]['endpoints']['mapped_final'])
    with pytest.raises(ValueError):b.validate_branch(*a)


@pytest.mark.parametrize('raw',[b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}',b'{"x":1,"x":2}'])
def test_json_reject(tmp_path,raw):
    p=tmp_path/'a.json';p.write_bytes(raw)
    with pytest.raises(ValueError):b.read_json(p,len(raw),hashlib.sha256(raw).hexdigest())


def test_read_scope(tmp_path):
    raw=b'{}';p=tmp_path/'a.json';p.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
    assert b.read_json(p,2,sha)=={}
    for size,digest in [(3,sha),(2,'0'*64),(True,sha)]:
        with pytest.raises(ValueError):b.read_json(p,size,digest)
    q=tmp_path/'link.json';q.symlink_to(p)
    with pytest.raises(ValueError):b.read_json(q,2,sha)
    with pytest.raises(ValueError):b.read_json(tmp_path/'never.dat',2,sha)
