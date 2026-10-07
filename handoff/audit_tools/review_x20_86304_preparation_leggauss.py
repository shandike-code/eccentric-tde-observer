"""Independent standard-library receipt, exact capacity-table and moment checks."""
import hashlib,json,math,pathlib,struct,sys


def expected_ledger(n):
    rows=[]
    def add(name,count):rows.append(['leggauss:'+name,count*8])
    add('coefficients-int',n+1);add('companion-series-copy',n+1)
    if n==1:add('companion-one',1)
    else:
        add('companion-zero',n*n)
        for s in ('arange','times-two','plus-one','sqrt','inverse'):add('scale-'+s,n)
        for s in ('arange','left','right'):add('offdiag-'+s,n-1)
        for s in ('coeff-ratio','scale-ratio','product','factor'):add('last-'+s,n)
    add('eigvalsh-return',n)
    def val(prefix,length,integer):
        if integer:add(prefix+'-astype',length)
        for i in range(3,length+1):
            tag=prefix+'-step-'+str(i)
            for suffix in ('left-product','left-subtract'):add(tag+'-'+suffix,1 if i==3 else n)
            for suffix in ('right-product','right-scale','right-add'):add(tag+'-'+suffix,n)
        add(prefix+'-final-product',n);add(prefix+'-final-add',n)
    val('dy',n+1,True)
    add('derivative-copy-int',n+1);add('derivative-astype',n+1);add('derivative-empty',n)
    val('df',n,False);add('newton-ratio',n);val('fm',n,True)
    for name in ('fm-abs','df-abs','weight-product','weight-inverse','weight-sym-add','weight-sym-divide','node-sym-subtract','node-sym-divide'):add(name,n)
    return rows


def review(doc):
    assert set(doc)=={'schema','numpy','cases','elapsed_seconds','private_workspace_metered','configuration_integrated','production_authorized'}
    assert doc['schema']=='leggauss-explicit-arrays-v1' and doc['numpy']=='2.5.2'
    for key in ('private_workspace_metered','configuration_integrated','production_authorized'):assert doc[key] is False
    assert type(doc['elapsed_seconds']) in (int,float) and math.isfinite(doc['elapsed_seconds']) and doc['elapsed_seconds']>=0
    assert len(doc['cases'])==16
    largest=0.;summary=[]
    for n,case in enumerate(doc['cases'],1):
        assert set(case)=={'degree','arrays','ledger','total','checks'}
        assert type(case['degree']) is int and case['degree']==n
        rows=expected_ledger(n)
        assert all(type(r) is list and len(r)==2 and type(r[0]) is str and type(r[1]) is int for r in case['ledger'])
        assert case['ledger']==rows
        assert type(case['total']) is int and case['total']==sum(r[1] for r in rows)
        checks=len(rows)+8+4*(n>1)+max(n-1,0)+4*max(n-2,0)
        assert type(case['checks']) is int and case['checks']==checks
        assert len(case['arrays'])==2
        values=[]
        for a in case['arrays']:
            assert set(a)=={'shape','dtype','hex','sha256'} and a['dtype']=='<f8'
            assert a['shape']==[n] and type(a['shape'][0]) is int
            raw=bytes.fromhex(a['hex']);assert len(raw)==8*n
            assert hashlib.sha256(raw).hexdigest()==a['sha256']
            v=struct.unpack('<'+'d'*n,raw);assert all(math.isfinite(x) for x in v);values.append(v)
        x,w=values
        assert all(-1<t<1 for t in x) and all(a<b for a,b in zip(x,x[1:]))
        assert all(t>0 for t in w)
        # Legendre 求积解析多项式矩；固定绝对门不随观察结果调节。
        errors=[abs(math.fsum(wi*xi**k for xi,wi in zip(x,w))-(0. if k%2 else 2./(k+1))) for k in range(2*n)]
        assert max(errors)<=2e-14
        largest=max(largest,max(errors));summary.append(dict(degree=n,reservations=len(rows),capacity=case['total'],checks=checks))
    return dict(verified=True,moment_max_abs_error=largest,cases=summary,private_workspace_metered=False,configuration_integrated=False)

if __name__=='__main__':
    result=review(json.loads(pathlib.Path(sys.argv[1]).read_text()))
    with pathlib.Path(sys.argv[2]).open('x') as f:json.dump(result,f,indent=2)
