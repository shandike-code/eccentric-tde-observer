from decimal import Decimal, localcontext
import hashlib
from pathlib import Path
from types import FunctionType
import numpy as np
import pytest
from operations import x20_85889_chord_scan as old
from operations import x20_85889_chord_scan_reuse as new
from handoff.audit_tools.review_x20_85889_chord_scan import review


def fields(shape=(33, 2, 3), seed=601):
    rng = np.random.default_rng(seed)
    return [rng.integers(1, 200, size=shape).astype('<f8') / 8 for _ in range(6)]


@pytest.mark.parametrize('shape', [(1,1,1), (31,2,3), (32,2,3), (33,2,3), (129,2,3)])
@pytest.mark.parametrize('layout', ['C', 'F', 'strided'])
def test_all_numeric_fields_equal_and_inputs_unchanged(shape, layout):
    aa = fields(shape)
    if layout == 'F':
        aa = [np.asfortranarray(a) for a in aa]
    if layout == 'strided':
        aa = [a[:, :, ::-1] for a in aa]
    before = [a.tobytes() for a in aa]
    flags = [a.flags.writeable for a in aa]
    assert new.slab_statistics(aa) == old.slab_statistics(aa)
    assert [a.tobytes() for a in aa] == before
    assert [a.flags.writeable for a in aa] == flags


def test_binary64_expression_bits_and_readonly_cache():
    aa = fields()
    for a in aa:
        a.flat[0] = -0.0
        a.flat[1] = 0.0
    expected = {}
    for a, h in old.COMBINATIONS:
        d, ra, rh, mapped = aa[h]-aa[a], aa[a+1]-aa[a], aa[h+1]-aa[h], aa[h+1]-aa[a+1]
        keys = (new.subtract_key(h,a), new.subtract_key(new.subtract_key(h+1,h),new.subtract_key(a+1,a)),
                new.subtract_key(h+1,a+1), new.subtract_key(a+1,a), new.subtract_key(h+1,h))
        expected.update(zip(keys, (d,rh-ra,mapped,ra,rh)))
    cache = new._SlabCache(aa, lambda: None)
    for key, v in expected.items():
        assert cache.raw(key).tobytes() == v.tobytes()
        assert cache.vector(key).astype('<f8').tobytes() == v.tobytes()
        assert not cache.raw(key).flags.writeable
        assert not cache.vector(key).flags.writeable
    assert len(cache.binary64) == len(cache.longdouble) == 15


@pytest.mark.parametrize('seed', [18, 61, 89])
def test_general_float_scale_and_reconstruction_rounding(seed):
    rng = np.random.default_rng(seed)
    aa = [np.ldexp(1+rng.random((33,2,3)),rng.integers(-100,101,size=(33,2,3))) for _ in range(6)]
    assert new.slab_statistics(aa) == old.slab_statistics(aa)


def test_binary64_defect_difference_overflow_rejected():
    m = np.finfo(float).max
    aa = [np.full((1,1,1),v) for v in (m,0.,m,0.,m,0.)]
    for kernel in (old.slab_statistics,new.slab_statistics):
        with pytest.raises(ArithmeticError):kernel(aa)


def test_actual_dot_count_and_no_array_products(monkeypatch):
    aa = fields((3,2,2)); calls = []
    dot = old.dot
    def count(x,y):
        calls.append(1)
        return dot(x,y)
    monkeypatch.setattr(old, 'dot', count)
    reference = old.slab_statistics(aa)
    assert len(calls) == 95
    calls.clear(); monkeypatch.setattr(new, 'dot', count)
    assert new.slab_statistics(aa) == reference
    assert len(calls) == 72
    cache = new._SlabCache(aa, lambda: None)
    cache.gram([new.subtract_key(1,0)])
    assert all(type(v) is str for pair in cache.products.values() for v in pair)


def test_independent_decimal_all_matrices():
    aa = fields((3,2,2)); row = new.slab_statistics(aa)
    with localcontext() as ctx:
        ctx.prec = 80
        tuples = [tuple(Decimal.from_float(float(v)) for v in vals) for vals in zip(*(a.flat for a in aa))]
        vectors = [[] for _ in range(5)]
        pairs = [[[] for _ in range(5)] for _ in range(4)]
        for vals in tuples:
            ap,af,am,hp,hf,hm = vals
            for dest, v in zip(vectors, (hf-af,af-ap,am-af,hf-hp,hm-hf)):
                dest.append(v)
            for dest, (a,h) in zip(pairs, ((0,3),(0,4),(1,3),(1,4))):
                ra,rh = vals[a+1]-vals[a], vals[h+1]-vals[h]
                for array,v in zip(dest,(vals[h]-vals[a],rh-ra,vals[h+1]-vals[a+1],ra,rh)):
                    array.append(v)
        for matrix, vs in zip([row['gram']]+[p['moments'] for p in row['pairs']], [vectors]+pairs):
            for i in range(5):
                for j in range(5):
                    products = [a*b for a,b in zip(vs[i],vs[j])]
                    assert Decimal(matrix['value'][i][j]) == sum(products)
                    assert Decimal(matrix['absolute'][i][j]) == sum(abs(p) for p in products)


@pytest.mark.parametrize('case', ['zero', 'signed_zero', 'cancel', 'wide', 'minimum', 'near_max'])
def test_extremes_match_platform_behavior(case):
    if case in ('zero','signed_zero'):
        aa = [np.zeros((3,1,2)) for _ in range(6)]
        if case == 'signed_zero':
            for a in aa[::2]:a.flat[::2] = -0.0
    elif case == 'cancel':
        aa = [np.full((3,1,2), 2.0**50) + np.arange(6).reshape(3,1,2)*i/4 for i in range(6)]
    elif case == 'wide':
        aa = [np.ldexp(np.full((3,1,2),float(i+1)),np.array([-500,-100,0,20,100,490]).reshape(3,1,2)) for i in range(6)]
    elif case == 'minimum':
        aa = [np.full((1,1,1),i*np.nextafter(0.,1.)) for i in range(1,7)]
    else:
        # Avoid overflow in fixture construction itself.
        aa = [np.full((1,1,1),(np.finfo(float).max/8)*(i+1)) for i in range(6)]
    with np.errstate(over='ignore',invalid='ignore'):
        try: reference = old.slab_statistics(aa)
        except (ArithmeticError, ValueError) as e:
            with pytest.raises(type(e)):new.slab_statistics(aa)
        else:
            actual = new.slab_statistics(aa)
            assert actual == reference
            if case == 'minimum':assert Decimal(actual['gram']['value'][0][0]) > 0


@pytest.mark.parametrize('fault', ['nan','inf','negative','dtype','shape','empty'])
def test_invalid_input_rejected(fault):
    aa = fields((3,1,2))
    if fault == 'nan':aa[1].flat[0] = np.nan
    if fault == 'inf':aa[1].flat[0] = np.inf
    if fault == 'negative':aa[1].flat[0] = -1
    if fault == 'dtype':aa[1] = aa[1].astype('float32')
    if fault == 'shape':aa[1] = aa[1][0:1]
    if fault == 'empty':aa = [np.empty((0,1,2)) for _ in range(6)]
    with pytest.raises(ValueError):new.slab_statistics(aa)


def test_cache_does_not_survive_calls():
    first, second = fields(seed=1), fields(seed=2)
    new.slab_statistics(first)
    assert new.slab_statistics(second) == old.slab_statistics(second)
    first[0].flat[0] += 2
    assert new.slab_statistics(first) == old.slab_statistics(first)


@pytest.mark.parametrize('operation', ['vector','gram','linf','reconstruction'])
def test_cache_hit_still_checks_stop(operation):
    stop = [False]
    def check():
        if stop[0]:raise InterruptedError('stop on hit')
    cache = new._SlabCache(fields(), check); key = new.subtract_key(1,0)
    calls = dict(vector=lambda:cache.vector(key), gram=lambda:cache.gram([key]),
                 linf=lambda:cache.linf(key),
                 reconstruction=lambda:cache.reconstruction(key,(1,),(key,),np.ones((33,2,3))))
    calls[operation]();stop[0]=True
    with pytest.raises(InterruptedError):calls[operation]()


@pytest.mark.parametrize('fault', ['time','rss'])
def test_resource_stop(fault):
    guard=old.Guard(clock=lambda:1,rss=lambda:5,seconds=0 if fault=='time' else 1,rss_bytes=5 if fault=='rss' else 6)
    with pytest.raises(TimeoutError if fault=='time' else MemoryError):new.slab_statistics(fields(),guard.check)


def test_wrong_coefficient_not_hidden_by_reused_vector(monkeypatch):
    coefficients = list(new.COEFFICIENTS)
    last = list(coefficients[-1]);last[0] = (0,0,0,0,0);coefficients[-1] = tuple(last)
    monkeypatch.setattr(new,'COEFFICIENTS',tuple(coefficients))
    # FF's d was already seen as PP's mapped vector, but coefficients now differ.
    with pytest.raises(ArithmeticError,match='basis reconstruction'):
        new.slab_statistics(fields())


def test_synthetic_scan_metadata_and_independent_review(tmp_path):
    aa = fields((129,2,3)); claims=[]
    for i,a in enumerate(aa):
        p=tmp_path/f'fixture-{i}.bin';raw=a.tobytes();p.write_bytes(raw)
        claims.append(dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    data=old.scan(claims,[129,2,3],lambda r:None)
    # 仅合成测试适配：原I/O函数体不改，只将其片函数绑定到新核。
    fixture_scan=FunctionType(old.scan.__code__,dict(vars(old),slab_statistics=new.slab_statistics),
                              'fixture_scan',old.scan.__defaults__)
    replaced=fixture_scan(claims,[129,2,3],lambda r:None)
    assert data['slabs']==replaced['slabs']
    assert review(replaced)==review(data)
    replaced['slabs'][0]['pairs'][0]['reconstruction_error_square'][0]='1e40'
    with pytest.raises(ValueError):review(replaced)
