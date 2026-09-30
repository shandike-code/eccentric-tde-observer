import copy,json
from pathlib import Path
import numpy as np
import pytest
from operations.x20_window_fields import basis_fields,measure_candidates
from operations.x20_window_prediction import require_candidate


def fields(tmp_path):
    shape=(34,2,2);x=np.linspace(2,5,np.prod(shape)).reshape(shape)
    operator=lambda z:.8*z+.5
    aa=[z for p in (x,x+1,x*.7,x*.6) for z in (p,operator(p))]
    paths=[]
    for i,z in enumerate(aa):
        p=tmp_path/str(i);z.tofile(p);paths.append(p)
    return shape,aa,paths,operator


def test_pairs_and_half_preserve_affine_operator(tmp_path):
    shape,aa,paths,op=fields(tmp_path);q,p=basis_fields(aa,[.2,-.1,.05])
    np.testing.assert_allclose(p,op(q),rtol=2e-15)
    np.testing.assert_allclose(.5*aa[1]+.5*p,op(.5*aa[0]+.5*q),rtol=2e-15)


def test_streamed_norms_and_short_tail(tmp_path):
    shape,aa,paths,op=fields(tmp_path);co=[.2,-.1,.05];q,p=basis_fields(aa,co)
    geo=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(34))
    r=measure_candidates(paths,shape,co,geo)
    assert [z['group_count'] for z in r['slabs']]==[32,2]
    assert r['fixed_scale_l2_ratios'][1]==pytest.approx(np.linalg.norm(p-q)/np.linalg.norm(aa[1]-aa[0]))


def test_negative_field_rejected_without_floor(tmp_path):
    shape,aa,paths,op=fields(tmp_path);geo=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(34))
    r=measure_candidates(paths,shape,[-10,0,0],geo)
    assert not r['passed'] and min(r['slabs'][0]['minima'])<0


@pytest.mark.parametrize('damage',['hash','coefficient','cap','gate','fraction'])
def test_candidate_identity_guard(damage):
    ev=Path('handoff/evidence')
    c=json.loads((ev/'20260930-x20-window-candidate-result.json').read_text())
    a=json.loads((ev/'20260930-x20-window-candidate-review.json').read_text());sha=a['result_sha256']
    require_candidate(c,a,sha)
    if damage=='hash':sha='wrong'
    elif damage=='coefficient':c['selected_coefficients'][0]+=.1
    elif damage=='cap':c['raw_coefficients'][0]=20;c['selected_coefficients'][0]=18
    elif damage=='fraction':c['half_fraction']=.4
    else:c['checks']['full_boundary_l1']=False
    with pytest.raises(ValueError):require_candidate(c,a,sha)
