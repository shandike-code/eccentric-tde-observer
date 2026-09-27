import runpy
from pathlib import Path
import numpy as np
import pytest
from operations.pilot_step21_seven_refresh import core_interval,exact_replay
from operations.joint_frequency_block import joint_block
from eccentric_tde_observer.mixed_frame_streaming import plan_mixed_frame_frequency_blocks,stream_mixed_frame_ale_source_iteration


def test_replay_rejects_even_tolerable_nonidentical_result():
    x=np.ones(2); y=x+0.1; z=y.copy(); z[0]=np.nextafter(z[0],np.inf)
    with pytest.raises(RuntimeError,match='bytewise'):exact_replay(x,y,z)
    assert exact_replay(x,y,y)['array_equal']


@pytest.mark.parametrize('index',[True,24.0,23,49,-1])
def test_only_registered_seven_cores(index):
    with pytest.raises(ValueError):core_interval(index)


def test_seven_core_global_indices_and_widths():
    assert core_interval(24)==(2688,3584)
    assert core_interval(48)==(5760,6656)


def test_seven_natural_blocks_preserve_native_operator():
    c=runpy.run_path(str(Path(__file__).with_name('test_mixed_frame_streaming.py')))['_streaming_case']()
    s=c['stencil'];natural=plan_mixed_frame_frequency_blocks(s,c['mu'],c['weight'],c['beta'],5)
    joint=tuple(joint_block(s,c['mu'],c['weight'],c['beta'],a,b) for a,b in [(0,35),(35,41)])
    outputs=[]
    for blocks in (natural,joint):
        out=np.empty_like(c['current'])
        stream_mixed_frame_ale_source_iteration(s,blocks,c['old_edge'],c['new_edge'],c['mu'],c['weight'],c['initial'],c['outer'],c['absorption'],c['emissivity'],c['scattering'],c['beta'],1.,c['current'],out,left_exterior_intensity=c['left'],right_exterior_intensity=c['right'],propagation_speed_cm_s=1.,spatial_scheme='hybrid_step_turning_upwind',compute_block_diagnostics=False)
        outputs.append(out)
    np.testing.assert_allclose(outputs[0],outputs[1],rtol=2e-14,atol=0)
    assert np.max(abs(outputs[0]-outputs[1]))/np.max(abs(outputs[0]-c['current']))<1e-6


def test_refresh_uses_actual_settled_map_and_rejects_old_or_partial():
    from operations.pilot_step21_seven_refresh import refreshed_pair
    rows=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,11)]
    state=dict(history=rows,active_map=None)
    ret=dict(history_rows=rows[-2:],endpoints=dict(final=dict(path='new-input',sha256='9'),mapped_final=dict(path='new-output',sha256='10')))
    old=[dict(sha256='old-x'),dict(sha256='old-y')]
    assert refreshed_pair(state,ret,old)==(ret['endpoints']['final'],ret['endpoints']['mapped_final'])
    for stale in ([dict(sha256='9'),old[1]],[old[0],dict(sha256='10')]):
        with pytest.raises(RuntimeError,match='reuse'):refreshed_pair(state,ret,stale)
    state['active_map']={'partial':True}
    with pytest.raises(RuntimeError,match='settled'):refreshed_pair(state,ret,old)


def test_refresh_rejects_crossed_endpoint_lineage():
    from operations.pilot_step21_seven_refresh import refreshed_pair
    rows=[dict(iteration=i,input_sha256=str(i-1),output_sha256=str(i)) for i in range(1,11)]
    state=dict(history=rows,active_map=None)
    ret=dict(history_rows=rows[-2:],endpoints=dict(final=dict(sha256='10'),mapped_final=dict(sha256='9')))
    with pytest.raises(RuntimeError,match='actual final'):refreshed_pair(state,ret,[dict(sha256='a'),dict(sha256='b')])
