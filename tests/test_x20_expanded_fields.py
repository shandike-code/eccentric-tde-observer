import copy
import json
from pathlib import Path
import numpy as np
import pytest
from operations.x20_expanded_fields import basis_fields,measure_candidates,write_candidates
from operations.x20_expanded_validation import require_candidate


def fields(tmp_path):
    shape=(2,2,2);rates=np.linspace(.2,.9,8).reshape(shape);source=np.ones(shape)
    operator=lambda z:rates*z+source
    a=np.linspace(3.,5.,8).reshape(shape);h=np.linspace(9.,2.,8).reshape(shape);x=np.linspace(4.,7.,8).reshape(shape)
    aa=[a,operator(a),operator(operator(a)),h,operator(h),operator(operator(h)),x,operator(x)]
    paths=[]
    for i,z in enumerate(aa):p=tmp_path/str(i);z.tofile(p);paths.append(p)
    return shape,aa,paths,operator


def test_eight_field_formula_preserves_affine_operator_and_half_input(tmp_path):
    shape,aa,paths,operator=fields(tmp_path);c=np.array([.1,-.05,.03,.2])
    q,p=basis_fields(aa,c);np.testing.assert_allclose(p,operator(q),rtol=2e-15,atol=0)
    full,half=tmp_path/'full.dat',tmp_path/'half.dat'
    write_candidates(paths,shape,c,full,half)
    np.testing.assert_array_equal(np.fromfile(full).reshape(shape),q)
    np.testing.assert_array_equal(np.fromfile(half).reshape(shape),.5*aa[1]+.5*q)
    with pytest.raises(FileExistsError):write_candidates(paths,shape,c,full,half)


def test_streamed_norms_match_direct_whole_array(tmp_path):
    shape,aa,paths,operator=fields(tmp_path);c=[.1,-.05,.03,.2]
    geometry=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(2))
    r=measure_candidates(paths,shape,c,geometry);q,p=basis_fields(aa,c)
    np.testing.assert_allclose(r['fixed_scale_l2_ratios'][1],np.linalg.norm(p-q)/np.linalg.norm(aa[2]-aa[1]),rtol=1e-13)
    assert r['checks']['full_field_nonnegative'];json.dumps(r,allow_nan=False)


def test_negative_field_is_reported_and_not_written(tmp_path):
    shape,aa,paths,operator=fields(tmp_path)
    geometry=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(2))
    c=[0,0,0,-10];r=measure_candidates(paths,shape,c,geometry)
    assert not r['checks']['full_field_nonnegative'] and not r['passed']
    assert min(r['slabs'][0]['minima'])<0
    with pytest.raises(ValueError):write_candidates(paths,shape,c,tmp_path/'full.dat',tmp_path/'half.dat')
    assert not (tmp_path/'full.dat').exists()


@pytest.mark.parametrize('damage',['hash','fraction','coefficient','cap','gate'])
def test_validation_refuses_changed_candidate(damage):
    root=Path('handoff/evidence');rp=root/'20260930-x20-expanded-candidate-result.json'
    if not rp.exists():pytest.skip('audited small candidate')
    c=json.loads(rp.read_text());a=json.loads((root/'20260930-x20-expanded-candidate-review.json').read_text());digest=a['result_sha256']
    require_candidate(c,a,digest)
    if damage=='hash':digest='wrong'
    elif damage=='fraction':c['half_fraction']=.4
    elif damage=='coefficient':c['selected_coefficients'][3]+=.001
    elif damage=='cap':c['raw_coefficients'][3]=20;c['selected_coefficients'][3]=18
    else:c['checks']['full_boundary_l1']=False
    with pytest.raises(ValueError):require_candidate(c,a,digest)
