import copy,json
from pathlib import Path
import numpy as np
import pytest
from operations import x20_spectral_feasibility as m
from handoff.audit_tools.review_x20_capped import reduce_prediction


def test_coefficient_halfspace_and_exact_polygon_minimum():
    poly=m.hull([[-1,-1],[-1,1],[1,-1],[1,1],[0,0]])
    clipped=m.clip_polygon(poly,np.array([1.,0.]),0)
    assert len(clipped)==4 and np.all(clipped[:,0]<=0)
    target=np.array([.5,.25,0]);g=np.eye(4);g[0,0]=1+target@target;g[0,1:]=g[1:,0]=-target
    basis=np.array([[1.,0],[0,1],[0,0]])
    p,r=m.minimize_polygon(g,np.zeros(3),basis,poly,safety=1)
    np.testing.assert_allclose(p,target[:2]);assert r['squared_upper']==pytest.approx(1/g[0,0])
    p,r=m.minimize_polygon(g,np.zeros(3),basis,clipped,safety=1)
    np.testing.assert_allclose(p,[0,.25]);assert r['squared_support_lower']==pytest.approx(r['squared_upper'])


def test_plane_hull_preserves_weight_cap_and_equality():
    f=np.array([.1,1,-2,.5]);anchor,basis,poly=m.coefficient_plane(f)
    for point in poly:
        c=anchor+basis@point;w=np.r_[c[0],1-sum(c),c[1:]]
        assert abs(f[0]+f[1:]@c)<1e-13 and sum(abs(w))<=17*(1+1e-13)
    with pytest.raises(ValueError):m.coefficient_plane([1,0,0,0])


def toy_spectra():
    a=np.linspace(3,5,8);h=np.linspace(9,2,8);rates=np.linspace(.2,.9,8)
    op=lambda z:rates*z+1
    return np.stack([a,op(a),op(op(a)),h,op(h),op(op(h))])


def test_spectral_cut_is_a_global_supporting_inequality():
    system=m.spectral_system(toy_spectra());anchor,basis,poly=m.coefficient_plane(system['flux'])
    c=anchor+basis@np.mean(poly,axis=0);limit=system['original_boundary_l1'];cut=m.spectral_cut(system,c,.9,limit)
    a=np.array(cut['a']);b=cut['b']
    assert a@c-b==pytest.approx(cut['numerator']/limit-cut['denominator'],abs=1e-13)
    for point in poly:
        z=anchor+basis@(.1*point+.9*np.mean(poly,axis=0));r=m.spectral_cut(system,z,.9,limit)
        assert a@z-b<=r['numerator']/limit-r['denominator']+1e-12


def test_bounded_solver_reports_no_improvement_without_writing_candidate():
    r=m.solve(np.eye(4),toy_spectra())
    assert r['status']=='no_20pct_candidate_in_registered_plane' and len(r['iterations'])==1
    assert r['iterations'][0]['bound']['l2_conservative_lower']>.8
    assert not r['candidate_written'] and not r['true_map_performed'];json.dumps(r,allow_nan=False)


def test_stream_collection_preserves_all_groups(tmp_path):
    shape=(2,2,2);paths=[]
    for i in range(6):
        p=tmp_path/str(i);np.full(shape,float(i+1)).tofile(p);paths.append(p)
    geometry=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(2))
    a=m.collect(paths,shape,geometry)
    assert a.shape==(6,2) and np.isfinite(a).all() and np.all(a>0)
    np.testing.assert_allclose(a[5],6*a[0])


def test_multiple_spectral_cuts_reach_the_constrained_boundary():
    spectra=np.array([[9.8,9.8],[10.1,10.1],[10.2,10.2],[10,10],[10.2,10],[10.2,10.2]])
    target=np.array([-.45,1.8,-1.8]);g=np.eye(4);g[0,0]=.1+target@target;g[0,1:]=g[1:,0]=-target
    result=m.solve(g,spectra);rows=result['iterations']
    assert result['status']=='algebraic_candidate_requires_full_field_validation' and len(rows)>1
    assert rows[0]['cuts'][0]['ratio_to_limit']>3
    assert all(r['ratio_to_limit']<=1 for r in rows[-1]['cuts'])
    assert .7<rows[-1]['bound']['l2_upper']<.8
    assert all(y['bound']['squared_support_lower']>=x['bound']['squared_support_lower']-1e-12 for x,y in zip(rows,rows[1:]))


def test_new_audit_rejects_changed_spectral_verdict_or_lost_group():
    folder=Path('outputs/review-20260925')
    p=folder/'x20-capped-80925-received/prediction.json'
    if not p.exists():pytest.skip('Mac received artifacts')
    p=json.loads(p.read_text());s=json.loads((folder/'x20-subspace-80862-received/prediction.json').read_text())
    r=reduce_prediction(p,s);assert r['boundary_ratios']['boundary_l1'][1]>6
    bad=copy.deepcopy(p);bad['prediction']['checks']['full_boundary_l1']=True
    with pytest.raises(AssertionError):reduce_prediction(bad,s)
    bad=copy.deepcopy(p);bad['prediction']['slabs'].pop()
    with pytest.raises(AssertionError):reduce_prediction(bad,s)
