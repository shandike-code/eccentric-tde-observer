from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from operations import scan_step21_wide_plane as wide


def lineage():
    rows=[dict(iteration=i,input_sha256=f'h{i-1}',output_sha256=f'h{i}') for i in range(1,17)]
    retained={n:dict(history_rows=deepcopy(rows[n-2:n]),endpoints={
        k:dict(path=f'x{i}',sha256=f'h{i}') for k,i in zip(('previous','final','mapped_final'),(n-2,n-1,n))}) for n in (8,16)}
    return dict(history=rows,active_map=None),retained


def test_nonconsecutive_pairs_have_real_successors():
    state,ret=lineage();cases=wide.paired_basis(state,ret)
    assert [c['path'] for c in cases['x6-x14-x15']['basis']]==['x6','x14','x15','x7','x15','x16']
    assert [c['path'] for c in cases['x7-x14-x15']['basis']]==['x7','x14','x15','x8','x15','x16']


@pytest.mark.parametrize('fault',['endpoint','row','history','active'])
def test_wrong_lineage_rejected(fault):
    state,ret=lineage()
    if fault=='endpoint':ret[8]['endpoints']['mapped_final']['sha256']='h9'
    if fault=='row':ret[16]['history_rows'][0]['iteration']=13
    if fault=='history':state['history'][5]['output_sha256']='bad'
    if fault=='active':state['active_map']={}
    with pytest.raises(ValueError):wide.paired_basis(state,ret)


def test_nonconsecutive_two_mode_affine_map_and_normal_equations():
    operator=np.diag([.91,.98]);fixed=np.array([3.,7.]);x=fixed+np.array([1.,2.]);states=[x.copy()]
    for _ in range(16):x=fixed+operator@(x-fixed);states.append(x.copy())
    a=[states[k] for k in (6,14,15,7,15,16)]
    g,b,_=wide.gram_terms(a);solved=wide.base.solve_coefficients(g,b)
    assert solved['resolved']
    q,p=wide.affine_pair(a,solved['uv'])
    np.testing.assert_allclose(p,fixed+operator@(q-fixed),rtol=0,atol=1e-13)
    np.testing.assert_allclose(q,fixed,rtol=0,atol=2e-9)
    np.testing.assert_allclose(g@np.array(solved['uv'])+b,0,atol=1e-14)


def test_subnormal_mapped_field_witness_uses_mapped_triple():
    a=np.array([1.,2.,3.,1e-310,2e-310,4e-310]);saved=a.copy()
    cut=wide.make_cut(a,'p',(1,2,3))
    np.testing.assert_allclose(cut['row'],[-.5,-.75],atol=1e-13)
    assert cut['lower']==-1
    assert [float.fromhex(x) for x in cut['inputs_hex']]==a.tolist()
    np.testing.assert_array_equal(a,saved)
    with pytest.raises(ValueError):wide.make_cut(np.zeros(6),'q',(1,2,3))


def test_negative_prediction_is_preserved_not_clipped():
    a=[np.array([x]) for x in (1.,2.,4.,2.,3.,5.)]
    q,p=wide.affine_pair(a,(3.,0.))
    assert q[0]==-2 and p[0]==-1


def test_cost_filter_is_separate_and_strict():
    def result(r,passed=True):return dict(feasible=passed,rounds=[dict(result=dict(predicted_ratio=r))])
    assert not wide.cost_eligible(result(.98))
    assert not wide.cost_eligible(result(.8))
    assert not wide.cost_eligible(result(.5,False))
    assert wide.cost_eligible(result(.79))
    assert not wide.cost_eligible(dict(feasible=False,rounds=[]))


def test_stream_gram_matches_direct_and_wrong_anchor_rejected(tmp_path):
    rng=np.random.default_rng(17);shape=(18,2,3)
    a=[rng.uniform(1,2,shape) for _ in range(6)]
    paths=[]
    for i,x in enumerate(a):
        path=tmp_path/f'{i}.dat';x.tofile(path);paths.append(path)
    latest=float(np.max(abs(a[5]-a[2]))/max(a[5].max(),a[2].max()))
    result=wide.gram_scan(paths,shape,latest,lambda **kw:None)
    g,b,r=wide.gram_terms(a)
    np.testing.assert_allclose(result['gram'],g,rtol=1e-14)
    np.testing.assert_allclose(result['rhs'],b,rtol=1e-14)
    assert result['r2_squared']==pytest.approx(r)
    assert len(result['slabs'])==2
    with pytest.raises(RuntimeError,match='residual differs'):
        wide.gram_scan(paths,shape,latest*2,lambda **kw:None)


def test_unresolved_gram_is_diagnostic_not_candidate():
    assert not wide.base.solve_coefficients([[1.,1.],[1.,1.]],[1.,1.])['resolved']


def test_duplicate_stream_paths_are_read_once(tmp_path):
    path=tmp_path/'state.dat';np.ones((2,2,3)).tofile(path)
    streams=wide.paired_streams([path]*6,(2,2,3))
    assert len({id(x) for x in streams})==1
    values=wide.read_slab(streams,0,1)
    assert len({id(x) for x in values})==1


def test_full_slab_evaluation_uses_six_states_and_keeps_negatives(tmp_path):
    shape=(2,2,3);paths=[]
    for i,value in enumerate((1.,2.,4.,2.,3.,5.)):
        path=tmp_path/f'{i}.dat';np.full(shape,value).tofile(path);paths.append(path)
    result=wide.inspect_fields(paths,shape,(3.,0.),np.array([1.,2.,3.]),.2)
    assert not result['gates']['positive']
    assert sum(s['negative_q'] for s in result['slabs'])==12
    assert sum(s['negative_p'] for s in result['slabs'])==12
    assert all(len(c['inputs_hex'])==6 for c in result['cuts'])
    assert result['slabs'][0]['minimum_q']==-2
    assert result['slabs'][0]['minimum_p']==-1
