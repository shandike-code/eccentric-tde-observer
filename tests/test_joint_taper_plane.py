import numpy as np
import pytest
from operations import joint_taper_plane as p


def test_convex_quadratic_interior_and_linf_cut():
    g=np.eye(2);b=np.array([-.4,-.3]);s=p.solve(g,b,[])
    np.testing.assert_allclose(s['uv'],.99*np.array([.4,.3]))
    # r=.5,M=1,d1=2,d2=0 implies alpha<=.25.
    cut=p.cut_at(.5,2.,0.,1,(0,0,0),1.)
    s=p.solve(g,b,[cut]);np.testing.assert_allclose(s['uv'],.99*np.array([.25,.3]))
    assert sum(p.coefficients(s['uv']))==1


def test_triangle_boundary_and_origin_only():
    s=p.solve(np.eye(2),[-2,-2],[]);np.testing.assert_allclose(s['uv'],[.495,.495])
    cuts=[dict(row=[-1,0],lower=0),dict(row=[0,-1],lower=0)]
    assert p.solve(np.eye(2),[-2,-2],cuts)['uv']==[0,0]


@pytest.mark.parametrize('g',[np.zeros((2,2)),np.ones((2,2)),np.diag([-1,1])])
def test_degenerate_directions_are_unresolved(g):assert not p.solve(g,[0,0],[])['resolved']


@pytest.mark.parametrize('uv',[[-.01,0],[.7,.4],[float('nan'),0]])
def test_invalid_convex_coefficients_rejected(uv):
    with pytest.raises(ValueError):p.coefficients(uv)


def states(tmp_path):
    shape=(32,2,2);x=np.ones(shape);r=np.full(shape,.1);d1=np.full(shape,-.15);d2=np.full(shape,-.15)
    d1[0]=.3;d2[1]=.3
    q=x+.2;z=x+.3
    arrays=(x,x+r,q,q+r+d1,z,z+r+d2);paths=[]
    for i,a in enumerate(arrays):
        f=tmp_path/f'{i}.dat';a.tofile(f);paths.append(f)
    return shape,paths


def test_streaming_gram_candidates_constraints_and_roundoff(tmp_path):
    shape,paths=states(tmp_path);flux=lambda a,start:np.sum(a,axis=(1,2))
    g=p.gram_scan(paths,shape,flux);o={'boundary_l1':1,'boundary_bolometric':1}
    a=p.inspect(paths,shape,[.3,.3],g,o,selected=(0,))
    assert a['cuts'] and not a['checks']['linf_nonincrease']
    assert abs(a['l2_ratio']-a['quadratic_l2_ratio'])<1e-14
    for cut in a['cuts']:
        r,d1,d2=map(float.fromhex,cut['values_hex']);M=float.fromhex(cut['maximum_hex'])
        np.testing.assert_allclose(cut['row'],[-cut['sign']*d1/M,-cut['sign']*d2/M])
    z=p.inspect(paths,shape,[0,0],g,o,selected=(0,));assert z['linf_ratio']==1 and not z['checks']['nonzero']
    with pytest.raises(ValueError,match='unselected'):p.inspect(paths,shape,[.1,.1],g,o,selected=())


def test_search_never_accepts_optimizer_without_full_scan():
    g={'gram':[[1,0],[0,1]],'rhs':[-.4,-.3]};calls=[]
    def ev(uv):calls.append(uv);return {'checks':{'linf':False},'cuts':[]}
    a=p.search(g,ev);assert len(calls)==1 and not a['eligible_for_independent_review'] and a['reason']=='cost_or_boundary_gate_failed'
    def fail(uv):raise RuntimeError('worker failure')
    with pytest.raises(RuntimeError):p.search(g,fail)


def test_search_budget_and_no_new_constraints():
    g={'gram':[[1,0],[0,1]],'rhs':[-.4,-.3]};n=[0]
    def ev(uv):
        n[0]+=1
        return {'checks':{'linf':False},'cuts':[p.cut_at(.5,1,0,1,(n[0],0,0),1)]}
    a=p.search(g,ev);assert a['passes']==6 and not a['eligible_for_independent_review'] and a['reason']=='constraint_budget_exhausted'
    def duplicate(uv):return {'checks':{'linf':False},'cuts':[p.cut_at(.5,1,0,1,(0,0,0),1)]}
    assert p.search(g,duplicate)['reason']=='no_new_constraints'


def test_physical_inputs_and_read_interrupt(tmp_path):
    shape,paths=states(tmp_path);flux=lambda a,start:np.sum(a,axis=(1,2))
    def stop():raise InterruptedError('stop')
    with pytest.raises(InterruptedError):p.gram_scan(paths,shape,flux,stop)
    a=np.fromfile(paths[0]);a[0]=np.nan;a.tofile(paths[0])
    with pytest.raises(ValueError):p.gram_scan(paths,shape,flux)


def test_unchanged_subnormal_copied():
    a=np.array([np.nextafter(0.,1.)]);assert np.array_equal(p.mix([a,a,a],p.coefficients([.2,.3])),a)


def test_accepted_candidate_requires_every_check():
    gram={'gram':[[1,0],[0,1]],'rhs':[-.3,-.3]}
    result=p.search(gram,lambda uv:{'checks':{'linf':True,'boundary':True,'cost':True},'cuts':[]})
    assert result['eligible_for_independent_review'] and result['passes']==2
    result=p.search(gram,lambda uv:{'checks':{'linf':True,'boundary':False,'cost':True},'cuts':[]})
    assert not result['eligible_for_independent_review']


def test_negative_signed_constraint_and_nonfinite_gram():
    c=p.cut_at(-.5,-2,0,-1,(1,2,3),1.)
    np.testing.assert_allclose(c['row'],[-2,0]);assert c['lower']==-.5
    with pytest.raises(ValueError):p.solve([[np.nan,0],[0,1]],[0,0],[])
    with pytest.raises(ValueError):p.solve([[1,0],[.1,1]],[0,0],[])
