from copy import deepcopy
import numpy as np
import pytest
from operations.prepare_half_four_map_feedback import validated_four_map_seed, EXPECTED_VALIDATION


def inputs():
    row={'input_sha256':'input','output_path':'state_1.dat','output_sha256':'output',
         'residual':2.44e-5,'boundary_l1':3.74e-5,'boundary_bolometric':3.18e-5,
         'maximum_worker_rss_mib':3501.}
    state={'status':'radiation','history':[row],'slots':['state_0.dat','state_1.dat','state_2.dat'],
           'current_slot':1,'current_sha256':'output','active_map':None}
    status={'status':'complete','new_maps':1,'extrapolation_validated':True}
    result={'actual_map':deepcopy(row),'candidate':{'sha256':'input'},'extrapolation_validated':True,
        'validation_checks':dict.fromkeys(EXPECTED_VALIDATION,True),'full_intensity_prediction_error_evaluated':True,
        'full_field_error':{'prediction_error_resolved':True,'error_over_actual_defect_l2':3.36e-10,
                            'candidate_reconstruction_exact':True},'feedback_evaluated':False,'accepted_material_step':False}
    declaration={'maximum_new_maps':1,'maximum_candidate_writes':1,'workers':16,'candidate_clipping':False,
        'material_changed':False,'physical_dt_changed':False,'full_field_prediction_error_fraction_of_actual_defect_limit':.01,
        'prediction':{'best_measured_residual':3.023e-5}}
    return state,status,result,declaration


def test_only_latest_actual_output_can_seed_new_pair_without_inheriting_history():
    args=inputs();before=deepcopy(args)
    seed=validated_four_map_seed(*args)
    assert seed['sha256']=='output' and seed['path']=='state_1.dat'
    assert args==before


@pytest.mark.parametrize('fault',['old_five_gates','reconstruction_flag','reconstruction_fact','extra_gate',
    'truthy_gate','scope','clipping','dt','material','already_feedback','stale_output','input_as_seed',
    'partial','pending','two_maps','false_improvement','memory','nan','loose_error','changed_tolerance'])
def test_rejects_incomplete_or_numerically_false_validation(fault):
    s,st,r,d=inputs()
    if fault=='old_five_gates':r['validation_checks'].pop('candidate_reconstruction_exact')
    if fault=='reconstruction_flag':r['validation_checks']['candidate_reconstruction_exact']=False
    if fault=='reconstruction_fact':r['full_field_error']['candidate_reconstruction_exact']=False
    if fault=='extra_gate':r['validation_checks']['invented']=True
    if fault=='truthy_gate':r['validation_checks']['candidate_reconstruction_exact']=1
    if fault=='scope':d['maximum_candidate_writes']=2
    if fault=='clipping':d['candidate_clipping']=True
    if fault=='dt':d['physical_dt_changed']=True
    if fault=='material':d['material_changed']=True
    if fault=='already_feedback':r['feedback_evaluated']=True
    if fault=='stale_output':s['current_sha256']='other'
    if fault=='input_as_seed':s['current_slot']=0;s['current_sha256']='input'
    if fault=='partial':s['active_map']={'iteration':2}
    if fault=='pending':s['pending_feedback']={'pair':1}
    if fault=='two_maps':s['history'].append(deepcopy(s['history'][0]))
    if fault=='false_improvement':r['actual_map']['residual']=s['history'][0]['residual']=4e-5
    if fault=='memory':r['actual_map']['maximum_worker_rss_mib']=s['history'][0]['maximum_worker_rss_mib']=7000.
    if fault=='nan':r['full_field_error']['error_over_actual_defect_l2']=np.nan
    if fault=='loose_error':r['full_field_error']['error_over_actual_defect_l2']=.02
    if fault=='changed_tolerance':d['full_field_prediction_error_fraction_of_actual_defect_limit']=.1
    with pytest.raises(ValueError):validated_four_map_seed(s,st,r,d)
