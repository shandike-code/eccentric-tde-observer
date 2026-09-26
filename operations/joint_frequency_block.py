"""Construct a contiguous core from the existing exact Doppler-halo planner."""
from dataclasses import replace
import numpy as np
from eccentric_tde_observer.mixed_frame_streaming import plan_mixed_frame_frequency_blocks


def joint_block(stencil, mu, weight, beta, start, stop):
    if type(start) is not int or type(stop) is not int or not 0 <= start < stop <= stencil.physical_group_count:
        raise ValueError('invalid global core interval')
    # Only the active interval changes; all global collision/outer edges remain exact.
    sub = replace(stencil, active_lab_edge_hz=stencil.active_lab_edge_hz[start:stop+1],
                  active_outer_group_start=stencil.active_outer_group_start+start,
                  active_outer_group_stop=stencil.active_outer_group_start+stop,
                  physical_group_count=stop-start)
    (block,) = plan_mixed_frame_frequency_blocks(sub, mu, weight, beta, stop-start)
    result = replace(block, core_group_start=start, core_group_stop=stop)
    if not np.array_equal(result.local_stencil.active_lab_edge_hz, stencil.active_lab_edge_hz[start:stop+1]):
        raise AssertionError('frequency edges changed')
    return result
