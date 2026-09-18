import numpy as np
import pytest
from operations.baseline_zero_control import zero_trial
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def source():
    codec=GroundStateLogSimplexCodec(2)
    base=codec.encode(np.array([1e4,2e4]),np.array([[.2,.8],[.4,.6]]),np.array([[.1,.2,.7],[.3,.2,.5]]))
    legacy=np.linspace(-.1,.1,8);direction=np.linspace(-.01,.01,8)
    return dict(base_encoded_state=base,encoded_state=base+.0625*direction,finite_direction=direction,
                base_residual=legacy,relaxation=np.array(.0625),temperature_k=np.array([1e4,2e4]),
                phase_index=np.array(1),step_duration_s=np.array(889.),density_g_cm3=np.array([1e-8,2e-8]))


def test_zero_is_exact_base_with_direction_and_time_preserved():
    s=source();z=zero_trial(s,s['base_encoded_state'],s['base_residual'])
    assert float(z['relaxation'])==0
    assert np.array_equal(z['encoded_state'],s['base_encoded_state'])
    for k in ('base_encoded_state','finite_direction','base_residual','phase_index','step_duration_s','density_g_cm3'):
        assert np.array_equal(z[k],s[k])
    assert np.all(z['temperature_k']>0)
    assert float(s['relaxation'])==.0625


def test_zero_control_refuses_unrelated_base():
    s=source()
    with pytest.raises(ValueError,match='different archived'):zero_trial(s,s['base_encoded_state']+.01,s['base_residual'])


def test_zero_control_refuses_corrupt_source_identity():
    s=source();s['encoded_state']=s['encoded_state']+.01
    with pytest.raises(ValueError,match='direction identity'):zero_trial(s,s['base_encoded_state'],s['base_residual'])
