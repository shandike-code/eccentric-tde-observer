import numpy as np
import pytest
from operations import scan_step21_block_short_step as scan


def test_positive_and_negative_active_constraints():
    raw=np.array([.9,-.4]);delta=np.array([2.,-3.])
    upper,index=scan.constrained_bound(raw,delta,1.)
    assert upper==pytest.approx(.05) and index==(0,)
    assert np.all(abs(raw+upper*delta)<=1.+1e-15)
    upper,index=scan.constrained_bound(-raw,-delta,1.)
    assert upper==pytest.approx(.05) and index==(0,)


def test_active_maximum_with_outward_direction_forbids_every_positive_step():
    upper,index=scan.constrained_bound(np.array([1.,-.1]),np.array([.01,-2.]),1.)
    assert upper==0 and index==(0,)
    result=scan.choose(1.,2.,-.5,upper)
    assert result['fraction']==0 and not result['l2_cost_pass']


def test_safety_fraction_and_exact_quadratic():
    r=scan.choose(1.,1.,-.5,.1)
    assert r['fraction']==pytest.approx(.09)
    assert r['predicted_l2_ratio']==pytest.approx(np.sqrt(1-.09+.09**2)) and r['l2_cost_pass']


@pytest.mark.parametrize('dd,rd',[(0.,0.),(1.,0.),(1.,.1)])
def test_no_descent_is_not_positive_result(dd,rd):
    assert scan.choose(1.,dd,rd,1.)['fraction']==0


@pytest.mark.parametrize('raw,delta,maximum',[(np.array([1.1]),np.array([0.]),1.),(np.array([1.]),np.array([np.nan]),1.),(np.array([0.]),np.array([0.]),0.)])
def test_bad_constraints_rejected(raw,delta,maximum):
    with pytest.raises(ValueError):scan.constrained_bound(raw,delta,maximum)


def test_stream_scan_matches_known_affine_direction(tmp_path,monkeypatch):
    monkeypatch.setattr(scan,'BLOCKS',(0,1));monkeypatch.setattr(scan.reused,'checkpoint',lambda:None)
    shape=(384,1,1);x=np.ones(shape)*2;y=x+.1;q=x.copy();q[:256]+=.5;tq=q+.08
    paths=[]
    for i,a in enumerate((x,y,q,tq)):
        p=tmp_path/f'{i}.dat';a.tofile(p);paths.append(p)
    # 正边界单频通量是线性泛函；本合成例只验证控制与流式代数，不代表真实输运。
    result=scan.scan(paths,shape,lambda a,start:a[:,0,0],dict(boundary_l1=.1,boundary_bolometric=.1))
    assert result['passes']==3 and result['choice']['fraction']>0
    assert result['choice']['streamed_linf_ratio']<1
    assert result['choice']['streamed_l2_ratio']==pytest.approx(result['choice']['predicted_l2_ratio'])
    assert not result['actual_map_performed'] and not result['candidate_written']
    assert sum(s['stop']-s['start'] for s in result['slabs'])==384


def test_unselected_change_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(scan.reused,'checkpoint',lambda:None)
    paths=[]
    for i,val in enumerate((1.,2.,3.,4.)):
        p=tmp_path/f'{i}.dat';np.full((32,1,1),val).tofile(p);paths.append(p)
    with pytest.raises(RuntimeError,match='undeclared'):scan.scan(paths,(32,1,1),lambda a,s:a[:,0,0],{})
