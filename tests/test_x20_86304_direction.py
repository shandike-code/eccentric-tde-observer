import copy
import hashlib
import io
import json
import numpy as np
import pytest
from handoff.audit_tools import diagnose_x20_86304_direction as d
from handoff.audit_tools import review_x20_86304_direction as oracle


def fixture(h0=4.,a0=0.,h1=3.,a1=0.):
    v=lambda value:np.tile([value,0.,0.,0.],128).astype('float64')
    return {k:v({('old','historical'):h0,('old','accelerated'):a0,('new','historical'):h1,('new','accelerated'):a1}[k[:2]]) for k in d.KEYS}


def run(states,mass=None):
    if mass is None:mass=np.arange(1.,129.)
    return dict(input_vectors={'__'.join(k):v.tolist() for k,v in states.items()},mass=mass.tolist(),quadruples=d.calculate(states,mass))


@pytest.mark.parametrize('values,ratio,projection,cosine',[
    ((4,0,3,0),.75,-.25,1.),((4,0,-2,0),.5,-1.5,-1.),
    ((4,0,9,5),1.,0.,1.),((4,0,0,0),0.,-1.,None),
    ((0,0,1,0),None,None,None),((0,0,0,0),None,None,None)])
def test_analytic(values,ratio,projection,cosine):
    result=run(fixture(*values));assert oracle.review(result)['passed']
    assert len(result['quadruples'])==16
    for row in result['quadruples'].values():
        assert row['mass_norm_ratio']==ratio
        assert row['projections']['D']==projection
        assert row['mass_cosine']==cosine


def test_nonuniform_and_input_immutable():
    states=fixture();states[('new','historical','final')][::4]=np.linspace(-3,5,128)
    before={k:v.tobytes() for k,v in states.items()}
    result=run(states);assert oracle.review(result)['passed']
    assert before=={k:v.tobytes() for k,v in states.items()}
    expected=np.sqrt(np.sum(np.arange(1.,129.)*np.linspace(-3,5,128)**2)/np.arange(1.,129.).sum())
    row=result['quadruples']['previous__previous__final__previous']
    assert row['norms']['C_new'][1]==pytest.approx(expected,rel=1e-15)


def test_near_cancellation():
    states=fixture(1e10,1e10-1,1e10+1e-5,1e10-1+2e-5)
    assert oracle.review(run(states))['passed']


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.,0.])
def test_bad_mass(value):
    mass=np.ones(128);mass[8]=value
    with pytest.raises(ValueError):run(fixture(),mass)


@pytest.mark.parametrize('kind',['nan','inf','shape','dtype','missing','wrong_branch','wrong_epoch'])
def test_bad_source(kind):
    s=fixture();key=d.KEYS[0]
    if kind in ('nan','inf'):s[key][0]=float(kind)
    elif kind=='shape':s[key]=s[key][:-1]
    elif kind=='dtype':s[key]=s[key].astype('float32')
    elif kind=='missing':s.pop(key)
    else:s[('wrong',*key[1:]) if kind=='wrong_epoch' else (key[0],'wrong',key[2])]=s.pop(key)
    with pytest.raises(ValueError):run(s)


@pytest.mark.parametrize('corrupt',['vector','norm','inner','projection','cosine','missing_quad','wrong_endpoint'])
def test_oracle_rejects(corrupt):
    r=run(fixture());row=next(iter(r['quadruples'].values()))
    if corrupt=='vector':row['vectors']['D'][3]+=1e-3
    elif corrupt=='norm':row['norms']['D'][1]*=2
    elif corrupt=='inner':row['mass_inner_with_C_old']['D']+=1
    elif corrupt=='projection':row['projections']['D']+=.01
    elif corrupt=='cosine':row['mass_cosine']=.5
    elif corrupt=='missing_quad':r['quadruples'].pop(next(iter(r['quadruples'])))
    else:r['input_vectors']['old__historical__previous'][0]+=1
    with pytest.raises(ValueError):oracle.review(r)


def test_identity_wrong_expression():
    s=[np.ones(512)]*4
    with pytest.raises(ValueError):d.identity(np.ones(512),np.zeros(512),s)


def test_underflow_rejected():
    with pytest.raises(ValueError,match='underflow'):d.norms(np.full(512,d.ETA),np.ones(128))


def test_overflow_rejected():
    with pytest.raises((ValueError,FloatingPointError)):d.calculate(fixture(1e308,0,1e308,0),np.ones(128))


def test_bound_file(tmp_path):
    p=tmp_path/'a.npz';p.write_bytes(b'good');sha=hashlib.sha256(b'good').hexdigest()
    assert d.read_bound(p,4,sha)==b'good'
    with pytest.raises(ValueError):d.read_bound(p,4,'0'*64)
    with pytest.raises(ValueError):d.read_bound(p,5,sha)
    with pytest.raises(ValueError):d.read_bound(p,4,sha,3)
    link=tmp_path/'link.npz';link.symlink_to(p)
    with pytest.raises(ValueError):d.read_bound(link,4,sha)
    dat=tmp_path/'a.dat';dat.write_bytes(b'good')
    with pytest.raises(ValueError):d.read_bound(dat,4,sha)


def test_duplicate_manifest():
    with pytest.raises(ValueError):d.claim_map({'files':[dict(path='x'),dict(path='x')]})
    with pytest.raises(ValueError):d.parse(b'{"x":1,"x":2}')
    with pytest.raises(ValueError):d.parse(b'{"x":NaN}')


@pytest.mark.parametrize('array',[np.array([float('nan')]),np.array([object()])])
def test_invalid_npz(array):
    f=io.BytesIO();np.savez(f,array=array)
    with pytest.raises(ValueError):d.unpack(f.getvalue())


@pytest.mark.parametrize('job,pair',[(86304,16),(85889,8),(84026,16)])
def test_wrong_job_map(job,pair):
    with pytest.raises(ValueError):d.source_identity('old',job,pair,d.PINS[0][4])
