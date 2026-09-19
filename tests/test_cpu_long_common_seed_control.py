import numpy as np
import pytest
from operations import cpu_long_common_seed_control as control
from eccentric_tde_observer.coupled_material_newton_krylov import GroundStateLogSimplexCodec


def candidate():
    codec=GroundStateLogSimplexCodec(2)
    base=codec.encode(np.array([1e4,2e4]),np.array([[.2,.8],[.4,.6]]),np.array([[.1,.2,.7],[.3,.2,.5]]))
    direction=np.linspace(-.01,.01,8)
    encoded=base+control.ALPHA*direction
    decoded=codec.decode(encoded)
    source=dict(base_encoded_state=base,encoded_state=encoded,finite_direction=direction,
                base_residual=np.linspace(-.1,.1,8),relaxation=np.array(control.ALPHA),step_duration_s=np.array(889.))
    for field in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g'):
        source[field]=np.array(getattr(decoded,field),copy=True)
    return source


def test_all_adjacent_candidate_fields_are_preserved():
    s=candidate();r=control.common_seed_trial(s,s['base_encoded_state'],s['base_residual'])
    for k in s:assert np.array_equal(r[k],s[k])


def test_resource_guard_preserved(monkeypatch):
    monkeypatch.setenv('SLURM_JOB_ID','test')
    monkeypatch.setenv('SLURM_CPUS_PER_TASK','32')
    monkeypatch.setenv('SLURM_MEM_PER_NODE',str(128*1024))
    control.pipeline.require_allocation(control.WORKERS)
    with pytest.raises(RuntimeError,match='6 GiB'):
        control.pipeline.require_allocation(32)


def test_refuses_unchanged_alpha_with_wrong_decoded_state():
    s=candidate();s['temperature_k'][0]+=1
    with pytest.raises(ValueError,match='decoded field'):
        control.common_seed_trial(s,s['base_encoded_state'],s['base_residual'])
