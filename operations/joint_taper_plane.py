"""Convex two-direction screening with whole-field Linf constraint generation."""
import math
import numpy as np
from operations.constrained_hybrid_fields import chunks,physical
from operations.scan_step21_positive_plane import intersect
CONTROL={'maximum_passes':6,'maximum_cuts':4096,'retreat':.99,'minimum_l2_gain':.2,'linf_roundoff':1e-10}
SELECTED=(23,24,25,47,48,49)


def coefficients(uv):
    uv=np.asarray(uv,float)
    if uv.shape!=(2,) or not np.isfinite(uv).all() or np.any(uv<0) or uv.sum()>1:raise ValueError('outside convex triangle')
    return np.array([1-uv.sum(),uv[0],uv[1]])


def solve(gram,rhs,cuts):
    g,b=np.asarray(gram,float),np.asarray(rhs,float)
    if g.shape!=(2,2) or b.shape!=(2,) or not np.isfinite(g).all() or not np.isfinite(b).all():raise ValueError('invalid Gram')
    if not np.allclose(g,g.T,rtol=0,atol=0):raise ValueError('nonsymmetric Gram')
    eig=np.linalg.eigvalsh(g)
    if eig[-1]<=0 or eig[0]<=1e-12*eig[-1]:return dict(resolved=False,reason='degenerate_or_indefinite_Gram')
    scale=float(np.max(abs(g)));g=g/scale;b=b/scale
    poly=np.array([[0.,0.],[1.,0.],[0.,1.]])
    for cut in cuts:poly=intersect(poly,cut['row'],cut['lower'])
    candidates=[np.zeros(2)]
    u=np.linalg.solve(g,-b)
    if np.all(u>=0) and u.sum()<=1 and all(np.dot(c['row'],u)>=c['lower'] for c in cuts):candidates.append(u)
    for a,z in zip(poly,np.roll(poly,-1,axis=0)):
        direction=z-a;den=float(direction@g@direction)
        t=min(1.,max(0.,-float(direction@(g@a+b))/den)) if den>0 else 0.
        p=a+t*direction
        if np.all(p>=0) and p.sum()<=1 and all(np.dot(c['row'],p)>=c['lower']-1e-12 for c in cuts):candidates.append(p)
    obj=[float(u@g@u+2*b@u) for u in candidates];raw=candidates[int(np.argmin(obj))];uv=CONTROL['retreat']*raw
    coefficients(uv)
    return dict(resolved=True,raw_uv=raw.tolist(),uv=uv.tolist(),polygon=poly.tolist(),retreat=CONTROL['retreat'])


def gram_scan(paths,shape,flux,checkpoint=lambda:None):
    rows=[];spectra=[[] for _ in range(6)]
    for start,arr in chunks(paths,shape):
        checkpoint();x,y,q,v,z,k=arr;r=y-x;d=[(v-q)-r,(k-z)-r]
        g=[[float(np.sum(a*b)) for b in d] for a in d];b=[float(np.sum(a*r)) for a in d]
        ss=float(np.sum(r*r));m=float(np.max(abs(r)))
        if not np.isfinite([*np.ravel(g),*b,ss,m]).all():raise ValueError('nonfinite Gram reduction')
        rows.append(dict(start=start,stop=start+len(x),gram=g,rhs=b,s0=ss,maximum=m))
        for j,a in enumerate(arr):spectra[j].extend(map(float,flux(a,start)))
    g=[[math.fsum(r['gram'][i][j] for r in rows) for j in range(2)] for i in range(2)]
    b=[math.fsum(r['rhs'][i] for r in rows) for i in range(2)];s0=math.fsum(r['s0'] for r in rows);m=max(r['maximum'] for r in rows)
    if s0<=0 or m<=0:raise ValueError('zero reference defect')
    f=np.asarray(spectra)
    if f.shape!=(6,shape[0]) or not np.isfinite(f).all():raise ValueError('invalid fluxes')
    return dict(gram=g,rhs=b,s0=s0,maximum=m,slabs=rows,fluxes=spectra)


def cut_at(r,d1,d2,sign,index,maximum):
    vals=[float(v) for v in (r,d1,d2)]
    if sign not in (-1,1) or not np.isfinite(vals+[maximum]).all() or maximum<=0 or abs(r)>maximum:raise ValueError('invalid witness')
    return dict(index=list(map(int,index)),sign=sign,values_hex=[v.hex() for v in vals],maximum_hex=float(maximum).hex(),row=[-sign*d1/maximum,-sign*d2/maximum],lower=sign*r/maximum-1)


def mix(arr,weights):
    # 完全相同的三输入直接复制，避免对未改次正规尾反复乘系数造成舍入变化。
    if np.array_equal(arr[0],arr[1]) and np.array_equal(arr[0],arr[2]):return arr[0]
    return sum(w*a for w,a in zip(weights,arr))


def inspect(paths,shape,uv,gram,original,*,selected=SELECTED,checkpoint=lambda:None):
    weights=coefficients(uv);M=gram['maximum'];rows=[];cuts=[]
    for start,(x,y,q,v,z,k) in chunks(paths,shape):
        checkpoint()
        if start//128 not in selected and not (np.array_equal(q,x) and np.array_equal(z,x)):raise ValueError('unselected inputs changed')
        u=mix([x,q,z],weights);tu=mix([y,v,k],weights);physical(u);physical(tu)
        r=y-x;d1=(v-q)-r;d2=(k-z)-r;actual=tu-u;prediction=r+uv[0]*d1+uv[1]*d2
        for sign in (-1,1):
            ix=np.unravel_index(np.argmax(sign*actual),actual.shape)
            if sign*actual[ix]>M*(1+CONTROL['linf_roundoff']):cuts.append(cut_at(r[ix],d1[ix],d2[ix],sign,(start+ix[0],*ix[1:]),M))
        row=dict(start=start,stop=start+len(x),squared_l2=float(np.sum(actual*actual)),maximum=float(np.max(abs(actual))),minimum_input=float(u.min()),minimum_output=float(tu.min()),field_scale=max(float(u.max()),float(tu.max())),affine_roundoff=float(np.max(abs(actual-prediction))))
        if not np.isfinite(list(row.values())).all():raise ValueError('nonfinite candidate reduction')
        rows.append(row)
    ss=math.fsum(r['squared_l2'] for r in rows);maximum=max(r['maximum'] for r in rows);scale=max(r['field_scale'] for r in rows)
    l2=math.sqrt(ss/gram['s0']);linf=maximum/M
    quadratic=gram['s0']+2*np.dot(gram['rhs'],uv)+np.asarray(uv)@np.asarray(gram['gram'])@np.asarray(uv)
    if quadratic<0:raise ArithmeticError('negative predicted norm')
    ratio=math.sqrt(quadratic/gram['s0'])
    checks=dict(nonzero=bool(np.any(uv)),convex=True,full_l2_cost=l2<=.8,quadratic_l2_cost=ratio<=.8,linf_nonincrease=linf<=1+CONTROL['linf_roundoff'],strict_radiation=scale>0 and maximum/scale<1e-4,affine_roundoff=max(r['affine_roundoff'] for r in rows)/M<1e-7)
    f=np.asarray(gram['fluxes']);boundary={}
    for label,t in [('full',1.),('half',.5)]:
        w=coefficients(t*np.asarray(uv));fi=sum(w[j]*f[2*j] for j in range(3));fo=sum(w[j]*f[2*j+1] for j in range(3))
        den=max(math.fsum(abs(v) for v in fi),math.fsum(abs(v) for v in fo));bi,bo=math.fsum(fi),math.fsum(fo);bden=max(abs(bi),abs(bo))
        if den<=0 or bden<=0:raise ValueError('undefined boundary normalization')
        vals=dict(boundary_l1=math.fsum(abs(v) for v in fo-fi)/den,boundary_bolometric=abs(bo-bi)/bden);boundary[label]=vals
        for name,value in vals.items():checks[label+'_'+name]=value<1e-3 and value<=original[name]*(1+CONTROL['linf_roundoff'])
    return dict(uv=list(map(float,uv)),weights=weights.tolist(),slabs=rows,l2_ratio=l2,quadratic_l2_ratio=ratio,linf_ratio=linf,checks=checks,boundary=boundary,cuts=cuts)


def search(gram,evaluate,save=lambda result:None):
    cuts=[];keys=set();rounds=[];eligible=False;reason='constraint_budget_exhausted'
    # 第1遍为Gram；剩余最多5遍逐点约束核验。仅真实扫描通过才能返回eligible。
    for n in range(1,CONTROL['maximum_passes']):
        solution=solve(gram['gram'],gram['rhs'],cuts)
        if not solution['resolved']:reason=solution['reason'];break
        result=evaluate(solution['uv']);rounds.append(dict(solution=solution,result=result));save(dict(rounds=rounds,cuts=cuts))
        if all(result['checks'].values()):eligible=True;reason='all_registered_predictive_gates_passed';break
        if not result['cuts']:reason='cost_or_boundary_gate_failed';break
        added=0
        for c in result['cuts']:
            key=(tuple(c['index']),c['sign'])
            if key not in keys:keys.add(key);cuts.append(c);added+=1
        if len(cuts)>CONTROL['maximum_cuts']:reason='cut_budget_exhausted';break
        if not added:reason='no_new_constraints';break
    return dict(rounds=rounds,cuts=cuts,eligible_for_independent_review=eligible,reason=reason,passes=1+len(rounds),full_constrained_optimum_proven=False,actual_map_performed=False,candidate_written=False,accepted_material_step=False)
