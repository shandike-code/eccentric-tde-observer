from pathlib import Path
import runpy
import numpy as np
import pytest
from operations.joint_frequency_block import joint_block
from eccentric_tde_observer.mixed_frame_streaming import plan_mixed_frame_frequency_blocks, stream_mixed_frame_ale_source_iteration


def case():
    return runpy.run_path(str(Path(__file__).with_name('test_mixed_frame_streaming.py')))['_streaming_case']()


def test_subinterval_reproduces_original_planner_bytewise():
    c=case();s=c['stencil']
    for b in plan_mixed_frame_frequency_blocks(s,c['mu'],c['weight'],c['beta'],7):
        j=joint_block(s,c['mu'],c['weight'],c['beta'],b.core_group_start,b.core_group_stop)
        for k in ('core_group_start','core_group_stop','collision_group_start','collision_group_stop','outer_group_start','outer_group_stop'):
            assert getattr(j,k)==getattr(b,k)
        for k in ('active_lab_edge_hz','outer_lab_edge_hz','comoving_collision_edge_hz'):
            assert np.array_equal(getattr(j.local_stencil,k),getattr(b.local_stencil,k))
        assert j.local_stencil.active_outer_group_start==b.local_stencil.active_outer_group_start


@pytest.mark.parametrize('start,stop',[(-1,2),(2,2),(2,42),(True,3),(1.5,3)])
def test_bad_intervals_rejected(start,stop):
    c=case()
    with pytest.raises(ValueError):joint_block(c['stencil'],c['mu'],c['weight'],c['beta'],start,stop)


def test_joint_partition_replays_natural_jacobi_map():
    c=case();s=c['stencil'];natural=plan_mixed_frame_frequency_blocks(s,c['mu'],c['weight'],c['beta'],7)
    joint=tuple(joint_block(s,c['mu'],c['weight'],c['beta'],a,b) for a,b in [(0,7),(7,28),(28,41)])
    outputs=[]
    for blocks in (natural,joint):
        out=np.empty_like(c['current'])
        stream_mixed_frame_ale_source_iteration(s,blocks,c['old_edge'],c['new_edge'],c['mu'],c['weight'],c['initial'],c['outer'],c['absorption'],c['emissivity'],c['scattering'],c['beta'],1.,c['current'],out,
            left_exterior_intensity=c['left'],right_exterior_intensity=c['right'],propagation_speed_cm_s=1.,spatial_scheme='hybrid_step_turning_upwind',compute_block_diagnostics=False)
        outputs.append(out)
    error=np.max(abs(outputs[0]-outputs[1]))
    assert error/np.max(abs(outputs[0]))<2e-14
    assert error/np.max(abs(outputs[0]-c['current']))<1e-6
