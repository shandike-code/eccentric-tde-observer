import numpy as np
import pytest
from operations import replay_material_response_witnesses as r


def test_replay_rejects_wrong_sign_and_nonfinite():
    assert r.comparison([1.,2.],[1.,2.])['bitwise_equal']
    assert not r.comparison([1.,-2.],[1.,2.])['passed']
    with pytest.raises(ValueError):r.comparison([np.nan],[1.])
    with pytest.raises(ValueError):r.comparison([1.,2.],[1.])


def source():
    return dict(job_id=80195,diagnostic_windows_passed=True,final_summary_present=True,
        accepted_outer_steps=20,new_material_steps=0,original_all_16_pass=False,
        baseline_replaced=False,production_signal_reducer_reused=False)


@pytest.mark.parametrize('key,value',[('job_id',80052),('diagnostic_windows_passed',False),
    ('final_summary_present',False),('new_material_steps',1),('baseline_replaced',True),('original_all_16_pass',True)])
def test_only_complete_independently_audited_source(key,value):
    a=source();r.require_source(a);a[key]=value
    with pytest.raises(RuntimeError):r.require_source(a)
