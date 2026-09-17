import numpy as np
import pytest
from operations.conservative_residual_diagnostic import equation_residual
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from eccentric_tde_observer.radiation_matter_feedback import ground_state_material_temperature_from_specific_energy_k
from eccentric_tde_observer.source import PhysicalDomainError


def setup():
    codec=GroundStateLogSimplexCodec(2)
    h=np.array([[.3,.7],[.2,.8]])
    he=np.array([[.2,.3,.5],[.1,.2,.7]])
    x=codec.encode([1e5,2e5],h,he)
    state=codec.decode(x)
    return codec,x,state


def test_same_physical_zero_as_legacy_response():
    codec,x,state=setup();e=state.specific_material_energy_erg_g
    r=equation_residual(codec,x,.5*e,e,.5*e,state.hydrogen_fraction,state.helium_fraction)
    np.testing.assert_allclose(r,0,atol=2e-14)
    t=ground_state_material_temperature_from_specific_energy_k(e,state.hydrogen_fraction,state.helium_fraction)
    legacy=codec.encode(t,state.hydrogen_fraction,state.helium_fraction)-x
    np.testing.assert_allclose(legacy,0,atol=2e-14)


def test_nonphysical_target_does_not_require_temperature_floor():
    codec,x,state=setup();e=state.specific_material_energy_erg_g
    with pytest.raises(PhysicalDomainError):
        ground_state_material_temperature_from_specific_energy_k(-e,state.hydrogen_fraction,state.helium_fraction)
    r=equation_residual(codec,x,e,e,-2*e,state.hydrogen_fraction,state.helium_fraction)
    np.testing.assert_allclose(r[:,0],2)
    np.testing.assert_allclose(r[:,1:],0,atol=2e-14)
    assert np.all(codec.decode(x).temperature_k>0)


def test_population_error_is_not_hidden_by_balanced_energy():
    codec,x,state=setup();e=state.specific_material_energy_erg_g
    h=state.hydrogen_fraction.copy();h[0]=[.5,.5]
    r=equation_residual(codec,x,e,e,np.zeros(2),h,state.helium_fraction)
    assert abs(r[0,1])>.1
    np.testing.assert_allclose(r[:,0],0,atol=1e-14)


@pytest.mark.parametrize('scale',[np.array([0.,1.]),np.array([np.nan,1.]),np.ones(3)])
def test_invalid_scale_rejected(scale):
    codec,x,state=setup();e=state.specific_material_energy_erg_g
    with pytest.raises(ValueError):equation_residual(codec,x,e,scale,np.zeros(2),state.hydrogen_fraction,state.helium_fraction)
