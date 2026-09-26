import numpy as np
import pytest
from operations import probe_step21_heating_projection as probe
from eccentric_tde_observer.mixed_frame_frequency import comoving_group_radiation
from eccentric_tde_observer.multigroup_continuum import ground_state_milne_multigroup
from eccentric_tde_observer.non_gray import lte_hydrogen_helium_ionization
from eccentric_tde_observer.radiative_transfer_1d import gauss_legendre_mu_weights
from eccentric_tde_observer.source import PhysicalDomainError


def test_fixed_matter_lorentz_and_heating_affine_with_negative_weight():
    mu,w=gauss_legendre_mu_weights(4);beta=np.array([.03,-.04])
    labedge=np.geomspace(8e13,1.2e17,49);edge=np.geomspace(1e14,1e17,25)
    rng=np.random.default_rng(42);b=rng.uniform(1,2,(48,4,2))*1e-6
    a=b*(1+rng.uniform(-.02,.02,b.shape));alpha=-2.2222504218978356
    q=b+alpha*(a-b);assert np.all(q>0)
    means=[comoving_group_radiation(x,labedge,edge,mu,w,beta).mean_intensity_density for x in (a,b,q)]
    np.testing.assert_allclose(means[2],means[1]+alpha*(means[0]-means[1]),rtol=3e-14,atol=0)
    rho=np.array([1e-10,2e-10]);temp=np.array([4e4,5e4]);s=lte_hydrogen_helium_ionization(rho,temp)
    def evaluate(mean,scattering=True):
        return ground_state_milne_multigroup(rho,temp,edge,mean,s.hydrogen_neutral_fraction,
            s.hydrogen_ionized_fraction,s.helium_neutral_fraction,s.helium_singly_ionized_fraction,
            s.helium_doubly_ionized_fraction,order_per_group=4,include_electron_scattering=scattering)
    fa,fb,fq=map(evaluate,means)
    np.testing.assert_array_equal(fa.emitted_power_erg_s_cm3,fb.emitted_power_erg_s_cm3)
    predicted=fb.radiative_heating_erg_s_cm3+alpha*(fa.radiative_heating_erg_s_cm3-fb.radiative_heating_erg_s_cm3)
    np.testing.assert_allclose(fq.radiative_heating_erg_s_cm3,predicted,rtol=3e-13,atol=0)
    np.testing.assert_allclose(evaluate(means[2],False).radiative_heating_erg_s_cm3,fq.radiative_heating_erg_s_cm3,rtol=1e-14)
    with pytest.raises(PhysicalDomainError):evaluate(-means[2])


def test_projection_known_minimum():
    r=probe.heating_projection([[0,0],[3,1],[0,0],[1,1]],1,np.ones(2),np.ones(2),np.ones(2))
    assert r['alpha']==pytest.approx(-.5)
    assert r['proxy_ratio']==pytest.approx(1/np.sqrt(2))


@pytest.mark.parametrize('bad',['zero_energy','negative_mass','nonfinite','shape','unresolved'])
def test_invalid_proxy_is_not_repaired(bad):
    q=np.array([[0.,0.],[3,1],[0,0],[1,1]]);u=np.ones(2);m=np.ones(2)
    if bad=='zero_energy':u[0]=0
    if bad=='negative_mass':m[0]=-1
    if bad=='nonfinite':q[0,0]=np.nan
    if bad=='shape':q=q[:3]
    if bad=='unresolved':q[1]=q[3]
    with pytest.raises(ValueError):probe.heating_projection(q,1,np.ones(2),u,m)


def test_thermal_cost_cannot_override_radiation_guard():
    gates={k:True for k in ('positive','coefficient_l1','coefficient_sum','strict_inner',
        'maximum_improves','boundary_l1','boundary_bolometric')}
    assert all(probe.screening_gates({'gates':gates},{'proxy_ratio':.79}).values())
    assert not all(probe.screening_gates({'gates':gates},{'proxy_ratio':.8}).values())
    gates['positive']=False
    assert not all(probe.screening_gates({'gates':gates},{'proxy_ratio':.1}).values())
    gates.pop('boundary_l1')
    with pytest.raises(ValueError):probe.screening_gates({'gates':gates},{'proxy_ratio':.1})
