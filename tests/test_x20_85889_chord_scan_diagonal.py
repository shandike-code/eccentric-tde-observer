from decimal import Decimal, localcontext
import numpy as np
import pytest
from operations import x20_85889_chord_scan as old
from operations import x20_85889_chord_scan_diagonal as new
from handoff.audit_tools.review_x20_85889_chord_scan import review


def fields(shape=(33, 2, 3), seed=601):
    rng = np.random.default_rng(seed)
    return [rng.integers(1, 200, size=shape).astype('<f8') / 8 for _ in range(6)]


@pytest.mark.parametrize('shape', [(1,1,1), (31,2,3), (32,2,3), (33,2,3), (129,2,3)])
@pytest.mark.parametrize('layout', ['C', 'F', 'strided', 'transpose', 'offset'])
def test_all_numeric_fields_equal_and_inputs_unchanged(shape, layout):
    aa = fields(shape)
    if layout == 'F':
        aa = [np.asfortranarray(a) for a in aa]
    if layout == 'strided':
        aa = [a[:, :, ::-1] for a in aa]
    if layout == 'transpose':aa = [a.transpose(2,0,1) for a in aa]
    if layout == 'offset':aa = [np.pad(a, ((0,0),(0,0),(1,1)))[:,:,1:-1] for a in aa]
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


def test_actual_calls_and_no_array_products(monkeypatch):
    from operations import x20_85889_chord_scan_reuse as reuse
    aa = fields((3,2,2)); reference = reuse.slab_statistics(aa)
    calls = dict(dot=0, square=0, sum=0)
    dot, square, total = new.dot, new.reconstruction_square, np.sum
    def counted_dot(x,y):
        calls['dot'] += 1
        return dot(x,y)
    def counted_square(x):
        calls['square'] += 1
        return square(x)
    def counted_sum(*args, **kwargs):
        calls['sum'] += 1
        return total(*args, **kwargs)
    monkeypatch.setattr(new, 'dot', counted_dot)
    monkeypatch.setattr(new, 'reconstruction_square', counted_square)
    monkeypatch.setattr(np, 'sum', counted_sum)
    assert new.slab_statistics(aa) == reference
    assert calls == dict(dot=42, square=30, sum=114)
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


def test_synthetic_explicit_wiring_and_independent_review(tmp_path):
    from handoff.audit_tools.exercise_x20_86191_diagonal import exercise
    assert exercise(tmp_path/'tiny')['independent_reviews_identical']


@pytest.mark.parametrize('layout', ['C','F','strided'])
@pytest.mark.parametrize('case', ['normal','zero','minimum','product_overflow','sum_overflow','nan','inf'])
def test_helper_return_warning_exception_semantics(layout, case):
    import warnings
    lim = np.finfo(np.longdouble)
    a = np.arange(12, dtype=np.longdouble).reshape(3,2,2)-6
    if case == 'zero':a[:] = -np.longdouble(0)
    if case == 'minimum':a[:] = np.longdouble(np.nextafter(0.,1.))
    if case == 'product_overflow':a[:] = lim.max
    if case == 'sum_overflow':a[:] = np.sqrt(lim.max)/2
    if case == 'nan':a[:] = np.nan
    if case == 'inf':a[:] = np.inf
    if layout == 'F':a = np.asfortranarray(a)
    if layout == 'strided':a = a[:,:,::-1]
    outcomes=[]
    for call in (lambda:old.dot(a,a)[0],lambda:new.reconstruction_square(a)):
        with warnings.catch_warnings(record=True) as messages, np.errstate(over='warn',invalid='warn'):
            warnings.simplefilter('always')
            try: value = old.decimal_text(call())
            except (ArithmeticError,ValueError) as e:outcome=('error',type(e),str(e))
            else:outcome=('value',value)
        outcomes.append((outcome, {m.category for m in messages}))
    # 原sum溢出可能警告两次，新版一次；类别和拒绝语义必须相同。
    assert outcomes[0] == outcomes[1]


def test_frozen_square_body_only_declared_change():
    import ast
    from pathlib import Path
    from operations import x20_85889_chord_scan_square as square
    tree = ast.parse(Path(new.__file__).read_text())
    reference = ast.parse(Path(square.__file__).read_text())
    helper = next(n for n in reference.body if isinstance(n, ast.FunctionDef) and n.name=='reconstruction_square')
    tree.body = [helper if isinstance(n, ast.ImportFrom) and n.module=='operations.x20_85889_chord_scan_square' else n for n in tree.body]
    tree.body[0] = reference.body[0]
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    oldklass = next(n for n in reference.body if isinstance(n, ast.ClassDef))
    gram = next(n for n in oldklass.body if isinstance(n, ast.FunctionDef) and n.name=='gram')
    klass.body = [gram if isinstance(n, ast.FunctionDef) and n.name=='gram' else n for n in klass.body]
    assert ast.dump(tree) == ast.dump(reference)
    assert new.reconstruction_square is square.reconstruction_square


@pytest.mark.parametrize('mode', ['warn','raise','ignore'])
def test_sum_overflow_inherited_error_policy(mode):
    import warnings
    delta = np.full((16,2,2), np.sqrt(np.finfo(np.longdouble).max)/2, dtype=np.longdouble)
    outcomes=[]
    for helper in (lambda:old.dot(delta,delta)[0],lambda:new.reconstruction_square(delta)):
        with warnings.catch_warnings(record=True) as messages, np.errstate(over=mode):
            warnings.simplefilter('always')
            try:old.decimal_text(helper())
            except (ArithmeticError,ValueError) as e:outcome=type(e)
            else:raise AssertionError('nonfinite reduction accepted')
        outcomes.append((outcome,{m.category for m in messages}))
    assert outcomes[0]==outcomes[1]


def test_helper_decimal_oracle_and_readonly_input():
    with localcontext() as ctx:
        ctx.prec=80
        a=np.array([-7,-1,0,3,11],dtype=np.longdouble)/8
        a.flags.writeable=False
        before=[old.decimal_text(x) for x in a]
        expected=sum((Decimal(v)/8)**2 for v in (-7,-1,0,3,11))
        assert Decimal(old.decimal_text(new.reconstruction_square(a)))==expected
        assert [old.decimal_text(x) for x in a]==before
        assert not a.flags.writeable


def test_complete_serialized_structure_and_reuse_equivalence():
    import json
    from operations import x20_85889_chord_scan_reuse as reuse
    aa=fields()
    assert json.dumps(new.slab_statistics(aa))==json.dumps(reuse.slab_statistics(aa))


def test_equal_values_distinct_keys_and_ordered_products(monkeypatch):
    aa=[np.ones((2,2,2)) for _ in range(6)]
    cache=new._SlabCache(aa,lambda:None)
    k,l=new.subtract_key(1,0),new.subtract_key(3,2)
    calls=[]; dot=new.dot
    def record(x,y):
        calls.append((x,y));return dot(x,y)
    monkeypatch.setattr(new,'dot',record)
    cache.gram([k,l]); cache.gram([l,k])
    assert len(calls)==2
    assert calls[0][0] is cache.vector(k) and calls[0][1] is cache.vector(l)
    assert calls[1][0] is cache.vector(l) and calls[1][1] is cache.vector(k)
    assert (k,l) in cache.products and (l,k) in cache.products


@pytest.mark.parametrize('failure',['helper','format','second_vector'])
def test_failed_diagonal_never_cached(monkeypatch,failure):
    cache=new._SlabCache(fields(),lambda:None); k=new.subtract_key(1,0)
    cache.vector(k)
    def fail(*args):raise InterruptedError('injected failure')
    if failure=='helper':monkeypatch.setattr(new,'reconstruction_square',fail)
    if failure=='format':monkeypatch.setattr(new,'decimal_text',fail)
    if failure=='second_vector':
        vector=cache.vector; calls=[]
        def get(key):
            calls.append(key)
            if len(calls)==2:fail()
            return vector(key)
        monkeypatch.setattr(cache,'vector',get)
    with pytest.raises(InterruptedError):cache.gram([k])
    assert cache.products=={}


def test_original_check_sequence_and_stop_between_vectors():
    from operations import x20_85889_chord_scan_square as square
    k=new.subtract_key(1,0)
    traces=[]
    for module in (square,new):
        trace=[]; cache=module._SlabCache(fields(),lambda:trace.append('check'))
        vector=cache.vector
        def get(key):
            trace.append(('vector',key));return vector(key)
        cache.vector=get
        cache.gram([k]); cache.gram([k]);traces.append(trace)
    assert traces[0]==traces[1]
    for module in (square,new):
        stop=[False]; visits=[]
        def check():
            if stop[0]:raise InterruptedError('second vector check')
        cache=module._SlabCache(fields(),check);cache.vector(k)
        vector=cache.vector
        def get(key):
            visits.append(key)
            value=vector(key)
            stop[0]=True
            return value
        cache.vector=get
        with pytest.raises(InterruptedError,match='second vector check'):cache.gram([k])
        assert visits==[k,k] and not cache.products


def test_two_serializations_and_shared_scalar(monkeypatch):
    cache=new._SlabCache(fields(),lambda:None);seen=[];format_value=new.decimal_text
    def record(v):seen.append(v);return format_value(v)
    monkeypatch.setattr(new,'decimal_text',record)
    cache.gram([new.subtract_key(1,0)])
    assert len(seen)==2 and seen[0] is seen[1]


def test_full_summary_types_order_zeros_against_all_references():
    import json
    from operations import x20_85889_chord_scan_square as square
    from operations import x20_85889_chord_scan_reuse as reuse
    aa=fields()
    for a in aa:a.flat[:2]=[-0.,0.];a.flags.writeable=False
    actual=json.dumps(new.slab_statistics(aa))
    for module in (old,reuse,square):assert actual==json.dumps(module.slab_statistics(aa))


def test_matrix_and_reconstruction_square_counts_separately(monkeypatch):
    count=dict(matrix=0,reconstruction=0); active=[]
    gram,reconstruction,helper=new._SlabCache.gram,new._SlabCache.reconstruction,new.reconstruction_square
    def g(self,keys):
        active.append('matrix')
        try:return gram(self,keys)
        finally:active.pop()
    def r(self,*args):
        active.append('reconstruction')
        try:return reconstruction(self,*args)
        finally:active.pop()
    def h(x):count[active[-1]]+=1;return helper(x)
    monkeypatch.setattr(new._SlabCache,'gram',g)
    monkeypatch.setattr(new._SlabCache,'reconstruction',r)
    monkeypatch.setattr(new,'reconstruction_square',h)
    new.slab_statistics(fields())
    assert count==dict(matrix=15,reconstruction=15)


def test_cooperative_signal_stop():
    calls=[0]
    def check():
        calls[0]+=1
        if calls[0]==30:raise InterruptedError('synthetic signal')
    with pytest.raises(InterruptedError):new.slab_statistics(fields(),check)
    assert calls[0]==30


def test_layout_warning_audit_both_dot_outputs():
    from handoff.audit_tools.exercise_x20_86191_diagonal import layout_and_warning_audit
    report=layout_and_warning_audit()
    assert len(report['records'])==135
    rows=[r for r in report['records'] if r['case']=='sum_overflow' and r['mode']=='warn']
    assert len(rows)==5
    for r in rows:
        assert len(r['original']['warnings'])==2
        assert len(r['shared']['warnings'])==1


@pytest.mark.parametrize('layout',['C','F','transpose','reverse','offset'])
def test_actual_sum_input_layouts_and_both_results(monkeypatch,layout):
    # 仅测试钩子：捕捉原dot和冻结辅助真正交给sum的数组，不改变归约。
    a=np.ldexp(np.arange(24,dtype=np.longdouble).reshape(4,2,3)-12,np.arange(24).reshape(4,2,3)*40-480)
    if layout=='F':a=np.asfortranarray(a)
    if layout=='transpose':a=a.transpose(2,0,1)
    if layout=='reverse':a=a[:,:,::-1]
    if layout=='offset':a=np.pad(a,((0,0),(0,0),(1,1)))[:,:,1:-1]
    a.flags.writeable=False
    observed=[];total=np.sum
    def capture(x,*args,**kwargs):
        observed.append((x.dtype,x.shape,x.strides,x.flags.c_contiguous,x.flags.f_contiguous,x.flags.aligned,
                         tuple(old.decimal_text(v) for v in x.flat)))
        return total(x,*args,**kwargs)
    monkeypatch.setattr(np,'sum',capture)
    signed,absolute=old.dot(a,a); shared=new.reconstruction_square(a)
    assert len(observed)==3 and observed[0]==observed[1]==observed[2]
    assert old.decimal_text(signed)==old.decimal_text(absolute)==old.decimal_text(shared)


def test_exact_declared_gram_source_change():
    import inspect
    from operations import x20_85889_chord_scan_square as square
    expected=inspect.getsource(square._SlabCache.gram).replace(
        '                    a, b = dot(self.vector(keys[i]), self.vector(keys[j]))',
        '''                    left = self.vector(keys[i])
                    right = self.vector(keys[j])
                    # 两次取数与停止检查保留；资格只认有序表达式键相同。
                    if keys[i] == keys[j]:
                        a = b = reconstruction_square(left)
                    else:
                        a, b = dot(left, right)''')
    assert inspect.getsource(new._SlabCache.gram)==expected
