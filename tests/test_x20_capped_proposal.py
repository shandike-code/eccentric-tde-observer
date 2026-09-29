import copy,json
import numpy as np
from operations import x20_boundary_subspace as previous
from operations import x20_capped_subspace as current


def test_capped_proposal_reuses_gram_but_remeasures_full_fields(tmp_path):
    shape=(2,2,2);rates=np.linspace(.2,.9,8).reshape(shape);source=np.ones(shape)
    a=np.linspace(3.,5.,8).reshape(shape);h=np.linspace(9.,2.,8).reshape(shape)
    operator=lambda z:rates*z+source
    arrays=[a,operator(a),operator(operator(a)),h,operator(h),operator(operator(h))]
    paths=[]
    for i,z in enumerate(arrays):
        p=tmp_path/str(i);z.tofile(p);paths.append(p)
    geometry=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(2))
    prior=previous.propose(paths,shape,geometry);saved=copy.deepcopy(prior)
    result=current.propose(paths,shape,geometry,prior)
    assert prior==saved and result['reused_gram_from_job']==80862
    json.dumps(result,allow_nan=False)
    q,p=previous.basis_fields(arrays,result['selected_coefficients'])
    np.testing.assert_allclose(operator(q),p,rtol=1e-14,atol=1e-14)
    assert np.min(q)>=0 and np.min(p)>=0 and result['bounds']['coefficient_l1']<=17
    np.testing.assert_allclose(result['prediction']['fixed_scale_l2_ratios'][1],np.linalg.norm(p-q)/np.linalg.norm(arrays[2]-arrays[1]),rtol=1e-12)
