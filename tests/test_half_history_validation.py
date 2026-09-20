from copy import deepcopy
import numpy as np
import pytest
from operations.validate_half_history_candidate import verify_scan, initialized_identity, EXPECTED_CHECKS, SOURCES


def inputs():
    basis=[{'path':str(i),'sha256':'h'+str(i)} for i in range(4)]
    declaration={'basis':basis,'source_order':list(SOURCES),'new_maps':0,'candidate_write_budget':0,
                 'coefficient_l1_cap':32.,'physical_dt_changed':False}
    prediction={'algebraic_feasibility':True,'checks':dict.fromkeys(EXPECTED_CHECKS,True),
                'actual_map_performed':False,'candidate_written':False,'best_measured_residual':8e-5,
                'direction':{'gamma':-.5,'feasible_interval':[-1.,0.],'coefficients':[.5,.5],
                             'coefficient_l1':1.,'direction_resolution_ratio':2.},
                'prediction':{'predicted_residual':3e-5,'predicted_boundary_l1':1e-5,
                              'predicted_boundary_bolometric':1e-6,'candidate_negative_count':0,
                              'predicted_map_negative_count':0,'minimum_candidate':0.,'minimum_predicted_map':0.}}
    return prediction,declaration,basis


def test_valid_positive_mixture():
    assert verify_scan(*inputs())==-.5


@pytest.mark.parametrize('fault',['missing_gate','failed_gate','basis','scope','coefficients','interval','residual','negative','nan'])
def test_scan_rejects_false_pass_claims(fault):
    p,d,b=inputs()
    if fault=='missing_gate':p['checks'].pop('boundary_spectrum_pass')
    if fault=='failed_gate':p['checks']['boundary_spectrum_pass']=False
    if fault=='basis':d['basis']=list(reversed(b))
    if fault=='scope':d['new_maps']=1
    if fault=='coefficients':p['direction']['coefficients']=[.6,.4]
    if fault=='interval':p['direction']['feasible_interval']=[0,1]
    if fault=='residual':p['prediction']['predicted_residual']=9e-5
    if fault=='negative':p['prediction']['candidate_negative_count']=1
    if fault=='nan':p['prediction']['predicted_residual']=np.nan
    with pytest.raises(ValueError):verify_scan(p,d,b)


def initialized():
    return {'status':'radiation','history':[],'current_slot':0,'current_sha256':'seed','active_map':None}


def test_initialization_preserves_whole_trial_and_empty_history():
    trial={'encoded_state':np.ones(8),'temperature_k':np.ones(2),'relaxation':np.array(.001953125)}
    initialized_identity(initialized(),{'sha256':'seed'},trial,deepcopy(trial))
    wrong=deepcopy(trial);wrong['relaxation']=np.array(.0625)
    with pytest.raises(ValueError,match='relaxation'):initialized_identity(initialized(),{'sha256':'seed'},trial,wrong)


@pytest.mark.parametrize('fault',['history','seed','slot','active','pending','status'])
def test_initialization_refuses_inherited_or_uncommitted_state(fault):
    s=initialized()
    if fault=='history':s['history']=[{'iteration':1}]
    if fault=='seed':s['current_sha256']='other'
    if fault=='slot':s['current_slot']=1
    if fault=='active':s['active_map']={'iteration':1}
    if fault=='pending':s['pending_feedback']={'pair':1}
    if fault=='status':s['status']='failed'
    with pytest.raises(RuntimeError):initialized_identity(s,{'sha256':'seed'},{'x':np.ones(1)},{'x':np.ones(1)})
