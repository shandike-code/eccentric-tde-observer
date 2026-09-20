from copy import deepcopy
import numpy as np
import pytest
from operations.prepare_half_history_feedback import validated_half_seed,EXPECTED_VALIDATION


def fixture():
    row={'input_sha256':'x','output_path':'state_1.dat','output_sha256':'y','residual':3e-5,
         'boundary_l1':1e-5,'boundary_bolometric':1e-6,'maximum_worker_rss_mib':3500.}
    s={'status':'radiation','history':[row],'slots':['state_0.dat','state_1.dat','state_2.dat'],
       'current_slot':1,'current_sha256':'y','active_map':None}
    status={'status':'complete','new_maps':1,'extrapolation_validated':True}
    r={'actual_map':deepcopy(row),'candidate':{'sha256':'x'},'extrapolation_validated':True,
       'validation_checks':dict.fromkeys(EXPECTED_VALIDATION,True),
       'full_intensity_prediction_error_evaluated':True,
       'full_field_error':{'prediction_error_resolved':True,'error_over_actual_defect_l2':1e-11},
       'feedback_evaluated':False,'accepted_material_step':False}
    d={'maximum_new_maps':1,'material_changed':False,'physical_dt_changed':False,
       'full_field_prediction_error_fraction_of_actual_defect_limit':.01,
       'prediction':{'best_measured_residual':7e-5}}
    return s,status,r,d


def test_seed_is_latest_actual_output_and_does_not_mutate_history():
    args=fixture();before=deepcopy(args)
    assert validated_half_seed(*args)['sha256']=='y'
    assert args==before


@pytest.mark.parametrize('case',['missing_gate','extra_gate','failed_gate','scalar_only','stale_output',
    'partial','wrong_dt','already_feedback','ratio_large','ratio_nan','changed_tolerance','false_memory_pass'])
def test_seed_refuses_unvalidated_or_different_experiments(case):
    s,st,r,d=fixture()
    if case=='missing_gate':r['validation_checks'].pop('worker_memory_pass')
    if case=='extra_gate':r['validation_checks']['invented']=True
    if case=='failed_gate':r['validation_checks']['worker_memory_pass']=False
    if case=='scalar_only':r['full_intensity_prediction_error_evaluated']=False
    if case=='stale_output':s['current_sha256']='z'
    if case=='partial':s['active_map']={'iteration':2}
    if case=='wrong_dt':d['physical_dt_changed']=True
    if case=='already_feedback':r['feedback_evaluated']=True
    if case=='ratio_large':r['full_field_error']['error_over_actual_defect_l2']=.011
    if case=='ratio_nan':r['full_field_error']['error_over_actual_defect_l2']=np.nan
    if case=='changed_tolerance':d['full_field_prediction_error_fraction_of_actual_defect_limit']=.1
    if case=='false_memory_pass':
        r['actual_map']['maximum_worker_rss_mib']=7000.;s['history'][0]['maximum_worker_rss_mib']=7000.
    with pytest.raises(ValueError):validated_half_seed(s,st,r,d)
