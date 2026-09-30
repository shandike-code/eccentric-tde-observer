import hashlib
import numpy as np
import pytest
from operations.x20_window_basis import basis_moments,collect


def fields():
    x=np.arange(132*4,dtype=float).reshape(132,2,2)+1
    a=[x,x+2,x+.7,x+1.2];return [v for z in a for v in (z,.9*z+3)]


def test_basis_order_and_exact_dot_products():
    z=fields();r=[z[i+1]-z[i] for i in (0,2,4,6)];b=np.asarray([r[0]]+[v-r[0] for v in r[1:]]).reshape(4,-1)
    q=basis_moments(z);np.testing.assert_allclose(q['gram'],b@b.T,rtol=1e-13,atol=1e-14)


def test_negative_or_missing_field_rejected():
    z=fields()
    with pytest.raises(ValueError):basis_moments(z[:6])
    z[3]=-z[3]
    with pytest.raises(ValueError):basis_moments(z)


def test_stream_hashes_and_short_final_slab(tmp_path):
    z=fields();claims=[]
    for i,v in enumerate(z):
        p=tmp_path/f'{i}.dat';v.astype('<f8').tofile(p);claims.append(dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    geo=dict(mu=np.array([-.5,.5]),weight=np.ones(2),width=np.ones(132))
    q=collect(claims,list(z[0].shape),geo);np.testing.assert_allclose(q['gram'],basis_moments(z)['gram'],rtol=1e-13,atol=1e-14)
    assert q['slabs'][-1]['group_count']==4 and q['all_eight_sha256_verified'] and not q['candidate_written']
    claims[-1]['sha256']='0'*64
    with pytest.raises(ValueError,match='SHA'):collect(claims,list(z[0].shape),geo)
