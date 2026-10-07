"""Frequency-component wiring; leggauss/material/startup internals remain open."""
import numpy as np
from operations.x20_86304_preparation_motion import validate_arrays, motion_arrays, reserve
from operations.x20_86304_preparation_quadrature import split_weights
from operations.x20_86304_preparation_stencil import stencil as frequency_stencil, plan as frequency_plan


def context_from_arrays(material, master, ledger, check):
    validate_arrays(material, master, ledger, check)
    result = motion_arrays(material, ledger, check)
    beta = result['beta']
    mu, weight = split_weights(32, 0.0, ledger, check)
    reserve(ledger, check, 'active-edge-copy', master['active_edge_hz'].nbytes)
    active_edge = np.array(master['active_edge_hz'], copy=True)
    maximum_beta = float(master['maximum_beta'])
    check()
    stencil = frequency_stencil(active_edge, maximum_beta, ledger, check)
    check()
    blocks = frequency_plan(stencil, mu, weight, beta, 128, ledger, check)
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
