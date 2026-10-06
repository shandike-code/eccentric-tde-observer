import copy
import hashlib
from pathlib import Path
import numpy as np
import pytest
from operations import x20_85889_chord_binding as b


@pytest.mark.parametrize('name',['../a','/a','a/../b','a//b','','.'])
def test_path_rejected(name):
    with pytest.raises(ValueError):b.relative_path(name)


def test_bytes_and_guard(tmp_path):
    p=tmp_path/'small.json';p.write_bytes(b'{}');sha=hashlib.sha256(b'{}').hexdigest()
    assert b.small_bytes(p,sha,2)==b'{}'
    with pytest.raises(ValueError):b.small_bytes(p,sha,3)
    with pytest.raises(ValueError):b.small_bytes(p,'0'*64)
    link=tmp_path/'link';link.symlink_to(p)
    with pytest.raises(ValueError):b.small_bytes(link,sha)
    dat=tmp_path/'a.dat';dat.write_bytes(b'{}')
    with pytest.raises(ValueError):b.small_bytes(dat,sha)


def test_duplicate_claims():
    with pytest.raises(ValueError):b.unique_claims([{'path':'a'},{'path':'a'}])


@pytest.mark.parametrize('change',['dtype','shape','signzero','keys','value'])
def test_arrays_bitwise(change):
    a={'x':np.array([0.])};c=copy.deepcopy(a)
    if change=='dtype':c['x']=c['x'].astype(np.float32)
    elif change=='shape':c['x']=c['x'].reshape(1,1)
    elif change=='signzero':c['x'][0]=-0.
    elif change=='keys':c['y']=c.pop('x')
    else:c['x'][0]=1
    with pytest.raises(ValueError):b.exact_arrays(a,c)


def fixture():
    h=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,17)]
    e={n:dict(path=f'{b.RUN}/accelerated/endpoints-map16/{n}.dat',size_bytes=10099884032,sha256=str(i))
       for n,i in zip(('previous','final','mapped_final'),(14,15,16))}
    return dict(new_map_count=16,history_rows=h[-2:],endpoints=e),dict(history=h,active_map=None,current_sha256='16')


def test_chain():
    m,s=fixture();assert len(b.endpoint_chain(m,s,'accelerated'))==3


@pytest.mark.parametrize('change',['count','active','link','current','path','size','names'])
def test_bad_chain(change):
    m,s=fixture()
    if change=='count':m['new_map_count']=15
    elif change=='active':s['active_map']={}
    elif change=='link':s['history'][1]['input_sha256']='bad'
    elif change=='current':s['current_sha256']='bad'
    elif change=='path':m['endpoints']['final']['path']='somewhere.dat'
    elif change=='size':m['endpoints']['final']['size_bytes']=1
    else:m['endpoints']['extra']=m['endpoints']['final']
    with pytest.raises(ValueError):b.endpoint_chain(m,s,'accelerated')
