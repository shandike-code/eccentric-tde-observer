import numpy as np
import pytest
from operations.review_small_step_evidence import trial_identity, classify_pair, vector_secant_check, Snapshot, decoded_field_audit


def test_config_label_cannot_replace_actual_trial():
    base=np.ones(8);direction=np.arange(8,dtype=float);legacy=np.ones(8)
    trial=dict(base_encoded_state=base,base_residual=legacy,finite_direction=direction,encoded_state=base+.0625*direction,relaxation=.0625)
    with pytest.raises(ValueError,match='alpha'):trial_identity(trial,base,legacy,.015625)
    trial['relaxation']=.015625
    with pytest.raises(ValueError,match='does not equal'):trial_identity(trial,base,legacy,.015625)


def test_same_length_opposite_secants_are_not_linear():
    result=vector_secant_check(np.array([1.,0]),np.array([-.5,0]),1.,.5)
    assert result['relative_vector_difference']==2
    assert not result['establishes_derivative_by_itself']


def test_zero_secant_does_not_create_a_signal_floor():
    assert vector_secant_check(np.zeros(4),np.zeros(4),1.,.5)['relative_vector_difference'] is None


def test_domain_failure_with_unconverged_radiation_is_only_observed():
    result=classify_pair([3e-4,2.9e-4],{},[56,56])
    assert result['response_domain_failure_observed']
    assert not result['both_radiation_endpoints_below_relaxed_gate']
    assert not result['exact_inner_error_bound_available']
    assert not result['formal_acceptance']


@pytest.mark.parametrize('radiation',[[1e-4,1e-4],[2.5e-4,2.5e-4],[float('nan'),1e-4]])
def test_radiation_gate_alone_never_accepts(radiation):
    assert not classify_pair(radiation,{'candidate_l2_contraction_pass':True},[0,0])['formal_acceptance']


def test_snapshot_rejects_large_rotating_state(tmp_path):
    with pytest.raises(ValueError,match='rotating'):Snapshot(tmp_path).save('outputs/test.dat')


def test_snapshot_preserves_first_atomic_read_and_rejects_conflict(tmp_path,monkeypatch):
    import operations.review_small_step_evidence as module
    monkeypatch.setattr(module,'ROOT',tmp_path)
    source=tmp_path/'state.json';source.write_text('{"history": []}')
    snap=Snapshot(tmp_path/'audit');dest=snap.save('state.json')
    source.write_text('{"history": [1]}')
    assert snap.save('state.json').read_text()=='{"history": []}'
    with pytest.raises(RuntimeError,match='conflicting'):snap.save('state.json','0'*64)


def test_archived_energy_metadata_cannot_hide_a_changed_native_temperature():
    from types import SimpleNamespace
    names=('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')
    t={k:np.ones(2) for k in names};d=SimpleNamespace(**{k:v.copy() for k,v in t.items()})
    t['specific_material_energy_erg_g']=np.nextafter(t['specific_material_energy_erg_g'],np.inf)
    report=decoded_field_audit(t,d)
    assert report['native_input_identity_pass']
    assert report['specific_material_energy_erg_g']['maximum_absolute_difference']>0
    t['temperature_k']=np.nextafter(t['temperature_k'],np.inf)
    assert not decoded_field_audit(t,d)['native_input_identity_pass']
