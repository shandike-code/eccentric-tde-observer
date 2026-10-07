"""In-memory original context arithmetic; real-source entry remains closed.

Authentication belongs to ArrayLoader plus an external source manifest. This
component never reads a path and does not confer production source identity.
"""
import numpy as np
from scripts.phase7b5x_full_depth_block_probe import (
    _full_column, LIGHT_SPEED_CM_S, gauss_legendre_split_mu_weights,
    mixed_frame_frequency_stencil_from_active_edges,
    plan_mixed_frame_frequency_blocks,
)


def validate_arrays(material, master):
    """Validate before original divisions; supports tiny synthetic phase counts."""
    required = {'density_g_cm3': (128,), 'temperature_k': (128,),
                'hydrogen_fraction': (128, 2), 'helium_fraction': (128, 3)}
    rho = material['density_g_cm3']
    if type(rho) is not np.ndarray or rho.ndim != 2 or not 2 <= rho.shape[0] <= 2048:
        raise ValueError('phase shape')
    phases = rho.shape[0]
    for key, tail in required.items():
        v = material[key]
        if (type(v) is not np.ndarray or v.dtype != np.dtype('float64') or
                v.shape != (phases, *tail) or not np.all(np.isfinite(v))):
            raise ValueError('material shape/dtype/finite: ' + key)
        if key in ('density_g_cm3', 'temperature_k') and np.any(v <= 0):
            raise ValueError('nonpositive ' + key)
        if key.endswith('_fraction') and (np.any(v < 0) or np.any(v > 1)):
            raise ValueError('population domain')
    for key, shape in [('cell_mass_g_cm2', (128,)), ('step_duration_s', (phases,))]:
        v = material[key]
        if (type(v) is not np.ndarray or v.dtype != np.dtype('float64') or
                v.shape != shape or not np.all(np.isfinite(v)) or np.any(v <= 0)):
            raise ValueError('positive mass/duration')
    edge = master['active_edge_hz']; maximum = master['maximum_beta']
    if (type(edge) is not np.ndarray or edge.dtype != np.dtype('float64') or
            edge.ndim != 1 or not 2 <= edge.size <= 9633 or
            not np.all(np.isfinite(edge)) or np.any(edge <= 0) or np.any(np.diff(edge) <= 0)):
        raise ValueError('frequency edge domain')
    if (type(maximum) is not np.ndarray or maximum.dtype != np.dtype('float64') or
            maximum.shape != () or not np.isfinite(maximum) or not 0 <= float(maximum) < 1):
        raise ValueError('maximum beta domain')


def _context_arrays(material, master):
    # 中文：仅移除原来两个磁盘读取点；柱几何、速度、相位及频率规划保持原表达式顺序。
    full = _full_column(material)
    following_edge = np.roll(full["edge_cm"], -1, axis=0)
    face_beta = (following_edge - full["edge_cm"]) / (
        material["step_duration_s"][:, None] * LIGHT_SPEED_CM_S
    )
    phase = int(np.unravel_index(np.argmax(np.abs(face_beta)), face_beta.shape)[0])
    following = (phase + 1) % face_beta.shape[0]
    duration = float(material["step_duration_s"][phase])
    parent_beta = 0.5 * (face_beta[phase, :-1] + face_beta[phase, 1:])
    beta = np.repeat(parent_beta, 16)
    mu, weight = gauss_legendre_split_mu_weights(32, 0.0)
    active_edge = np.array(master["active_edge_hz"], copy=True)
    maximum_beta = float(master["maximum_beta"])
    stencil = mixed_frame_frequency_stencil_from_active_edges(
        active_edge, maximum_beta
    )
    blocks = plan_mixed_frame_frequency_blocks(stencil, mu, weight, beta, 128)
    rows = []
    for index, block in enumerate(blocks):
        active = block.local_stencil.physical_group_count
        collision = block.local_stencil.comoving_collision_group_count
        outer = block.local_stencil.outer_lab_group_count
        identified = 8 * mu.size * (
            5 * active * beta.size
            + 2 * outer * beta.size
            + collision * beta.size
            + active * (beta.size + 1)
        )
        rows.append((identified, index, block))
    identified_bytes, block_index, selected = max(rows, key=lambda row: row[0])
    return {
        "material": material,
        "full": full,
        "face_beta": face_beta,
        "phase": phase,
        "following": following,
        "duration_s": duration,
        "parent_beta": parent_beta,
        "beta": beta,
        "mu": mu,
        "weight": weight,
        "stencil": stencil,
        "blocks": blocks,
        "selected": selected,
        "selected_block_index": block_index,
        "identified_live_bytes": identified_bytes,
    }


def context_from_arrays(material, master, check):
    validate_arrays(material, master)
    check()
    result = _context_arrays(material, master)
    check()
    return result


def native_configuration(*args, **kwargs):
    raise RuntimeError("DO NOT RUN: lifecycle and complete native acceptance pending")
