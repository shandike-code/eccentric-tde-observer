import numpy as np
import pytest
from operations import x20_boundary_subspace as m


def test_boundary_equality_changes_unconstrained_minimum():
    g=np.eye(4);g[0,1:]=g[1:,0]=[-.1,-.2,-.3]
    c,r=m.constrained_solution(g,[1,1,0,0]);assert c[0]==pytest.approx(-1)
    np.testing.assert_allclose(c[1:],[.2,.3]);assert r['retained_rank']==3


def test_unresolved_boundary_is_not_fabricated():
    g=np.diag([1.,1.,1e-20,0.])
    with pytest.raises(ValueError,match='outside resolved'):m.constrained_solution(g,[1,0,0,1])
    c,r=m.constrained_solution(g,[0,0,0,0]);assert r['retained_rank']==1 and np.array_equal(c,np.zeros(3))


def test_positivity_and_coefficient_cap_are_global():
    assert m.positive_upper(np.array([1.,0.]),np.array([-1.,1.]))==.5
    assert m.positive_upper(np.array([0.]),np.array([-1e-320]))==0
    c,r=m.bounded_coefficients(np.array([100.,0.,0.]),.5)
    assert r['coefficient_l1']<=17 and r['selected_fraction']<=.45
    with pytest.raises(ValueError):m.positive_upper(np.array([-1.]),np.array([0.]))


def test_affine_fields_use_one_anchor_and_same_coefficients():
    aa=[np.array([float(i+1)]) for i in range(6)];c=np.array([.2,-.1,.3])
    x,y=m.basis_fields(aa,c);w=m.weights(c)
    assert w.sum()==pytest.approx(1)
    assert x[0]==pytest.approx(w@np.array([1.,2.,4.,5.]))
    assert y[0]==pytest.approx(w@np.array([2.,3.,5.,6.]))


def test_full_stream_prediction_and_half_identity(tmp_path):
    shape=(2,2,2);paths=[]
    for i,n in enumerate([3.,4.,5.,6.,7.,8.]):
        p=tmp_path/str(i);np.full(shape,n).tofile(p);paths.append(p)
    c=np.array([.1,.1,.1]);geometry=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(2))
    r=m.measure_candidates(paths,shape,c,geometry);assert not r['passed']
    full,half=tmp_path/'f',tmp_path/'h';m.write_candidates(paths,shape,c,full,half)
    assert np.array_equal(np.fromfile(half),.5*np.fromfile(paths[1])+.5*np.fromfile(full))
    with pytest.raises(FileExistsError):m.write_candidates(paths,shape,c,full,half)


def test_three_pass_proposal_matches_small_affine_operator(tmp_path):
    import json
    shape=(2,2,2);rates=np.linspace(.2,.9,8).reshape(shape);b=np.ones(shape)
    a=np.linspace(3.,5.,8).reshape(shape);h=np.linspace(9.,2.,8).reshape(shape)
    operator=lambda z:rates*z+b
    aa=[a,operator(a),operator(operator(a)),h,operator(h),operator(operator(h))]
    paths=[]
    for i,z in enumerate(aa):
        p=tmp_path/str(i);z.tofile(p);paths.append(p)
    geo=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(2))
    result=m.propose(paths,shape,geo);json.dumps(result,allow_nan=False)
    q,p=m.basis_fields(aa,result['selected_coefficients'])
    np.testing.assert_allclose(operator(q),p,rtol=1e-14,atol=1e-14)
    assert np.all(q>=0) and np.all(p>=0) and result['bounds']['coefficient_l1']<=17
    assert result['prediction']['fixed_scale_l2_ratios'][1]==pytest.approx(np.linalg.norm(p-q)/np.linalg.norm(aa[2]-aa[1]))
