import json
from pathlib import Path
from copy import deepcopy
from fractions import Fraction as F
import numpy as np
import pytest
from operations.x20_83080_constrained_basis import require_source
from operations.x20_window_basis import basis_moments
from handoff.audit_tools.diagnose_x20_83080_step_interval import quadratic,constrained_minimum


def source():
    a=json.loads(Path('handoff/evidence/20261001-x20-quarter-prediction-83080-review.json').read_text())
    d=dict(job_id='83080',git_commit='4bfd4004e27c55bee43d702acbfd144a6096b8f7',source_job=83063,sign_audit_job=83075,shape=[9632,32,4096],step_multiplier=.25,global_coefficients=[0.,-1.8,.9485574831263044],fields=[{}]*8)
    return a,d


def test_current_rejected_source_is_accepted_as_diagnostic_input():require_source(*source())

@pytest.mark.parametrize('change',['wrong_job','missing_field','false_positive','nonnegative_failure','step','commit'])
def test_wrong_premise_rejected(change):
    a,d=deepcopy(source())
    if change=='wrong_job':a['source_job']=82686
    if change=='missing_field':d['fields'].pop()
    if change=='false_positive':a['result']['checks']['full_l2_benefit']=True
    if change=='nonnegative_failure':a['result']['checks']['full_field_nonnegative']=False
    if change=='step':d['step_multiplier']=.5
    if change=='commit':d['git_commit']='0'*40
    with pytest.raises(ValueError):require_source(a,d)


def test_three_point_quadratic_and_interval_minimum():
    # 精确函数2t²-3t+4；区间约束只作用于解析最小位置，不改辐射数组。
    f=lambda t:2*t*t-3*t+4
    a,b,c=quadratic(f(F(0)),f(F(1,8)),f(F(1,4)))
    assert (a,b,c)==(2,-3,4)
    t,v=constrained_minimum(a,b,c,F(1,4))
    assert t==F(1,4) and v==f(t)/4
    assert constrained_minimum(a,b,c,F(1))[0]==F(3,4)
    with pytest.raises(ValueError):constrained_minimum(F(-1),b,c,F(1))


def test_nonfinite_fields_fail():
    fields=[np.ones((2,2,2)) for _ in range(8)]
    fields[5][0,0,0]=np.nan
    with pytest.raises(ValueError):basis_moments(fields)
