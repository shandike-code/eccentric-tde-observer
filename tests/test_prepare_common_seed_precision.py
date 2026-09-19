from copy import deepcopy
import numpy as np
import pytest
from operations.prepare_common_seed_precision import latest_seed,same_material
from operations import common_seed_trial_control as control
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def state():
    return {'status':'common_seed_control_complete','history':[{'output_path':'s.dat','output_sha256':'a'*64}],
            'slots':['s.dat'],'current_slot':0,'current_sha256':'a'*64,'active_map':None}


def test_latest_seed_is_exact_recorded_output():
    assert latest_seed(state())['sha256']=='a'*64


@pytest.mark.parametrize('field,value',[('status','radiation'),('active_map',{'iteration':3}),
                                       ('pending_feedback',{'round':1}),('current_sha256','b'*64)])
def test_rejects_unsettled_or_inconsistent_source(field,value):
    s=state();s[field]=value
    with pytest.raises(ValueError):latest_seed(s)


def test_material_comparison_checks_all_fields_including_time():
    codec=GroundStateLogSimplexCodec(1)
    base=codec.encode(np.array([1e4]),np.array([[.2,.8]]),np.array([[.1,.2,.7]]))
    direction=np.ones(4)*.01;encoded=base+control.ALPHA*direction;decoded=codec.decode(encoded)
    t=dict(base_encoded_state=base,encoded_state=encoded,finite_direction=direction,
           base_residual=np.zeros(4),relaxation=np.array(control.ALPHA),step_duration_s=np.array(889.))
    for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        t[k]=np.array(getattr(decoded,k))
    same_material(t,deepcopy(t))
    other=deepcopy(t);other['step_duration_s']=np.array(890.)
    with pytest.raises(ValueError,match='same material'):same_material(t,other)
