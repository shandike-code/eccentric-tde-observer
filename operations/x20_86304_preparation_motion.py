"""Column-integrated context with explicit validation and motion result budgets.

Gauss, stencil and planner internals remain outside this array-result ledger.
This is not complete native metering or interpreter-startup protection.
"""
import numpy as np
from operations.x20_86304_preparation_column import full_column
from scripts.phase7b5x_full_depth_block_probe import (
    LIGHT_SPEED_CM_S, gauss_legendre_split_mu_weights,
    mixed_frame_frequency_stencil_from_active_edges,
    plan_mixed_frame_frequency_blocks,
)


def reserve(ledger, check, label, size):
    check()
    ledger.reserve('motion:' + label, size)


def validate_arrays(material, master, ledger, check):
    rho = material['density_g_cm3']
    if type(rho) is not np.ndarray or rho.ndim != 2 or not 2 <= rho.shape[0] <= 2048:
        raise ValueError('phase shape')
    phases = rho.shape[0]
    shapes = {'density_g_cm3': (phases,128), 'temperature_k': (phases,128),
              'hydrogen_fraction': (phases,128,2), 'helium_fraction': (phases,128,3),
              'cell_mass_g_cm2': (128,), 'step_duration_s': (phases,)}
    for key, shape in shapes.items():
        a = material[key]
        if type(a) is not np.ndarray or a.dtype != np.dtype('float64') or a.shape != shape:
            raise ValueError('material layout')
        reserve(ledger, check, key + ':finite-mask', a.size)
        if not np.all(np.isfinite(a)): raise ValueError('material finite')
        reserve(ledger, check, key + ':lower-mask', a.size)
        if key.endswith('_fraction'):
            if np.any(a < 0): raise ValueError('population domain')
            reserve(ledger, check, key + ':upper-mask', a.size)
            if np.any(a > 1): raise ValueError('population domain')
        elif np.any(a <= 0): raise ValueError('positive material')
    edge = master['active_edge_hz']; maximum = master['maximum_beta']
    if (type(edge) is not np.ndarray or edge.dtype != np.dtype('float64') or
            edge.ndim != 1 or not 2 <= edge.size <= 9633): raise ValueError('frequency layout')
    reserve(ledger, check, 'edge-finite-mask', edge.size)
    if not np.all(np.isfinite(edge)): raise ValueError('frequency finite')
    reserve(ledger, check, 'edge-positive-mask', edge.size)
    if np.any(edge <= 0): raise ValueError('frequency positive')
    reserve(ledger, check, 'edge-diff', (edge.size-1)*8)
    difference = np.diff(edge)
    reserve(ledger, check, 'edge-increasing-mask', difference.size)
    if np.any(difference <= 0): raise ValueError('frequency increasing')
    if type(maximum) is not np.ndarray or maximum.dtype != np.dtype('float64') or maximum.shape != ():
        raise ValueError('maximum beta layout')
    check()
    if not np.isfinite(maximum) or not 0 <= float(maximum) < 1: raise ValueError('maximum beta domain')


def motion_arrays(material, ledger, check):
    """Original phase-selection and velocity tree, following metered column."""
    full = full_column(material, ledger, check)
    edge = full['edge_cm']; phases = edge.shape[0]
    reserve(ledger, check, 'following-edge', edge.nbytes)
    following_edge = np.roll(edge, -1, axis=0)
    reserve(ledger, check, 'edge-displacement', edge.nbytes)
    displacement = following_edge - full['edge_cm']
    # 边界位移 cm 除以 dt*c（cm）得到无量纲 beta；保留原乘法后除法顺序。
    reserve(ledger, check, 'duration-light-distance', phases*8)
    distance = material['step_duration_s'][:, None] * LIGHT_SPEED_CM_S
    reserve(ledger, check, 'face-beta', edge.nbytes)
    face_beta = displacement / distance
    del displacement, distance
    reserve(ledger, check, 'face-beta-absolute', face_beta.nbytes)
    absolute = np.abs(face_beta)
    # argmax 可能为 C 顺序复制输入；按完整容量预留，不冒称实测必有此复制。
    reserve(ledger, check, 'argmax-contiguous-capacity', face_beta.nbytes)
    phase = int(np.unravel_index(np.argmax(absolute), face_beta.shape)[0])
    del absolute
    following = (phase + 1) % face_beta.shape[0]
    duration = float(material['step_duration_s'][phase])
    reserve(ledger, check, 'adjacent-face-sum', 256*8)
    adjacent = face_beta[phase, :-1] + face_beta[phase, 1:]
    reserve(ledger, check, 'parent-beta', 256*8)
    parent_beta = 0.5 * adjacent
    del adjacent
    reserve(ledger, check, 'subcell-beta', 4096*8)
    beta = np.repeat(parent_beta, 16)
    for name, a in [('face-beta',face_beta),('parent-beta',parent_beta),('beta',beta)]:
        reserve(ledger, check, name + ':finite-mask', a.size)
        if not np.all(np.isfinite(a)): raise ValueError('nonfinite motion')
    check()
    return dict(full=full,face_beta=face_beta,phase=phase,following=following,
                duration_s=duration,parent_beta=parent_beta,beta=beta)


def context_from_arrays(material, master, ledger, check):
    validate_arrays(material, master, ledger, check)
    result = motion_arrays(material, ledger, check)
    beta = result['beta']
    # 这里只预约求积返回数组；leggauss 及其下层内部临时量尚未计量。
    reserve(ledger, check, 'quadrature-return-capacity', 2*32*8)
    mu, weight = gauss_legendre_split_mu_weights(32, 0.0)
    reserve(ledger, check, 'active-edge-copy', master['active_edge_hz'].nbytes)
    active_edge = np.array(master['active_edge_hz'], copy=True)
    maximum_beta = float(master['maximum_beta'])
    check()
    stencil = mixed_frame_frequency_stencil_from_active_edges(active_edge, maximum_beta)
    check()
    blocks = plan_mixed_frame_frequency_blocks(stencil, mu, weight, beta, 128)
    rows = []
    for index, block in enumerate(blocks):
        check()
        active = block.local_stencil.physical_group_count
        collision = block.local_stencil.comoving_collision_group_count
        outer = block.local_stencil.outer_lab_group_count
        identified = 8 * mu.size * (
            5 * active * beta.size + 2 * outer * beta.size + collision * beta.size
            + active * (beta.size + 1))
        rows.append((identified, index, block))
    identified_bytes, block_index, selected = max(rows, key=lambda row: row[0])
    result.update(material=material,mu=mu,weight=weight,stencil=stencil,blocks=blocks,
                  selected=selected,selected_block_index=block_index,identified_live_bytes=identified_bytes)
    check()
    return result


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: scientific internals and lifecycle incomplete')
