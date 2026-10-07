"""Independent scalar/Decimal80 review, without importing the diagnostic kernel."""
import argparse
from decimal import Decimal, localcontext
import hashlib
import io
import itertools
import json
from pathlib import Path

import numpy as np

E = Decimal(2)**-52
TINY = Decimal(2)**-1074
ENDS = ('previous','final')


def dec(x):
    return x if isinstance(x, Decimal) else Decimal.from_float(float(x))


def ensure(ok, label):
    if not ok:
        raise ValueError(label)


def authenticate_inputs(data):
    """Bind exported vectors and mass back to the checked source bytes independently."""
    seen=set(); endpoints={}; mass=None
    for source in data['sources']:
        path=Path(source['path'])
        ensure(str(path) not in seen, 'duplicate source')
        seen.add(str(path))
        ensure(not any(p.is_symlink() for p in (path,*path.parents)), 'source link')
        limit=17159976 if path.name=='physical_old_time_level.npz' else 8*1024**2
        ensure(path.suffix!='.dat' and source['size_bytes']<=limit, 'source scope')
        with path.open('rb') as f:raw=f.read(source['size_bytes']+1)
        ensure(len(raw)==source['size_bytes'] and hashlib.sha256(raw).hexdigest()==source['sha256'], 'source bytes')
        if path.name.endswith('_response.npz'):
            ensure(source['size_bytes']<1024**2,'response cap')
            parts=path.parts
            era='old' if 'x20-85875-matched-85889-received' in parts else 'new'
            ensure(('pair16' if era=='old' else 'pair08') in parts,'response pair')
            branch=parts[-3];end=path.name.removesuffix('_response.npz')
            key='__'.join((era,branch,end))
            ensure(key not in endpoints, 'duplicate endpoint')
            with np.load(io.BytesIO(raw),allow_pickle=False) as z:endpoints[key]=z['residual'].copy()
        elif path.name=='physical_old_time_level.npz':
            ensure(source['sha256']=='33f248d5cf35ac07fffd139e1cd99d4edefa590debf7e109f67f2dbc57adf455','mass pin')
            with np.load(io.BytesIO(raw),allow_pickle=False) as z:mass=z['cell_mass_g_cm2'].copy()
    ensure(set(endpoints)==set(data['input_vectors']) and len(endpoints)==8,'source coverage')
    ensure(mass is not None and np.array_equal(mass,np.array(data['mass'])),'source mass')
    for k,v in endpoints.items():
        ensure(v.dtype==np.dtype('float64') and v.shape==(512,) and v.tobytes()==np.array(data['input_vectors'][k],dtype='float64').tobytes(),'source vector')
    return dict(sources=len(seen),responses=8,mass_source_verified=True)


def review(data):
    ensure(len(data['mass']) == 128 and all(x > 0 for x in data['mass']), 'mass')
    ensure(set(data['quadruples']) == {'__'.join(q) for q in itertools.product(ENDS,repeat=4)}, 'quadruple coverage')
    checks=[]
    with localcontext() as context:
        context.prec=80
        m=list(map(dec,data['mass'])); total=sum(m); tau=64*512*E
        def compare(actual, exact, scale, label):
            a=dec(actual); error=abs(a-exact); bound=tau*scale
            ensure(a.is_finite() and exact.is_finite() and error <= bound, label)
            checks.append(dict(label=label,error=str(error),bound=str(bound)))
        for key,row in data['quadruples'].items():
            ho,ao,hn,an=key.split('__'); inp=data['input_vectors']
            h0=inp['old__historical__'+ho];a0=inp['old__accelerated__'+ao]
            h1=inp['new__historical__'+hn];a1=inp['new__accelerated__'+an]
            ensure(all(len(v)==512 for v in (h0,a0,h1,a1)), 'input shape')
            sub=lambda a,b:[x-y for x,y in zip(a,b)]
            cold,cnew,wh,wa=sub(h0,a0),sub(h1,a1),sub(h1,h0),sub(a1,a0)
            expected=dict(C_old=cold,C_new=cnew,W_H=wh,W_A=wa,D=sub(cnew,cold),D_alternative=sub(wh,wa))
            ensure(set(row['vectors'])==set(expected),'vector coverage')
            for name,v in expected.items():
                ensure([float(x).hex() for x in v]==[float(x).hex() for x in row['vectors'][name]], 'vector '+key+name)
            for i,(a,b) in enumerate(zip(expected['D'],expected['D_alternative'])):
                scale=sum(abs(dec(v[i])) for v in (h0,a0,h1,a1))
                ensure(abs(dec(a)-dec(b))<=32*E*scale+8*TINY,'independent identity')
            vectors={k:list(map(dec,v)) for k,v in expected.items()}
            nn={}; inn={}; absinn={}
            for name,v in vectors.items():
                cells=[sum(x*x for x in v[i*4:i*4+4]) for i in range(128)]
                squares=[sum(cells),sum(x*w for x,w in zip(cells,m))/total,max(cells)]
                nn[name]=[x.sqrt() for x in squares]
                for j,n in enumerate(nn[name]):
                    compare(row['norms'][name][j],n,abs(n),key+':'+name+':norm'+str(j))
                    compare(dec(row['norms'][name][j])**2,squares[j],squares[j],key+':'+name+':square'+str(j))
                terms=[m[i//4]*v[i]*vectors['C_old'][i] for i in range(512)]
                inn[name]=sum(terms)/total; absinn[name]=sum(abs(x) for x in terms)/total
                compare(row['mass_inner_with_C_old'][name],inn[name],absinn[name],key+':'+name+':inner')
            den=inn['C_old']
            for name in ('D','W_H','W_A'):
                actual=row['projections'][name]
                if den == 0:ensure(actual is None,'zero projection')
                else:compare(actual,inn[name]/den,2*absinn[name]/den,key+':'+name+':projection')
            if nn['C_old'][1]==0:ensure(row['mass_norm_ratio'] is None,'zero norm ratio')
            else:
                ratio=nn['C_new'][1]/nn['C_old'][1]
                compare(row['mass_norm_ratio'],ratio,2*abs(ratio),key+':ratio')
            cosden=nn['C_old'][1]*nn['C_new'][1]
            if cosden==0:ensure(row['mass_cosine'] is None,'zero cosine')
            else:compare(row['mass_cosine'],inn['C_new']/cosden,3*absinn['C_new']/cosden,key+':cosine')
    fractions=[Decimal(c['error'])/Decimal(c['bound']) for c in checks if Decimal(c['bound'])]
    return dict(passed=True,quadruples=16,scalar_checks=len(checks),maximum_fraction_of_bound=str(max(fractions)) if fractions else None,checks=checks,
                method='per-element Python subtraction, Decimal80 inner products and norms; independent of diagnostic module',strict_error_bound=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--target',type=Path,required=True);a=p.parse_args()
    raw=a.input.read_bytes();data=json.loads(raw);binding=authenticate_inputs(data);r=review(data);r['source_binding']=binding;r['input']=dict(path=str(a.input),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    with a.target.open('x') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in r.items() if k!='checks'}))
