import numpy as np
import pytest
from operations import common_outer_step17 as step


def fixture():
    codec=step.GroundStateLogSimplexCodec(2)
    x=codec.encode(np.array([1e4,2e4]),np.array([[.5,.5],[.4,.6]]),np.array([[.4,.3,.3],[.2,.3,.5]]))
    d=codec.decode(x);t={k:np.array(getattr(d,k)) for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    t.update(encoded_state=x,base_encoded_state=x.copy(),base_residual=np.ones_like(x)*.01,finite_direction=np.ones_like(x)*.01,
        relaxation=np.array(0.),phase_index=np.array(0),step_duration_s=np.array(3.),density_g_cm3=np.ones(2))
    return t,{'step_duration_s':np.array([3.]),'density_g_cm3':np.ones((1,2))}


def test_rebase_accepts_iterate_not_target_and_preserves_physical_time():
    accepted,old=fixture();r=np.arange(8)*.001
    base=step.rebase_trial(accepted,r,old);trial=step.make_candidate(base,r)
    assert np.array_equal(base['encoded_state'],accepted['encoded_state'])
    assert np.array_equal(trial['encoded_state'],accepted['encoded_state']+r/64)
    assert float(trial['relaxation'])==1/64
    for k in ('phase_index','step_duration_s','density_g_cm3'):
        assert np.array_equal(trial[k],accepted[k])
    step.bridge.validate_identity(trial,base,r,old)


@pytest.mark.parametrize('mutation',['direction','denominator','nonzero_base','trust'])
def test_invalid_rebase_or_large_trial_rejected(mutation):
    base,old=fixture();r=base['base_residual'].copy()
    if mutation=='direction':base['finite_direction']*=2
    if mutation=='denominator':base['base_residual']*=2
    if mutation=='nonzero_base':base['relaxation']=np.array(1/64)
    if mutation=='trust':
        r*=10000;base['base_residual']=r.copy();base['finite_direction']=r.copy()
    with pytest.raises(ValueError):step.make_candidate(base,r)


def test_physical_dt_cannot_rebase():
    t,old=fixture();old['step_duration_s'][0]=4
    with pytest.raises(ValueError):step.rebase_trial(t,t['base_residual'],old)
