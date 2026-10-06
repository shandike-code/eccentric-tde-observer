import copy
from decimal import Decimal, localcontext
import hashlib
from pathlib import Path
import numpy as np
import pytest
from operations.x20_85889_chord_scan import slab_statistics,scan,Guard
from handoff.audit_tools.review_x20_85889_chord_scan import review


def fields(shape=(129,2,3)):
    x=np.arange(np.prod(shape),dtype=float).reshape(shape)%11+2
    y=np.flip(x,axis=0)+3
    return [x,.5*x+4,.25*x+6,y,.5*y+4,.25*y+6]


def claims_for(tmp_path,aa):
    claims=[]
    for i,a in enumerate(aa):
        p=tmp_path/f'synthetic-{i}.bin';raw=a.astype('<f8').tobytes();p.write_bytes(raw)
        claims.append(dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    return claims


def run(tmp_path,aa=None,progress=lambda r:None,guard=None):
    aa=fields() if aa is None else aa
    return scan(claims_for(tmp_path,aa),list(aa[0].shape),progress,guard)


def test_affine_contraction_all_pairs_and_tail(tmp_path):
    data=run(tmp_path);out=review(data)
    assert out['slabs']==5 and len(out['blocks'])==2
    for pair in out['total']['pairs']:
        assert Decimal(pair['mapped_difference_l2_ratio'])==Decimal('.5')
        assert Decimal(pair['direction_projection'])==Decimal('.5')
        assert Decimal(pair['relative_change_l2'])==Decimal('.5')
    assert data['field_bytes_read']==18*129*2*3*8


def test_independent_scalar_gram_oracle():
    rng=np.random.default_rng(103)
    aa=[rng.integers(1,200,size=(2,3,4)).astype(float)/8 for _ in range(6)]
    result=slab_statistics(aa)
    with localcontext() as ctx:
        ctx.prec=80
        vectors=[[],[],[],[],[]]
        for values in zip(*(a.flat for a in aa)):
            ap,af,am,hp,hf,hm=map(lambda x:Decimal.from_float(float(x)),values)
            for dest,v in zip(vectors,[hf-af,af-ap,am-af,hf-hp,hm-hf]):dest.append(v)
        for i in range(5):
            for j in range(5):
                assert Decimal(result['gram']['value'][i][j])==sum(a*b for a,b in zip(vectors[i],vectors[j]))


def test_zero_is_undefined_not_floor(tmp_path):
    out=review(run(tmp_path,[np.zeros((1,1,1)) for _ in range(6)]))
    assert all(p['mapped_difference_l2_ratio'] is None for p in out['total']['pairs'])


def test_nonparallel_signed_moments(tmp_path):
    rng=np.random.default_rng(44)
    out=review(run(tmp_path,[rng.integers(1,20,size=(3,2,2)).astype(float) for _ in range(6)]))
    assert any(Decimal(p['cos_difference_mapped'])<Decimal('.9') for p in out['total']['pairs'])
    assert any(Decimal(x)<0 for row in out['total']['gram'] for x in row)


@pytest.mark.parametrize('fault',['nan','inf','negative','dtype','shape'])
def test_reject_bad_field(fault):
    aa=fields((2,2,2))
    if fault=='nan':aa[0][0,0,0]=np.nan
    if fault=='inf':aa[0][0,0,0]=np.inf
    if fault=='negative':aa[0][0,0,0]=-1
    if fault=='dtype':aa[0]=aa[0].astype('float32')
    if fault=='shape':aa[0]=aa[0][0:1]
    with pytest.raises(ValueError):slab_statistics(aa)


def test_subnormal_never_silently_discarded():
    tiny=np.nextafter(0.,1.)
    aa=[np.array([[[v*tiny]]]) for v in (1,2,3,4,5,6)]
    if np.finfo(np.longdouble).maxexp<=1024:
        with pytest.raises(ArithmeticError,match='underflow'):slab_statistics(aa)
    else:
        row=slab_statistics(aa)
        assert Decimal(row['gram']['value'][0][0])>0


@pytest.mark.parametrize('fault',['hash','size','tail','duplicate','symlink'])
def test_source_rejections(tmp_path,fault):
    aa=fields((2,1,1));claims=claims_for(tmp_path,aa)
    if fault=='hash':claims[0]['sha256']='0'*64
    if fault=='size':claims[0]['size_bytes']-=8
    if fault=='tail':
        with Path(claims[0]['path']).open('ab') as f:f.write(b'12345678')
    if fault=='duplicate':claims[1]=claims[0]
    if fault=='symlink':
        p=Path(claims[0]['path']);target=p.with_suffix('.target');p.rename(target);p.symlink_to(target)
    with pytest.raises(ValueError):scan(claims,[2,1,1],lambda r:None)


@pytest.mark.parametrize('fault',['missing','duplicate','order','extent','block','sha','psd','direct','incomplete','nan','labels','stat','rounding','reconstruction'])
def test_reviewer_rejects_corruption(tmp_path,fault):
    data=run(tmp_path)
    if fault=='missing':data['slabs'].pop()
    if fault=='duplicate':data['slabs'].append(data['slabs'][0])
    if fault=='order':data['slabs'].reverse()
    if fault=='extent':data['slabs'][-1]['group_count']=32
    if fault=='block':data['slabs'][-1]['block']=0
    if fault=='sha':data['hashes_after'][0]='0'*64
    if fault=='psd':
        g=data['slabs'][0]['gram']
        for key in ('value','absolute'):g[key][0][1]=g[key][1][0]='1e40'
    if fault=='direct':data['slabs'][0]['pairs'][0]['moments']['value'][0][0]='1e40'
    if fault=='incomplete':data['status']='stopped'
    if fault=='nan':data['slabs'][0]['gram']['value'][0][0]='NaN'
    if fault=='labels':data['labels'].reverse()
    if fault=='rounding':data['arithmetic']['rounding_mode_code']=1
    if fault=='reconstruction':data['slabs'][0]['pairs'][0]['reconstruction_error_square'][0]='1e40'
    if fault=='stat':data['source_stats_before'][0]=data['source_stats_after'][0]=(0,0,8,0,0)
    with pytest.raises(ValueError):review(data)


def test_replace_mid_scan(tmp_path):
    aa=fields();claims=claims_for(tmp_path,aa);done=[]
    def mutate(row):
        if not done:
            p=Path(claims[0]['path']);replacement=p.with_suffix('.replacement')
            replacement.write_bytes(p.read_bytes());replacement.replace(p);done.append(True)
    with pytest.raises(ValueError):scan(claims,list(aa[0].shape),mutate)


def test_stop_preserves_completed_slab_only(tmp_path):
    rows=[];guard=Guard(stop=lambda:bool(rows))
    with pytest.raises(InterruptedError):run(tmp_path,progress=rows.append,guard=guard)
    assert len(rows)==1 and rows[0]['first_group']==0


@pytest.mark.parametrize('fault',['time','rss'])
def test_resource_rejection(fault):
    g=Guard(clock=lambda:1,rss=lambda:5,seconds=0 if fault=='time' else 1,rss_bytes=5 if fault=='rss' else 6)
    with pytest.raises(TimeoutError if fault=='time' else MemoryError):g.check()


def test_stop_inside_numerical_slab():
    calls=[]
    def check():
        calls.append(1)
        if len(calls)==3:raise InterruptedError('stop during reduction')
    with pytest.raises(InterruptedError):slab_statistics(fields((2,1,1)),check)
    assert len(calls)==3


def test_short_read_after_start(tmp_path):
    aa=fields();claims=claims_for(tmp_path,aa);once=[]
    def truncate(row):
        if not once:
            with Path(claims[0]['path']).open('r+b') as f:f.truncate(32*2*3*8)
            once.append(True)
    with pytest.raises(ValueError,match='short field read'):
        scan(claims,list(aa[0].shape),truncate)


def test_wrong_coefficient_cannot_hide_in_error_budget(monkeypatch):
    import operations.x20_85889_chord_scan as core
    coefficients=list(core.COEFFICIENTS)
    bad=list(coefficients[0]);bad[0]=(0,0,0,0,0);coefficients[0]=tuple(bad)
    monkeypatch.setattr(core,'COEFFICIENTS',tuple(coefficients))
    with pytest.raises(ArithmeticError,match='basis reconstruction'):core.slab_statistics(fields((2,1,1)))
