"""Lab-frame collision four-force over a declared comoving frequency window.

Diagnostic v1: retains the existing P0 lab intensity and P0 comoving coefficients.
No material update, extrapolation, or observed source difference enters this API.
"""
import numpy as np
from eccentric_tde_observer.mixed_frame_frequency import (
    lorentz_ray_transform,
    _piecewise_constant_overlap_integral_columns,
)
from eccentric_tde_observer.radiation import LIGHT_SPEED_CM_S


def common_frequency_four_force(lab_intensity,lab_edge,comoving_edge,
                                extinction,emissivity,mu,weight,beta,window):
    """Integrate lab energy and momentum first, then inverse-transform the source.

    共动窗口[A,B]在每条射线的lab频域为[A/D,B/D]。在每个lab组与此
    窗口的交集上积分：∫chi_lab dnu=∫chi0 dnu0，
    ∫eta_lab dnu=D^-3∫eta0 dnu0。I_lab在lab组内为常数。
    因而先求lab碰撞源，再独立求其能量/动量矩，不调用原子加热路径。
    """
    lab=np.asarray(lab_intensity,dtype=float);le=np.asarray(lab_edge,dtype=float)
    ce=np.asarray(comoving_edge,dtype=float);chi=np.asarray(extinction,dtype=float)
    eta=np.asarray(emissivity,dtype=float);b=np.asarray(beta,dtype=float)
    mu=np.asarray(mu,dtype=float);weight=np.asarray(weight,dtype=float)
    win=np.asarray(window,dtype=float)
    transform=lorentz_ray_transform(mu,weight,b);d=transform.doppler_lab_to_comoving
    if (b.ndim!=1 or lab.ndim!=3 or lab.shape[1:]!=d.shape
        or le.ndim!=1 or le.size!=lab.shape[0]+1 or ce.ndim!=1
        or chi.shape!=(ce.size-1,b.size) or eta.shape!=chi.shape):
        raise ValueError('frequency/ray/depth axes mismatch')
    if (win.shape!=(2,) or not all(np.isfinite(v).all() for v in (lab,le,ce,chi,eta,win))
        or np.any(lab<0) or np.any(chi<0) or np.any(eta<0)
        or le[0]<=0 or ce[0]<=0 or np.any(np.diff(le)<=0) or np.any(np.diff(ce)<=0)
        or win[0]<=0 or win[1]<=win[0]):
        raise ValueError('invalid finite positive frequency/source domain')
    if win[0]<ce[0] or win[1]>ce[-1]:raise ValueError('window leaves coefficient domain')
    lower=win[0]/d;upper=win[1]/d
    if np.any(lower<le[0]) or np.any(upper>le[-1]):
        raise ValueError('transformed window leaves supplied lab domain')
    n_depth=b.size;flat=lab.reshape(lab.shape[0],-1);factors=d.ravel()
    lower=lower.ravel();upper=upper.ravel();collision=np.zeros(d.size);scale=np.zeros(d.size)
    for start in range(0,d.size,2048):
        stop=min(start+2048,d.size);ids=np.arange(start,stop);depth=ids%n_depth
        for f in range(lab.shape[0]):
            lo=np.maximum(lower[ids],le[f]);hi=np.minimum(upper[ids],le[f+1]);active=hi>lo
            if not np.any(active):continue
            selected=ids[active];di=depth[active];factor=factors[selected]
            # 使用交集的co频率端点直接从原窗口截断；避免A/D*D的末位越界。
            # 这不是物理量裁剪：max/min仅构造已声明频域的几何交集。
            co_lo=np.maximum(win[0],le[f]*factor)[None,:]
            co_hi=np.minimum(win[1],le[f+1]*factor)[None,:]
            chi_int=_piecewise_constant_overlap_integral_columns(
                chi[:,di],ce,np.diff(ce),co_lo,co_hi,
            )[0]
            eta_int=_piecewise_constant_overlap_integral_columns(
                eta[:,di],ce,np.diff(ce),co_lo,co_hi,
            )[0]/factor**3
            absorbed=flat[f,selected]*chi_int
            collision[selected]+=eta_int-absorbed
            scale[selected]+=eta_int+absorbed
    collision=collision.reshape(d.shape);scale=scale.reshape(d.shape)
    energy=2*np.pi*np.sum(weight[:,None]*collision,axis=0)
    momentum=2*np.pi/LIGHT_SPEED_CM_S*np.sum(weight[:,None]*mu[:,None]*collision,axis=0)
    heating=-(energy-b*LIGHT_SPEED_CM_S*momentum)/np.sqrt(1-b*b)
    result={'lab_energy_erg_s_cm3':energy,'lab_momentum_dyn_cm3':momentum,
            'common_formal_erg_s_cm3':heating,
            'absolute_collision_scale_erg_s_cm3':2*np.pi*np.sum(weight[:,None]*scale,axis=0)}
    if not all(np.isfinite(v).all() for v in result.values()):
        raise ArithmeticError('nonfinite common-window four-force')
    return result
