import copy
import numpy as np
import pytest
from operations import x20_history_operator as m
from handoff.audit_tools.review_x20_histories import comparison,localization


def test_positivity_intersects_both_signs():
    assert m.positivity_interval(np.array([2.,3.]),np.array([1.,-1.]))==(-2.,3.)
    assert m.positivity_interval(np.array([0.,0.]),np.array([1.,-1.]))==(-0.,0.)
    with pytest.raises(ValueError):m.positivity_interval(np.array([-1.]),np.array([1.]))


def test_frozen_operator_rejects_other_configuration_change():
    a=dict(run='a',warm_seed=1,sources=[],boundary_threshold=.001)
    b=dict(a,run='b',warm_seed=2,sources=[1]);m.same_operator_config(a,b)
    b['boundary_threshold']=.002
    with pytest.raises(ValueError):m.same_operator_config(a,b)


def test_direction_reduces_known_affine_defect_without_changing_arrays():
    x=np.array([5.,5.]);h=np.array([8.,7.]);y=.8*x+1.5;k=.8*h+1.5
    before=[z.copy() for z in (x,y,h,k)];r=m.basis_stats(before)
    choice=m.select_coefficient(r['gram'],r['alpha_interval']);a=choice['alpha']
    assert choice['difference_gain_l2']==pytest.approx(.8)
    assert choice['difference_projection']==pytest.approx(.8)
    assert choice['alpha']==pytest.approx(.9*2.5/2.6)
    assert np.linalg.norm((y+a*(k-y))-(x+a*(h-x)))<np.linalg.norm(y-x)
    assert all(np.array_equal(u,v) for u,v in zip(before,(x,y,h,k)))


def test_zero_difference_is_not_a_resolved_direction():
    g=np.diag([1.,0.,2.,2.]);g[2,3]=g[3,2]=2.
    q=m.select_coefficient(g,[-8.,8.]);assert not q['direction_resolved'] and q['alpha']==0 and q['unconstrained_alpha'] is None
    g[0,0]=-1
    with pytest.raises(ValueError):m.select_coefficient(g,[-8.,8.])


def test_true_midpoint_rejects_nonlinear_map(tmp_path):
    shape=(3,2,2);x=np.ones(shape);h=2*x;y=.8*x+1;k=.8*h+1;mid=.5*x+.5*h;t=.8*mid+1
    paths=[]
    for i,z in enumerate((x,y,h,k,mid,t)):
        p=tmp_path/f'{i}.dat';z.tofile(p);paths.append(p)
    assert m.midpoint_comparison(paths,shape)['affinity_pass']
    (t+.01).tofile(paths[-1]);assert not m.midpoint_comparison(paths,shape)['affinity_pass']
    (mid+.1).tofile(paths[-2])
    with pytest.raises(ValueError):m.midpoint_comparison(paths,shape)


def test_midpoint_writer_checks_input_and_refuses_overwrite(tmp_path):
    shape=(2,2,2);a=tmp_path/'a';b=tmp_path/'b';out=tmp_path/'out'
    np.ones(shape).tofile(a);(3*np.ones(shape)).tofile(b)
    m.write_midpoint([a,b],out,shape);assert np.array_equal(np.fromfile(out),np.full(8,2.))
    with pytest.raises(FileExistsError):m.write_midpoint([a,b],out,shape)


def test_vector_difference_is_not_difference_of_norms():
    a={'previous':np.ones(8),'final':np.ones(8)};b={k:-v for k,v in a.items()}
    r=comparison(a,b,np.ones(8),np.ones(2),np.ones(3));assert not r['passed']
    with pytest.raises(ValueError):comparison(a,b,np.ones(8),np.ones(2),np.zeros(3))


def test_localization_keeps_all_cells_and_components():
    d=np.ones(512);r=localization(d,np.ones(128))
    assert r['component_fractions']==pytest.approx([.25]*4)
    assert len(r['cell_fractions'])==128 and sum(r['cell_fractions'])==pytest.approx(1)


def test_audit_default_rejects_unregistered_child_and_map24(tmp_path):
    from handoff.audit_tools.review_refreshed_directions import audit_pair
    with pytest.raises(AssertionError):audit_pair(tmp_path,2,tmp_path,tmp_path,tmp_path,'historical')
    with pytest.raises(AssertionError):audit_pair(tmp_path,24,tmp_path,tmp_path,tmp_path,'control')


def test_retained_pair_refuses_mapped_slot_or_partial_history():
    claims=[dict(path=str(i),sha256=str(i),size_bytes=m.pipeline.STATE_BYTES) for i in range(3)]
    rows=[dict(iteration=1,input_sha256='0',output_sha256='1'),dict(iteration=2,input_sha256='1',output_sha256='2')]
    state=dict(history=rows,active_map=None,current_sha256='2')
    ret=dict(history_rows=rows,endpoints=dict(previous=claims[0],final=claims[1],mapped_final=claims[2]))
    assert m.retained_pair(state,ret,2)==claims[1:]
    bad=copy.deepcopy(ret);bad['endpoints']['final']=claims[0]
    with pytest.raises(ValueError):m.retained_pair(state,bad,2)
    state['active_map']={}
    with pytest.raises(ValueError):m.retained_pair(state,ret,2)


def test_complete_stream_scan_reports_prediction_not_map(tmp_path):
    shape=(3,2,2);x=np.full(shape,5.);h=np.full(shape,8.);y=.8*x+1.5;k=.8*h+1.5
    paths=[]
    for i,z in enumerate((x,y,h,k)):
        p=tmp_path/f'{i}.dat';z.tofile(p);paths.append(p)
    r=m.collect_scan(paths,shape,dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(3)))
    assert r['choice']['alpha']==pytest.approx(.75)
    assert r['l2_ratio']==pytest.approx(.1)
    assert r['difference_nonparallel_fraction']==pytest.approx(0,abs=1e-14)
    assert not r['candidate_written'] and r['true_map_required']


def test_black_tail_small_direction_does_not_overflow_ratio():
    with np.errstate(over='raise',divide='raise',invalid='raise'):
        assert m.positivity_interval(np.array([1.,1.]),np.array([1e-320,-1e-320]))==(-8.,8.)
