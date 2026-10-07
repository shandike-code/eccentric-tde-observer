"""Bounded explicit array results for stencil, Lorentz rays and block planning.

Only exact float64 ndarrays enter. Object/scalar/native private workspaces are
not measured; this component is not connected to production configuration.
"""
import numpy as np
from eccentric_tde_observer.mixed_frame_ale import MixedFrameFrequencyStencil
from eccentric_tde_observer.mixed_frame_frequency import LorentzRayTransform
from eccentric_tde_observer.mixed_frame_streaming import MixedFrameFrequencyBlock, _covering_group_slice
from eccentric_tde_observer.source import PhysicalDomainError


def reserve(ledger, check, name, size):
    check()
    ledger.reserve('frequency:' + name, int(size))


def layout(a, maximum):
    if type(a) is not np.ndarray or a.dtype != np.dtype('float64') or a.ndim != 1 or not 1 <= a.size <= maximum:
        raise ValueError('bounded float64 vector required')


def finite(a, ledger, check, name):
    reserve(ledger, check, name + ':finite', a.size)
    if not np.all(np.isfinite(a)): raise PhysicalDomainError('nonfinite ' + name)


def increasing(a, ledger, check, name):
    reserve(ledger, check, name + ':diff', (a.size-1)*8)
    delta = np.diff(a)
    reserve(ledger, check, name + ':increasing', delta.size)
    if np.any(delta <= 0.0): raise PhysicalDomainError('unordered ' + name)


def copy(a, ledger, check, name):
    reserve(ledger, check, name, a.nbytes)
    result = np.array(a, copy=True)
    result.setflags(write=False)
    return result


def stencil(active, maximum_velocity_beta, ledger, check):
    layout(active, 9633)
    if active.size < 2: raise PhysicalDomainError('empty frequency grid')
    finite(active, ledger, check, 'active')
    increasing(active, ledger, check, 'active')
    reserve(ledger, check, 'active:positive', active.size)
    if np.any(active <= 0): raise PhysicalDomainError('positive frequency required')
    beta = float(maximum_velocity_beta)
    if not np.isfinite(beta) or beta < 0.0 or beta >= 1.0: raise PhysicalDomainError('maximum beta')
    if beta == 0.0:
        collision = copy(active, ledger, check, 'collision-copy')
        outer = copy(active, ledger, check, 'outer-copy')
        start = 0
    else:
        # 原 Doppler 上下界与 128 epsilon 裕量；守护组不进入物理频带积分。
        gamma = 1.0 / np.sqrt(1.0 - beta**2)
        minimum_doppler = gamma * (1.0 - beta)
        maximum_doppler = gamma * (1.0 + beta)
        margin = 128.0 * np.finfo(np.float64).eps
        collision_low = minimum_doppler * active[0] * (1.0 - margin)
        collision_high = maximum_doppler * active[-1] * (1.0 + margin)
        outer_low = collision_low / maximum_doppler * (1.0 - margin)
        outer_high = collision_high / minimum_doppler * (1.0 + margin)
        middle = copy(active, ledger, check, 'collision-active-copy')
        reserve(ledger, check, 'collision-list-coercion-capacity', 16)
        reserve(ledger, check, 'collision-concatenate', (active.size+2)*8)
        collision = np.concatenate(([collision_low], middle, [collision_high]))
        middle = copy(active, ledger, check, 'outer-active-copy')
        reserve(ledger, check, 'outer-list-coercion-capacity', 32)
        reserve(ledger, check, 'outer-concatenate', (active.size+4)*8)
        outer = np.concatenate(([outer_low,collision_low],middle,[collision_high,outer_high]))
        start = 2
    increasing(collision, ledger, check, 'collision')
    increasing(outer, ledger, check, 'outer')
    finite(collision, ledger, check, 'collision-output')
    finite(outer, ledger, check, 'outer-output')
    return MixedFrameFrequencyStencil(
        outer_lab_edge_hz=copy(outer,ledger,check,'outer-return'),
        comoving_collision_edge_hz=copy(collision,ledger,check,'collision-return'),
        active_lab_edge_hz=copy(active,ledger,check,'active-return'),
        active_outer_group_start=start,active_outer_group_stop=start+active.size-1,
        physical_group_count=active.size-1,comoving_collision_group_count=collision.size-1,
        outer_lab_group_count=outer.size-1,groups_per_decade=None,maximum_velocity_beta=beta)


def rays(mu, weight, beta, ledger, check):
    layout(mu,32);layout(weight,32);layout(beta,4096)
    if mu.size < 2 or weight.shape != mu.shape: raise PhysicalDomainError('angular shape')
    finite(mu,ledger,check,'mu');finite(weight,ledger,check,'weight')
    for name,a,kind in [('mu-low',mu,'low'),('mu-high',mu,'high'),('weight-positive',weight,'positive')]:
        reserve(ledger,check,name,a.size)
        bad = a <= -1.0 if kind=='low' else a >= 1.0 if kind=='high' else a <= 0.0
        if np.any(bad): raise PhysicalDomainError(name)
    check()
    if not np.isclose(np.sum(weight),2.0,rtol=2e-13,atol=2e-15): raise PhysicalDomainError('quadrature unity')
    finite(beta,ledger,check,'beta')
    reserve(ledger,check,'beta-abs',beta.nbytes);absolute=np.abs(beta)
    reserve(ledger,check,'beta-domain',beta.size)
    if np.any(absolute >= 1.0): raise PhysicalDomainError('subluminal beta')
    reserve(ledger,check,'beta-square',beta.nbytes);square=beta**2
    reserve(ledger,check,'gamma-radicand',beta.nbytes);radicand=1.0-square
    reserve(ledger,check,'gamma-root',beta.nbytes);root=np.sqrt(radicand)
    reserve(ledger,check,'gamma',beta.nbytes);gamma=1.0/root
    mu_view=mu.reshape((mu.size,1));weight_view=weight.reshape((mu.size,1));n=mu.size*beta.size
    # D=nu_comoving/nu_lab；保留两次独立 denominator 计算，不合并原表达式。
    reserve(ledger,check,'doppler-product',n*8);product=mu_view*beta[None,...]
    reserve(ledger,check,'doppler-difference',n*8);difference=1.0-product
    reserve(ledger,check,'doppler',n*8);doppler=gamma[None,...]*difference
    reserve(ledger,check,'denominator-product',n*8);product=mu_view*beta[None,...]
    reserve(ledger,check,'denominator',n*8);denominator=1.0-product
    reserve(ledger,check,'aberration-numerator',n*8);numerator=mu_view-beta[None,...]
    reserve(ledger,check,'comoving-mu',n*8);comoving_mu=numerator/denominator
    reserve(ledger,check,'doppler-square',n*8);square=doppler**2
    reserve(ledger,check,'comoving-weight',n*8);comoving_weight=weight_view/square
    reserve(ledger,check,'weight-sum',beta.nbytes);total=np.sum(comoving_weight,axis=0)
    reserve(ledger,check,'measure',beta.nbytes);measure=0.5*total
    reserve(ledger,check,'measure-difference',beta.nbytes);difference=measure-1.0
    reserve(ledger,check,'measure-error',beta.nbytes);relative_error=np.abs(difference)
    arrays=(doppler,comoving_mu,comoving_weight,relative_error)
    for name,a in zip(('doppler','comoving-mu','comoving-weight','measure-error'),arrays):finite(a,ledger,check,name)
    reserve(ledger,check,'doppler-positive',n)
    if np.any(doppler <= 0):raise ArithmeticError('nonpositive Doppler')
    reserve(ledger,check,'comoving-mu-abs',n*8);absolute=np.abs(comoving_mu)
    reserve(ledger,check,'comoving-mu-domain',n)
    if np.any(absolute >= 1.0):raise ArithmeticError('aberration domain')
    return LorentzRayTransform(*(copy(a,ledger,check,name+'-return') for name,a in zip(('doppler','comoving-mu','comoving-weight','measure-error'),arrays)))


def plan(grid, mu, weight, beta, core_group_count, ledger, check):
    if type(core_group_count) is not int or not 1 <= core_group_count <= 128:raise ValueError('core size')
    # 只接受本组件可表示的固定频率规模，防止外部伪造 dataclass 绕过容量范围。
    for a in (grid.active_lab_edge_hz,grid.comoving_collision_edge_hz,grid.outer_lab_edge_hz):
        layout(a,9637)
        if not a.flags.c_contiguous:raise ValueError('planner requires contiguous stencil edges')
    if (type(grid.physical_group_count) is not int or grid.physical_group_count!=grid.active_lab_edge_hz.size-1 or not 1<=grid.physical_group_count<=9632):raise ValueError('grid count')
    transform=rays(mu,weight,beta,ledger,check)
    doppler=transform.doppler_lab_to_comoving
    check();minimum_doppler=float(np.min(doppler));maximum_doppler=float(np.max(doppler))
    active=grid.active_lab_edge_hz;collision=grid.comoving_collision_edge_hz;outer=grid.outer_lab_edge_hz
    blocks=[]
    for start in range(0,grid.physical_group_count,core_group_count):
        check();stop=min(start+core_group_count,grid.physical_group_count)
        cs,ce=_covering_group_slice(collision,float(active[start]*minimum_doppler),float(active[stop]*maximum_doppler))
        check()
        os,oe=_covering_group_slice(outer,float(collision[cs]/maximum_doppler),float(collision[ce]/minimum_doppler))
        gs=grid.active_outer_group_start+start;ge=grid.active_outer_group_start+stop
        if not os<=gs or not oe>=ge:raise ArithmeticError('lost active core')
        local=MixedFrameFrequencyStencil(
            outer_lab_edge_hz=copy(outer[os:oe+1],ledger,check,'block-outer'),
            comoving_collision_edge_hz=copy(collision[cs:ce+1],ledger,check,'block-collision'),
            active_lab_edge_hz=copy(active[start:stop+1],ledger,check,'block-active'),
            active_outer_group_start=gs-os,active_outer_group_stop=ge-os,
            physical_group_count=stop-start,comoving_collision_group_count=ce-cs,outer_lab_group_count=oe-os,
            groups_per_decade=grid.groups_per_decade,maximum_velocity_beta=grid.maximum_velocity_beta)
        blocks.append(MixedFrameFrequencyBlock(start,stop,cs,ce,os,oe,local))
    check()
    return tuple(blocks)


def native_configuration(*args,**kwargs):
    raise RuntimeError('DO NOT RUN: preparation not integrated or complete')
