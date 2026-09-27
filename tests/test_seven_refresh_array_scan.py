import math
import numpy as np
import pytest
from operations.scan_step21_seven_refresh_arrays import frequency_stats

def test_all_angles_depths_and_signs_contribute():
    a=np.array([[1.,2.],[3.,4.]])
    b=np.array([[2.,1.],[3.,6.]])
    got=frequency_stats(a,b)
    assert got==dict(square=6.,maximum=2.,minimum_input=1.,minimum_output=1.)
    assert math.sqrt(got['square'])!=abs(float((b-a).sum()))

@pytest.mark.parametrize('bad',[np.array([[np.nan]]),np.array([[-1.]]),np.ones((2,2))])
def test_nonphysical_or_wrong_shape_rejected(bad):
    with pytest.raises(ValueError):frequency_stats(np.ones((1,1)),bad)


def test_refreshed_source_rejects_old_or_mislabeled_fields():
    from copy import deepcopy
    from operations.scan_step21_seven_refresh_arrays import check_refreshed_source
    d=dict(source_job_id=78161,refreshed_halo=True,source_run='outputs/hpc/step21-seven-short-validation-20260927',cases={'control':{'input':{'sha256':'new-x'},'output':{'sha256':'new-y'}}},original_77577_pair=[{'sha256':'old-x'},{'sha256':'old-y'}])
    check_refreshed_source(d)
    for key,value in [('source_job_id',77577),('refreshed_halo',False),('source_run','old')]:
        bad=deepcopy(d);bad[key]=value
        with pytest.raises(RuntimeError,match='refreshed'):check_refreshed_source(bad)
    for key,sha in [('input','old-x'),('output','old-y')]:
        bad=deepcopy(d);bad['cases']['control'][key]['sha256']=sha
        with pytest.raises(RuntimeError,match='stale'):check_refreshed_source(bad)
