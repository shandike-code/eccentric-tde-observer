import json
from pathlib import Path
from copy import deepcopy
import pytest
from operations.x20_83063_quarter_prediction import backtracked_coefficients

def evidence():return json.loads(Path('handoff/evidence/20261001-x20-subnormal-83075-review.json').read_text())

def test_audited_local_bound_selects_quarter_only():
    assert backtracked_coefficients(evidence(),[0.,-7.2,3.7942299325052176])==[0.,-1.8,.9485574831263044]

@pytest.mark.parametrize('damage',['job','count','bound','half','full','review'])
def test_changed_premise_is_rejected(damage):
    a=deepcopy(evidence())
    if damage=='job':a['job_id']=82740
    if damage=='count':a['counts'][0]['negative_count']-=1
    if damage=='bound':a['local_upper_fraction']=.25
    if damage=='half':a['counts'][2]['half']['-1']=0
    if damage=='full':a['counts'][0]['full']['-1']=0
    if damage=='review':a['integer_certificates_verified']=False
    with pytest.raises(ValueError):backtracked_coefficients(a,[0.,-7.2,3.7942299325052176])
