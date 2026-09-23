"""Exact P0 collision integrals over a moving finite-frequency boundary."""
import numpy as np
from eccentric_tde_observer.mixed_frame_frequency import (
    _piecewise_constant_overlap_integral_columns,
)


def boundary_integrals(lab_intensity, lab_edge, comoving_edge, doppler,
                       absorption, emission, scattering, mean, boundary):
    """Return signed integrals from boundary to D*boundary, per ray and depth.

    采用冻结的分段常数 I_lab、chi_0、eta_0；只积分两个频带的差集。
    I_0 dnu_0 = D^4 I_lab dnu_lab，不能把组平均的乘积当连续光谱。
    返回吸收、热发射、散射对物质加热的贡献，尚未乘角权/2pi。
    """
    lab=np.asarray(lab_intensity);le=np.asarray(lab_edge);ce=np.asarray(comoving_edge)
    d=np.asarray(doppler);fields=[np.asarray(v) for v in (absorption,emission,scattering,mean)]
    if lab.ndim!=3 or d.shape!=lab.shape[1:] or le.size!=lab.shape[0]+1:
        raise ValueError('radiation axes mismatch')
    if any(v.shape!=(len(ce)-1,lab.shape[2]) for v in fields):
        raise ValueError('coefficient axes mismatch')
    if (not all(np.isfinite(v).all() for v in [lab,le,ce,d,*fields])
        or np.any(lab<0) or any(np.any(v<0) for v in fields)
        or np.any(d<=0) or np.any(np.diff(le)<=0) or np.any(np.diff(ce)<=0)
        or le[0]<=0 or ce[0]<=0 or not np.isfinite(boundary) or boundary<=0):
        raise ValueError('invalid finite positive frequency/radiation domain')
    lo=np.minimum(boundary,d*boundary).ravel();hi=np.maximum(boundary,d*boundary).ravel()
    factors=d.ravel();sign=np.sign(factors-1.)
    if np.any(lo<ce[0]) or np.any(hi>ce[-1]):
        raise ValueError('boundary strip leaves coefficient domain')
    out={k:np.zeros(d.size) for k in ('absorption','emission','scattering')}
    flat=lab.reshape(lab.shape[0],-1);n_depth=lab.shape[2]
    for start in range(0,d.size,2048):
        stop=min(start+2048,d.size);ids=np.arange(start,stop);di=ids%n_depth
        for g in range(len(ce)-1):
            lower=np.maximum(lo[ids],ce[g]);upper=np.minimum(hi[ids],ce[g+1])
            active=upper>lower
            if not np.any(active):continue
            selected=ids[active];depth=di[active];factor=factors[selected]
            # 只跳过几何交集为空的区间；所有非空频率段（含尾端）均积分。
            integral=_piecewise_constant_overlap_integral_columns(
                flat[:,selected],le,np.diff(le),
                (lower[active]/factor)[None,:],(upper[active]/factor)[None,:],
            )[0]*factor**4
            width=upper[active]-lower[active];sgn=sign[selected]
            out['absorption'][selected]+=sgn*fields[0][g,depth]*integral
            out['emission'][selected]-=sgn*fields[1][g,depth]*width
            out['scattering'][selected]+=sgn*fields[2][g,depth]*(integral-fields[3][g,depth]*width)
    if not all(np.isfinite(v).all() for v in out.values()):
        raise ArithmeticError('nonfinite boundary integral')
    return {k:v.reshape(d.shape) for k,v in out.items()}
