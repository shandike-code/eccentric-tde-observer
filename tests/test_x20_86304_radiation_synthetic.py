import copy
from decimal import Decimal
import numpy as np
import pytest
from handoff.audit_tools.exercise_x20_86304_radiation import scalar_oracle,exercise
from operations.x20_85889_chord_scan_diagonal import slab_statistics


@pytest.mark.parametrize('case',['parallel','reverse','cancel','zero','nonparallel'])
def test_oracle(case):
    x=np.arange(24,dtype='<f8').reshape(4,2,3)/8+4
    if case=='parallel':a=[x,.5*x+4,.25*x+6,x+2,.5*x+5,.25*x+6.5]
    if case=='reverse':a=[x,16-x,x,2+x,14-x,2+x]
    if case=='cancel':a=[x,x+1,x+2,x+2,x+1,x]
    if case=='zero':a=[np.zeros_like(x) for _ in range(6)]
    if case=='nonparallel':a=[np.random.default_rng(i).integers(1,64,x.shape).astype('<f8')/8 for i in range(6)]
    before=[v.tobytes() for v in a];r=slab_statistics(a)
    assert scalar_oracle(a,r)==250;assert before==[v.tobytes() for v in a]
    bad=copy.deepcopy(r);bad['pairs'][2]['moments']['value'][1][3]='12345678'
    with pytest.raises(ValueError):scalar_oracle(a,bad)


def test_actual_wiring(tmp_path):
    assert exercise(tmp_path/'small')['scalar_matrix_checks']==1250


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.])
def test_nonphysical(value):
    a=[np.ones((1,2,3)) for _ in range(6)];a[0][0,0,0]=value
    with pytest.raises(ValueError):slab_statistics(a)


def test_extreme():
    t=np.nextafter(0.,1.);a=[np.full((1,1,1),i*t) for i in range(1,7)]
    if np.finfo(np.longdouble).maxexp<=1024:
        with pytest.raises(ArithmeticError):slab_statistics(a)
    else:assert Decimal(slab_statistics(a)['gram']['value'][0][0])>0
    a=[np.full((1,1,1),float(v)) for v in [0,1e308,0,1e308,0,1e308]]
    with pytest.raises(ArithmeticError):slab_statistics(a)


def test_wrong_coefficients(monkeypatch):
    from operations import x20_85889_chord_scan_diagonal as kernel
    coefficients=list(kernel.COEFFICIENTS);last=list(coefficients[-1]);last[0]=(0,0,0,0,0);coefficients[-1]=tuple(last)
    monkeypatch.setattr(kernel,'COEFFICIENTS',tuple(coefficients))
    x=np.arange(24,dtype='<f8').reshape(4,2,3)+2
    a=[x,.5*x+4,.25*x+6,x+3,.5*x+5.5,.25*x+6.75]
    with pytest.raises(ArithmeticError,match='basis reconstruction'):kernel.slab_statistics(a)


def test_zero_ratio_and_forged_error(tmp_path):
    import hashlib,json
    from operations.x20_85889_chord_scan import scan
    from handoff.audit_tools.review_x20_85889_chord_scan import review
    claims=[]
    for i in range(6):
        raw=np.zeros((1,2,3),dtype='<f8').tobytes();p=tmp_path/f'zero-{i}.bin';p.write_bytes(raw)
        claims.append(dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    d=scan(claims,[1,2,3],lambda _:None)
    d['slabs'][0].update(slab_statistics([np.zeros((1,2,3)) for _ in range(6)]))
    assert all(p['mapped_difference_l2_ratio'] is None for p in review(d)['total']['pairs'])
    d['slabs'][0]['pairs'][0]['reconstruction_error_square'][0]='1e40'
    with pytest.raises(ValueError):review(d)
