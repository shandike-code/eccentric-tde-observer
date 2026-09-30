"""Fixed three-direction full-field prediction, preserving every frequency and cell."""
import math
import numpy as np
from operations import x20_history_operator as core


def basis_fields(aa,c):
    c=np.asarray(c,float)
    if len(aa)!=8 or c.shape!=(3,) or not np.isfinite(c).all():raise ValueError('eight fields and three finite coefficients required')
    if any(z.shape!=aa[0].shape for z in aa):raise ValueError('field shape mismatch')
    for z in aa:core.physical(z)
    b,d,h,j,a,k,x,y=aa
    # 输入锚点B和输出锚点C用相同位移系数；三个真实输入输出对对应。
    q=b+c[0]*(h-b)+c[1]*(a-b)+c[2]*(x-b)
    p=d+c[0]*(j-d)+c[1]*(k-d)+c[2]*(y-d)
    return q,p


def spectrum(z,start,geometry):
    return core.boundary_spectrum(z,geometry['mu'],geometry['weight'],geometry['width'][start:start+len(z)])


def measure_candidates(paths,shape,c,geometry,checkpoint=lambda:None):
    rows=[]
    for start,aa in core.chunks(paths,shape):
        checkpoint();q,p=basis_fields(aa,c);x,y=aa[:2];h=.5*x+.5*q;hp=.5*y+.5*p
        for z in (q,p,h,hp):
            if not np.isfinite(z).all():raise ValueError('nonfinite proposed field')
        defects=[y-x,p-q,hp-h];ff=[spectrum(z,start,geometry) for z in (x,y,q,p,h,hp)]
        rows.append(dict(first_group=start,group_count=len(x),squared_l2=[float(np.sum(z.astype(np.longdouble)**2,dtype=np.longdouble)) for z in defects],
            linf=[float(np.max(abs(z))) for z in defects],scales=[max(float(np.max(u)),float(np.max(v))) for u,v in ((x,y),(q,p),(h,hp))],
            minima=[float(z.min()) for z in (q,p,h,hp)],boundary_flux=[math.fsum(z) for z in ff],
            boundary_l1_numerator=[math.fsum(abs(ff[i+1]-ff[i])) for i in (0,2,4)],
            boundary_signed=[math.fsum(ff[i+1]-ff[i]) for i in (0,2,4)]))
    if any(min(r['minima'])<0 for r in rows):
        return dict(slabs=rows,checks=dict(full_field_nonnegative=False),passed=False,
                    status='negative_field_rejected',other_gates_evaluated=False)
    sums=[math.fsum(r['squared_l2'][i] for r in rows) for i in range(3)];peaks=[max(r['linf'][i] for r in rows) for i in range(3)]
    if sums[0]<=0 or peaks[0]<=0:raise ValueError('zero reference defect')
    flux=[math.fsum(r['boundary_flux'][i] for r in rows) for i in range(6)];boundary=[]
    for i in range(3):
        den=max(flux[2*i:2*i+2]);scale=max(r['scales'][i] for r in rows)
        if den<=0 or scale<=0:raise ValueError('zero boundary/field scale')
        boundary.append(dict(boundary_l1=math.fsum(r['boundary_l1_numerator'][i] for r in rows)/den,
            boundary_bolometric=abs(math.fsum(r['boundary_signed'][i] for r in rows))/den,residual=peaks[i]/scale))
    ratios=[math.sqrt(z/sums[0]) for z in sums];maxima=[z/peaks[0] for z in peaks]
    checks=dict(full_field_nonnegative=all(min(r['minima'])>=0 for r in rows),full_l2_benefit=ratios[1]<=.8,full_linf_nonincrease=maxima[1]<=1.0000000001,
        half_l2_nonincrease=ratios[2]<=1.0000000001,half_linf_nonincrease=maxima[2]<=1.0000000001)
    for i,name in [(1,'full'),(2,'half')]:
        checks[name+'_radiation']=boundary[i]['residual']<1e-4
        for key in ('boundary_l1','boundary_bolometric'):checks[name+'_'+key]=boundary[i][key]<1e-3 and boundary[i][key]<=boundary[0][key]*1.0000000001
    return dict(slabs=rows,fixed_scale_l2_ratios=ratios,fixed_scale_linf_ratios=maxima,boundary=boundary,checks=checks,passed=all(checks.values()))


