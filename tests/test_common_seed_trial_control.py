import numpy as np
import pytest
from operations.common_seed_trial_control import ALPHA, common_seed_trial
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def candidate():
    codec=GroundStateLogSimplexCodec(2)
    base=codec.encode(np.array([1e4,2e4]),np.array([[.2,.8],[.4,.6]]),np.array([[.1,.2,.7],[.3,.2,.5]]))
    direction=np.linspace(-.01,.01,8)
    encoded=base+ALPHA*direction
    decoded=codec.decode(encoded)
    source=dict(base_encoded_state=base,encoded_state=encoded,finite_direction=direction,
                base_residual=np.linspace(-.1,.1,8),relaxation=np.array(ALPHA),step_duration_s=np.array(889.))
    for field in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        source[field]=np.array(getattr(decoded,field),copy=True)
    return source


def test_all_candidate_fields_are_preserved_exactly():
    s=candidate();r=common_seed_trial(s,s['base_encoded_state'],s['base_residual'])
    assert set(r)==set(s)
    for k in s:
        assert np.array_equal(r[k],s[k])
        assert not np.shares_memory(r[k],s[k])


def test_refuses_decoded_field_corruption():
    s=candidate();s['temperature_k'][0]+=1
    with pytest.raises(ValueError,match='decoded field'):common_seed_trial(s,s['base_encoded_state'],s['base_residual'])


def test_refuses_wrong_alpha_even_on_same_direction():
    s=candidate();s['relaxation']=np.array(.0078125)
    s['encoded_state']=s['base_encoded_state']+s['relaxation']*s['finite_direction']
    with pytest.raises(ValueError,match='alpha'):common_seed_trial(s,s['base_encoded_state'],s['base_residual'])
