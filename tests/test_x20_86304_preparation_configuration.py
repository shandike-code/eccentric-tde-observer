import hashlib
import json
import numpy as np
import pytest
from handoff.audit_tools.exercise_x20_86304_preparation_configuration import fixture
from operations.x20_86304_preparation_configuration import configure_from_bytes, native_configuration


def test_composed_configuration():
    args=fixture();before=tuple(dict(x) for x in args)
    result=configure_from_bytes(*args,lambda:None)
    assert args==before
    assert result['fixed']['sources']['current_material_state']==args[1]['trial']
    assert result['template']['sources']['second_material_iterate']==args[1]['trial']
    assert result['template']['sources']['initial_radiation_state']['path']==args[2]['path']
    c=result['context']
    assert (c['phase'],c['following'],c['duration_s'])==(0,1,1.)
    assert [(b.core_group_start,b.core_group_stop) for b in c['blocks']]==[(0,128),(128,129)]
    assert np.array_equal(c['full']['edge_cm'],np.tile(np.arange(-128.,129.),(2,1)))
    assert np.count_nonzero(c['beta'])==0
    assert result['material']['density_parent'].shape==(256,)
    assert result['production_authorized'] is False


@pytest.mark.parametrize('role',['fixed','template','trial','base','residual','old','master'])
def test_bad_sha(role):
    b,c,w,e=fixture();c[role]['sha256']='1'*64
    with pytest.raises(ValueError,match='authenticated'):configure_from_bytes(b,c,w,e,lambda:None)


@pytest.mark.parametrize('change',['phase_bool','phase_wrong','duration_bool','shape_bool','shape_wrong','warm_size','warm_parent','warm_absolute','warm_bool','missing'])
def test_external_rejection(change):
    b,c,w,e=fixture()
    if change=='phase_bool':e['phase']=False
    if change=='phase_wrong':e['phase']=1
    if change=='duration_bool':e['duration_s']=True
    if change=='shape_bool':e['shape'][0]=True
    if change=='shape_wrong':e['shape'][0]=128
    if change=='warm_size':w['size_bytes']+=1
    if change=='warm_parent':w['path']='../bad.dat'
    if change=='warm_absolute':w['path']='/bad.dat'
    if change=='warm_bool':w['size_bytes']=True
    if change=='missing':del b['master']
    with pytest.raises(ValueError):configure_from_bytes(b,c,w,e,lambda:None)


@pytest.mark.parametrize('role',['old','master'])
def test_wrong_role_binding(role):
    b,c,w,e=fixture();t=json.loads(b['template'])
    key={'old':'phase7b4r_material','master':'phase7b5p_master_input'}[role]
    t['sources'][key]['sha256']='1'*64
    b['template']=json.dumps(t).encode();c['template'].update(size_bytes=len(b['template']),sha256=hashlib.sha256(b['template']).hexdigest())
    f=json.loads(b['fixed']);f['sources']['phase7b7i_template_protocol']=c['template']
    b['fixed']=json.dumps(f).encode();c['fixed'].update(size_bytes=len(b['fixed']),sha256=hashlib.sha256(b['fixed']).hexdigest())
    with pytest.raises(ValueError,match='source role'):configure_from_bytes(b,c,w,e,lambda:None)


def test_stop_and_closed():
    def stop():raise RuntimeError('stop')
    with pytest.raises(RuntimeError,match='stop'):configure_from_bytes(*fixture(),stop)
    with pytest.raises(RuntimeError,match='DO NOT RUN'):native_configuration(synthetic=True)
