import numpy as np
import pytest
from operations.recover_equation_baseline import recover_equation_residual
from operations.conservative_residual_diagnostic import equation_residual
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec
from eccentric_tde_observer.source import PhysicalDomainError


def states():
    codec=GroundStateLogSimplexCodec(2)
    x=codec.encode([1e5,2e5],[[.3,.7],[.2,.8]],[[.2,.3,.5],[.1,.2,.7]])
    target=codec.encode([9e4,2.1e5],[[.4,.6],[.25,.75]],[[.25,.3,.45],[.12,.2,.68]])
    return codec,x,target


def test_conversion_matches_direct_energy_and_population_equations():
    codec,x,target=states();t=codec.decode(target)
    scale=np.array([1e13,2e13]);old=np.array([2e13,3e13])
    direct=equation_residual(codec,x,old,scale,t.specific_material_energy_erg_g-old,t.hydrogen_fraction,t.helium_fraction)
    recovered=recover_equation_residual(codec,x,target-x,scale)
    np.testing.assert_allclose(recovered,direct,rtol=2e-13,atol=2e-14)


def test_ionization_change_is_retained_when_thermal_coordinate_is_unchanged():
    codec,x,_=states();r=np.zeros_like(x);r[1]=.4
    result=recover_equation_residual(codec,x,r,np.ones(2)*1e13)
    assert result[0,0] < 0 and result[0,1]==-.4
    np.testing.assert_array_equal(result[1],np.zeros(4))


def test_zero_legacy_residual_recovers_zero():
    codec,x,_=states()
    np.testing.assert_array_equal(recover_equation_residual(codec,x,np.zeros_like(x),np.ones(2)),np.zeros((2,4)))


@pytest.mark.parametrize('scale',[[0,1],[np.nan,1],[1]])
def test_invalid_scale_rejected(scale):
    codec,x,t=states()
    with pytest.raises(ValueError):recover_equation_residual(codec,x,t-x,scale)


def test_nonfinite_missing_response_is_not_convertible():
    codec,x,_=states();r=np.zeros_like(x);r[0]=np.nan
    with pytest.raises(ValueError):recover_equation_residual(codec,x,r,np.ones(2))


def test_target_on_simplex_boundary_is_rejected_without_floor():
    codec,x,_=states();r=np.zeros_like(x);r[1]=1000
    with pytest.raises(PhysicalDomainError):recover_equation_residual(codec,x,r,np.ones(2))
