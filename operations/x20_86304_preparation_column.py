"""Explicit array-result reservations for the original full-column expressions.

This isolated component is not yet wired into header_configuration. Reservations
are cumulative payload capacities, excluding ndarray/Python objects and native
reduction workspace; they are neither allocator measurements nor an RSS bound.
"""
import numpy as np


def full_column(material, ledger, check):
    """Preserve the original numerical expression tree and operand order."""
    rho = material['density_g_cm3']
    if type(rho) is not np.ndarray or rho.dtype != np.dtype('float64') or rho.ndim != 2:
        raise ValueError('density layout')
    phases, cells = rho.shape
    if cells != 128 or not 2 <= phases <= 2048:
        raise ValueError('column shape')
    shapes = {'cell_mass_g_cm2': (128,), 'density_g_cm3': (phases, 128),
              'temperature_k': (phases, 128), 'hydrogen_fraction': (phases, 128, 2),
              'helium_fraction': (phases, 128, 3)}

    def reserve(label, size):
        check()
        ledger.reserve('column:' + label, size)

    # 面质量除以体密度给出层宽 cm；验证不修补或归一化输入。
    for key, shape in shapes.items():
        a = material[key]
        if type(a) is not np.ndarray or a.dtype != np.dtype('float64') or a.shape != shape:
            raise ValueError('material layout: ' + key)
        reserve(key + ':finite-mask', a.size)
        if not np.all(np.isfinite(a)):
            raise ValueError('nonfinite material')
        reserve(key + ':lower-mask', a.size)
        if key.endswith('fraction'):
            if np.any(a < 0):
                raise ValueError('negative population')
            reserve(key + ':upper-mask', a.size)
            if np.any(a > 1):
                raise ValueError('population above one')
        elif np.any(a <= 0):
            raise ValueError('nonpositive material')

    reserve('half-width', phases * 128 * 8)
    half_width = material['cell_mass_g_cm2'][None, :] / material['density_g_cm3']
    reserve('full-width', phases * 256 * 8)
    full_width = np.concatenate((half_width, half_width[:, ::-1]), axis=1)
    reserve('half-thickness', phases * 8)
    half_thickness = np.sum(half_width, axis=1)
    # 保留两次负号及原 cumsum/add/concatenate 求值顺序，不作代数改写。
    reserve('left-negative', phases * 8)
    left = -half_thickness[:, None]
    reserve('right-negative', phases * 8)
    negative = -half_thickness[:, None]
    reserve('cumulative-width', phases * 256 * 8)
    cumulative = np.cumsum(full_width, axis=1)
    reserve('shifted-edge', phases * 256 * 8)
    shifted = negative + cumulative
    del negative, cumulative
    reserve('edge', phases * 257 * 8)
    edge = np.concatenate((left, shifted), axis=1)
    del left, shifted
    check()
    scale = float(np.max(half_thickness))
    reserve('midplane-absolute', phases * 8)
    if float(np.max(np.abs(edge[:, 128]))) / scale > 2.0e-15:
        raise ArithmeticError('centred full column lost its midplane')
    result = {'edge_cm': edge}
    for key in ('density_g_cm3', 'temperature_k', 'hydrogen_fraction', 'helium_fraction'):
        reserve(key + ':mirror', 2 * material[key].nbytes)
        result[key] = np.concatenate((material[key], material[key][:, ::-1]), axis=1)
    # 原调用者只验输入有限；本接口另拒中间溢出，不给 NaN 通过中面比较的机会。
    for key, a in result.items():
        reserve(key + ':output-finite-mask', a.size)
        if not np.all(np.isfinite(a)):
            raise ValueError('nonfinite column output')
    check()
    return result


def native_configuration(*args, **kwargs):
    raise RuntimeError('DO NOT RUN: isolated column component, preparation incomplete')
