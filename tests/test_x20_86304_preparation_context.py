"""Only synthetic context planning, without real material or master paths."""
import ast
from pathlib import Path
import numpy as np
import pytest
from operations import x20_86304_preparation_context as target


def inputs():
    return ({'density_g_cm3': np.ones((2,128)),
             'temperature_k': np.ones((2,128))*10000,
             'hydrogen_fraction': np.broadcast_to([.75,.25],(2,128,2)).copy(),
             'helium_fraction': np.broadcast_to([.5,.25,.25],(2,128,3)).copy(),
             'cell_mass_g_cm2': np.ones(128),'step_duration_s': np.ones(2)},
            {'active_edge_hz': np.arange(1.,131.),'maximum_beta': np.array(0.)})


def test_original_ast_order():
    root=Path(__file__).resolve().parents[1]
    source=ast.parse((root/'scripts/phase7b5x_full_depth_block_probe.py').read_text())
    original=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='_context')
    new=ast.parse((root/'operations/x20_86304_preparation_context.py').read_text())
    adapted=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='_context_arrays')
    expected=original.body[1:]
    index=next(i for i,n in enumerate(expected) if isinstance(n,ast.With))
    replaced=expected[index].body
    for stmt in replaced:
        for node in ast.walk(stmt):
            if isinstance(node,ast.Name) and node.id=='data': node.id='master'
    expected[index:index+1]=replaced
    assert ast.dump(ast.Module(body=expected,type_ignores=[])) == ast.dump(ast.Module(body=adapted.body,type_ignores=[]))


def test_static_column_independent():
    old,master=inputs(); before={k:v.tobytes() for k,v in old.items()}
    c=target.context_from_arrays(old,master,lambda:None)
    assert c['phase']==0 and c['following']==1 and c['duration_s']==1
    assert np.array_equal(c['full']['edge_cm'],np.tile(np.arange(-128.,129.),(2,1)))
    assert np.count_nonzero(c['face_beta'])==0 and np.count_nonzero(c['beta'])==0
    assert c['beta'].shape==(4096,)
    assert [(b.core_group_start,b.core_group_stop) for b in c['blocks']]==[(0,128),(128,129)]
    for b in c['blocks']:
        assert b.collision_group_start==b.outer_group_start==b.core_group_start
        assert b.collision_group_stop==b.outer_group_stop==b.core_group_stop
    assert c['selected_block_index']==0
    assert np.isclose(np.sum(c['weight']),2.,rtol=0,atol=2e-15)
    assert np.isclose(np.sum(c['weight']*c['mu']),0.,rtol=0,atol=2e-15)
    assert {k:v.tobytes() for k,v in old.items()}==before


def test_moving_column_phase_and_sign():
    old,master=inputs();old['density_g_cm3'][1]*=.5;master['maximum_beta']=np.array(1e-6)
    c=target.context_from_arrays(old,master,lambda:None)
    expected=np.arange(-128.,129.)/target.LIGHT_SPEED_CM_S
    assert np.array_equal(c['face_beta'][0],expected)
    assert np.array_equal(c['face_beta'][1],-expected)
    assert c['phase']==0
    assert np.array_equal(c['parent_beta'],.5*(expected[:-1]+expected[1:]))
    assert np.array_equal(c['beta'],np.repeat(c['parent_beta'],16))
    assert [(b.core_group_start,b.core_group_stop) for b in c['blocks']]==[(0,128),(128,129)]


@pytest.mark.parametrize('key', ['density_g_cm3','temperature_k','cell_mass_g_cm2','step_duration_s'])
@pytest.mark.parametrize('value', [0.,-1.,float('nan'),float('inf')])
def test_invalid_positive(key,value):
    old,master=inputs();old[key].flat[0]=value
    with pytest.raises(ValueError):target.context_from_arrays(old,master,lambda:None)


@pytest.mark.parametrize('bad', [np.array(True),np.array(-.1),np.array(1.),np.array(float('nan')),np.ones(1)])
def test_invalid_master_beta(bad):
    old,master=inputs();master['maximum_beta']=bad
    with pytest.raises(ValueError):target.context_from_arrays(old,master,lambda:None)


def test_frequency_and_shape_and_stop():
    old,master=inputs();master['active_edge_hz'][0]=0
    with pytest.raises(ValueError):target.context_from_arrays(old,master,lambda:None)
    old,master=inputs();old['density_g_cm3']=np.ones((2,127))
    with pytest.raises(ValueError):target.context_from_arrays(old,master,lambda:None)
    old,master=inputs()
    def stop():raise RuntimeError('stop')
    with pytest.raises(RuntimeError,match='stop'):target.context_from_arrays(old,master,stop)
    with pytest.raises(RuntimeError,match='DO NOT RUN'):target.native_configuration(synthetic=True)
