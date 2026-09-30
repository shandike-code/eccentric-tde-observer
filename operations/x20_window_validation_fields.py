"""Write the single audited candidate and compare true outputs to its prediction."""
import math
from pathlib import Path
import numpy as np
from operations.x20_window_fields import basis_fields
from operations import x20_history_operator as core


def write_candidates(paths,shape,coefficients,full,half,checkpoint=lambda:None):
    full,half=Path(full),Path(half);temp=[p.with_suffix('.tmp') for p in (full,half)]
    if len(set((full,half,*temp)))!=4 or any(p.exists() for p in (full,half,*temp)):raise FileExistsError('immutable candidate paths')
    with temp[0].open('xb') as f,temp[1].open('xb') as h:
        for _,aa in core.chunks(paths,shape):
            checkpoint();q,_=basis_fields(aa,coefficients);m=.5*aa[0]+.5*q
            core.physical(q);core.physical(m);q.tofile(f);m.tofile(h)
    if any(p.stat().st_size!=math.prod(shape)*8 for p in temp):raise ValueError('candidate size')
    for a,b in zip(temp,(full,half)):a.replace(b)


def prediction_error(paths,shape,coefficients,checkpoint=lambda:None):
    if len(paths)!=10:raise ValueError('eight source fields plus full/half true outputs required')
    rows=[]
    for first,aa in core.chunks(paths,shape):
        checkpoint();_,p=basis_fields(aa[:8],coefficients);half_p=.5*aa[1]+.5*p
        for z in aa[8:]:core.physical(z)
        residuals=[aa[1]-aa[0],aa[8]-p,aa[9]-half_p]
        rows.append(dict(first_group=first,group_count=len(p),
            squared_l2=[float(np.sum(z.astype(np.longdouble)**2,dtype=np.longdouble)) for z in residuals],
            linf=[float(np.max(abs(z))) for z in residuals]))
    sq=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(3)]
    peak=[max(r['linf'][i] for r in rows) for i in range(3)]
    if sq[0]<=0 or peak[0]<=0:raise ValueError('zero normalization')
    ratios=[math.sqrt(x/sq[0]) for x in sq];maxima=[x/peak[0] for x in peak]
    checks={name+'_'+norm:v<=1e-6 for name,i in [('full',1),('half',2)] for norm,v in [('l2_affinity',ratios[i]),('linf_affinity',maxima[i])]}
    return dict(slabs=rows,l2_ratios=ratios,linf_ratios=maxima,checks=checks,passed=all(checks.values()))
