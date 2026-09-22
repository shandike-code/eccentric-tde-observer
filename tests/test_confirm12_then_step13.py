import numpy as np
import pytest
from operations import confirm12_then_step13 as task


def materials(alpha=1/64):
    x=np.array([1.,2.,3.,4.]);r=np.array([.1,.2,.3,.4])
    return ({'relaxation':np.array(0.),'encoded_state':x,'base_encoded_state':x.copy()},
        {'relaxation':np.array(alpha),'encoded_state':x+alpha*r,
         'base_encoded_state':x.copy(),'finite_direction':r})


def test_actual_amplitude_and_displacement_are_both_required():
    b,t=materials();task.validate_accepted_material(b,t)
    with pytest.raises(RuntimeError):task.validate_accepted_material(*materials(1/128))
    t['encoded_state'][0]+=.01
    with pytest.raises(RuntimeError):task.validate_accepted_material(b,t)


def test_adapters_restore_frozen_module_bindings_after_exception():
    a=task.stage.prepare_confirmation;b=task.batch.ALPHAS
    with pytest.raises(RuntimeError):
        with task.adapters():
            assert task.stage.prepare_confirmation is task.prepare_confirmation
            assert task.batch.ALPHAS=={'full':1/64,'half':1/128}
            raise RuntimeError('injected')
    assert task.stage.prepare_confirmation is a and task.batch.ALPHAS is b


@pytest.mark.parametrize('field,value',[
    ('outer_step_index',11),('formal_finite_step_accepted',False),
    ('fresh_control_corroborated',False),('alphas',{'full':1/128,'half':1/256})])
def test_unqualified_source_never_runs_confirmation(monkeypatch,tmp_path,field,value):
    d={'outer_step_index':12,'formal_finite_step_accepted':True,
       'fresh_control_corroborated':True,'alphas':task.NEXT_ALPHAS};d[field]=value
    calls=[]
    monkeypatch.setattr(task.stage,'configure',lambda *a:None)
    monkeypatch.setattr(task.pipeline,'read',lambda *a:d)
    monkeypatch.setattr(task.stage,'execute',lambda *a:calls.append('execute'))
    with pytest.raises(RuntimeError,match='corroborated'):task.execute(tmp_path)
    assert not calls


def test_validated_source_uses_bounded_combined_driver(monkeypatch,tmp_path):
    d={'outer_step_index':12,'formal_finite_step_accepted':True,
       'fresh_control_corroborated':True,'alphas':task.NEXT_ALPHAS}
    calls=[]
    monkeypatch.setattr(task.stage,'configure',lambda source,index:calls.append((source,index)))
    monkeypatch.setattr(task.pipeline,'read',lambda *a:d)
    def execute(out):
        assert task.stage.prepare_confirmation is task.prepare_confirmation
        assert task.batch.ALPHAS==task.NEXT_ALPHAS
        assert task.stage.MAXIMUM_MAPS==24 and task.stage.MAXIMUM_PAIRS==8
        calls.append('execute')
    monkeypatch.setattr(task.stage,'execute',execute)
    task.execute(tmp_path)
    assert calls==[(task.SOURCE,12),'execute']
