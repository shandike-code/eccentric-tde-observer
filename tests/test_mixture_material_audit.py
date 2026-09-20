from copy import deepcopy
import numpy as np
import pytest
from operations.audit_mixture_material_residual import zero_matches_candidate,verify_gate_inventory,REQUIRED_GATES


def fixture():
    a={k:np.ones(8) for k in ('base_encoded_state','base_residual','finite_direction','density_g_cm3')}
    a.update(phase_index=np.array(1367),step_duration_s=np.array(889.),relaxation=np.array(.001953125))
    a['encoded_state']=a['base_encoded_state']+.001953125*a['finite_direction']
    z=deepcopy(a);z['relaxation']=np.array(0.);z['encoded_state']=z['base_encoded_state'].copy()
    return z,a


def test_zero_control_is_frozen_candidate_base():zero_matches_candidate(*fixture())


@pytest.mark.parametrize('field',['encoded_state','base_residual','finite_direction','density_g_cm3','phase_index','step_duration_s','relaxation'])
def test_wrong_zero_baseline_is_rejected(field):
    z,a=fixture();z[field]=z[field]+1
    with pytest.raises(ValueError):zero_matches_candidate(z,a)


def test_audit_does_not_require_exactly_two_failed_gates():
    gates=dict.fromkeys(REQUIRED_GATES,True)
    assert verify_gate_inventory({'gate_checks':gates})==[]
    gates['last_two_atomic_heating_pass']=False
    assert verify_gate_inventory({'gate_checks':gates})==['last_two_atomic_heating_pass']


@pytest.mark.parametrize('fault',['missing','extra','nonboolean'])
def test_incomplete_or_ambiguous_gate_inventory_is_rejected(fault):
    g=dict.fromkeys(REQUIRED_GATES,True)
    if fault=='missing':g.pop('inner_noise_resolved_pass')
    if fault=='extra':g['new']=True
    if fault=='nonboolean':g['inner_noise_resolved_pass']='true'
    with pytest.raises(ValueError):verify_gate_inventory({'gate_checks':g})
