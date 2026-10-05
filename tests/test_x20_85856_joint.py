from copy import deepcopy
from pathlib import Path
import json
import pytest
from handoff.audit_tools.solve_x20_85856_joint import require_candidate,ORDER,RUNS
from handoff.audit_tools.verify_x20_bounded_gram import rational

def specimen():
    c=json.loads(Path('handoff/evidence/20261006-x20-85856-joint-candidate.json').read_text())
    mats=[[[rational(v) for v in row] for row in c[k]] for k in ('objective_gram','radiation_gram','heating_gram')]
    faces=[([rational(v) for v in z['normal']],rational(z['limit'])) for z in c['constraints']]
    return c,*mats,faces

def test_current_source_order_and_certificate():
    assert ORDER==((85821,16),(85821,8),(84026,16),(82989,16)) and set(RUNS)=={85821,84026,82989}
    args=specimen();assert require_candidate(*args)==args[0]['selected_coefficients']

@pytest.mark.parametrize('kind',['old_source','step','cap','coefficient','heating','full_field_claim'])
def test_changed_candidate_rejected(kind):
    c,g,gr,gh,faces=deepcopy(specimen())
    if kind=='old_source':c['source_job']=85744
    if kind=='step':c['step_safety']=.45
    if kind=='cap':c['coefficient_l1_cap']=18
    if kind=='coefficient':c['selected_coefficients'][0]+=.001
    if kind=='heating':gh[0][0]+=1
    if kind=='full_field_claim':c['full_field_nonnegative_verified']=True
    with pytest.raises(AssertionError):require_candidate(c,g,gr,gh,faces)
