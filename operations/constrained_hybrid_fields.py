"""Bounded-memory full-field line constraints and independent original-map audit."""
from contextlib import ExitStack
from pathlib import Path
import numpy as np

BLOCKS=(14,47)
CONTROL={'step_safety':.9,'maximum_fraction':1.,'minimum_l2_gain':.001,
         'linf_roundoff':1e-10,'affinity_limit':1e-6,'radiation_limit':1e-4,'boundary_limit':1e-3}


def physical(a):
    if not np.isfinite(a).all() or np.any(a<0):raise ValueError('nonfinite or negative intensity')


def chunks(paths,shape):
    with ExitStack() as stack:
        files=[stack.enter_context(Path(p).open('rb')) for p in paths]
        for start in range(0,shape[0],32):
            groups=min(32,shape[0]-start);n=groups*int(np.prod(shape[1:]))
            arrays=[]
            for f in files:
                a=np.fromfile(f,dtype='<f8',count=n)
                if a.size!=n:raise ValueError('truncated field')
                a=a.reshape(groups,*shape[1:]);physical(a);arrays.append(a)
            yield start,arrays
        if any(f.read(1) for f in files):raise ValueError('unexpected field tail')


def feasible_upper(raw,change,maximum):
    """Intersect |r+t*d|<=M with t in [0,1]; no intensity clipping."""
    if maximum<=0 or np.max(abs(raw))>maximum*(1+2e-15):raise ValueError('invalid reference Linf')
    upper=1.
    positive=change>0;negative=change<0
    if positive.any():upper=min(upper,float(np.min((maximum-raw[positive])/change[positive])))
    if negative.any():upper=min(upper,float(np.min((maximum+raw[negative])/(-change[negative]))))
    if upper<0:raise ArithmeticError('infeasible zero endpoint')
    return upper


def choose_fraction(s0,dd,rd,upper):
    if s0<=0 or dd<=0:raise ValueError('zero scale or direction')
    optimum=-rd/dd
    if optimum<=0 or upper<=0:return {'fraction':0.,'feasible':False,'reason':'no nonzero descent interval'}
    # 先取全场Linf可行区间内的L2二次最优，再留固定10%步长裕量。
    fraction=CONTROL['step_safety']*min(optimum,upper,CONTROL['maximum_fraction'])
    square=s0+2*fraction*rd+fraction*fraction*dd
    if square<0:raise ArithmeticError('negative predicted squared norm')
    ratio=float(np.sqrt(square/s0))
    return {'fraction':fraction,'feasible':ratio<=1-CONTROL['minimum_l2_gain'],
            'predicted_l2_ratio':ratio,'unconstrained_fraction':optimum,'linf_upper':upper}


def scan(paths,shape,flux,original_row):
    s0=dd=rd=maximum=unchanged_scale=0.;surfaces=[[] for _ in paths]
    for start,(x,y,u,v) in chunks(paths,shape):
        if start//128 not in BLOCKS:
            if not np.array_equal(x,u):raise ValueError('undeclared block changed')
            unchanged_scale=max(unchanged_scale,float(np.max(x)))
        raw=y-x;d=(v-u)-raw
        s0+=float(np.sum(raw*raw));dd+=float(np.sum(d*d));rd+=float(np.sum(raw*d))
        maximum=max(maximum,float(np.max(abs(raw))))
        for store,a in zip(surfaces,(x,y,u,v)):store.append(flux(a,start))
    upper=1.
    for _,(x,y,u,v) in chunks(paths,shape):
        raw=y-x;upper=min(upper,feasible_upper(raw,(v-u)-raw,maximum))
    choice=choose_fraction(s0,dd,rd,upper)
    choice.update(original_defect_l2=float(np.sqrt(s0)),original_defect_linf=maximum,
                  squared_direction_l2=dd,original_dot_direction=rd)
    if not choice['fraction']:return choice
    fs=[np.concatenate(values) for values in surfaces];t=choice['fraction']
    checks={};predictions={}
    for label,a in [('selected',t),('half',t/2)]:
        fin=(1-a)*fs[0]+a*fs[2];fout=(1-a)*fs[1]+a*fs[3]
        denominator=max(float(np.sum(abs(fin))),float(np.sum(abs(fout))))
        bol=max(abs(float(fin.sum())),abs(float(fout.sum())))
        if denominator<=0 or bol<=0 or unchanged_scale<=0:raise ValueError('zero boundary/field scale')
        l1=float(np.sum(abs(fout-fin)))/denominator
        total=abs(float(fout.sum()-fin.sum()))/bol
        predictions[label]={'boundary_l1':l1,'boundary_bolometric':total,
            'radiation_upper_bound':maximum/unchanged_scale}
        for key,value in [('boundary_l1',l1),('boundary_bolometric',total)]:
            checks[label+'_'+key]=(value<CONTROL['boundary_limit'] and value<=original_row[key]*(1+CONTROL['linf_roundoff']))
        checks[label+'_radiation']=maximum/unchanged_scale<CONTROL['radiation_limit']
    choice.update(boundary_predictions=predictions,checks=checks,
                  feasible=choice['feasible'] and all(checks.values()),prediction_is_not_validation=True)
    return choice


def write_convex(source,endpoint,destination,fraction,shape):
    if not 0<fraction<=1:raise ValueError('undeclared nonconvex fraction')
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    tmp=destination.with_suffix('.tmp')
    with tmp.open('wb') as f:
        for start,(x,u) in chunks([source,endpoint],shape):
            if start//128 in BLOCKS:value=u if fraction==1 else (1-fraction)*x+fraction*u
            else:
                if not np.array_equal(x,u):raise ValueError('unselected block differs')
                value=x
            physical(value);value.tofile(f)
    if tmp.stat().st_size!=int(np.prod(shape))*8:raise ValueError('candidate byte count')
    tmp.replace(destination)


def full_endpoint(source,replacements,destination,shape):
    """Read only selected saved cores; stream all untouched original groups."""
    destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    cores={i:np.load(p,allow_pickle=False) for i,p in replacements.items()}
    if set(cores)!=set(BLOCKS):raise ValueError('wrong block inventory')
    for value in cores.values():
        if value.shape!=(128,*shape[1:]):raise ValueError('core shape')
        physical(value)
    tmp=destination.with_suffix('.tmp')
    with tmp.open('wb') as f:
        for start,(x,) in chunks([source],shape):
            index=start//128
            value=cores[index][start%128:start%128+len(x)] if index in cores else x
            value.tofile(f)
    tmp.replace(destination)


def validate(paths,shape):
    sums=np.zeros(4);peaks=np.zeros(4);rows=[]
    for start,(x,y,u,v,h,k) in chunks(paths,shape):
        if start//128 not in BLOCKS:
            if not (np.array_equal(x,u) and np.array_equal(x,h)):raise ValueError('unselected input changed')
        elif not np.array_equal(h,.5*x+.5*u):raise ValueError('half identity')
        a=y-x;b=v-u;c=k-h;d=c-.5*a-.5*b
        ds=[a,b,c,d];ss=np.array([float(np.sum(z*z)) for z in ds]);pp=np.array([float(np.max(abs(z))) for z in ds])
        sums+=ss;peaks=np.maximum(peaks,pp)
        rows.append({'first_group':start,'group_count':len(x),'squared_l2':ss.tolist(),'linf':pp.tolist()})
    if sums[0]<=0 or peaks[0]<=0:raise ValueError('zero original defect')
    return {'fixed_scale_l2_ratios':np.sqrt(sums/sums[0]).tolist(),
            'fixed_scale_linf_ratios':(peaks/peaks[0]).tolist(),'slabs':rows,'all_groups_evaluated':shape[0]}
