import hashlib
import numpy as np
import pytest
from operations.x20_cross_seed_chord import moments,reduce_rows,scan


def test_known_linear_action_with_common_affine_source():
    a=np.arange(12.).reshape(3,4)+1;h=a+np.arange(12.).reshape(3,4)/20
    r=reduce_rows([moments(a,.8*a+2,h,.8*h+2)])
    assert r['rayleigh_action']==pytest.approx(.8)
    assert r['relative_change_l2']==pytest.approx(.2)
    assert r['mapped_difference_l2_ratio']==pytest.approx(.8)


def test_equal_input_difference_is_not_a_spectral_radius():
    z=np.ones((2,3));r=reduce_rows([moments(z,z,z,z)])
    assert r['zero_difference'] and r['rayleigh_action'] is None


def test_negative_intensity_rejected():
    with pytest.raises(ValueError):moments(np.ones(2),np.ones(2),-np.ones(2),np.ones(2))


def test_stream_rejects_false_sha(tmp_path):
    claims=[]
    for i in range(4):
        p=tmp_path/f'{i}.dat';np.ones((1,2,3),dtype='<f8').tofile(p)
        claims.append(dict(path=str(p),size_bytes=p.stat().st_size,sha256='0'*64))
    with pytest.raises(ValueError,match='SHA'):scan(claims,[1,2,3],lambda _:None)


def test_stream_matches_whole_array_and_preserves_last_short_block(tmp_path):
    a=np.arange(132*6,dtype=float).reshape(132,2,3)+1;h=a+2
    fields=[a,.9*a+1,h,.9*h+1];claims=[]
    for i,x in enumerate(fields):
        p=tmp_path/f'{i}.dat';x.astype('<f8').tofile(p)
        claims.append(dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    r=scan(claims,list(a.shape),lambda _:None)
    assert set(r['blocks'])=={'0','1'} and r['slabs'][-1]['group_count']==4
    direct=reduce_rows([moments(*fields)])
    for key in ('dd','de','ee','rayleigh_action','relative_change_l2'):
        assert r['total'][key]==pytest.approx(direct[key])
