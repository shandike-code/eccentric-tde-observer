from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
import json
import pytest
from handoff.audit_tools.solve_x20_83104_constrained import constrained_qp,verify
from handoff.audit_tools.verify_x20_bounded_gram import rational
from operations.x20_83104_constrained_prediction import require_candidate


def gram(t):
    t=list(map(F,t));return [[sum(v*v for v in t),*[-v for v in t]]]+[[-t[i]]+[F(i==j) for j in range(3)] for i in range(3)]


def test_exact_active_constraint_and_dual_certificate():
    g=gram([2,1,-1]);faces=[([F(1),F(0),F(0)],F(1,2))]
    r=constrained_qp(g,faces);verify(g,faces,r)
    assert r['coefficients']==[F(1,2),F(1),F(-1)] and r['multipliers']==[F(3)]
    r['multipliers'][0]+=1
    with pytest.raises(AssertionError):verify(g,faces,r)


def test_interior_optimum_and_nonpositive_gram_rejection():
    g=gram([1,2,3]);r=constrained_qp(g,[]);verify(g,[],r)
    assert r['coefficients']==[1,2,3]
    g[3][3]=0
    with pytest.raises(ValueError,match='nonpositive'):constrained_qp(g,[])


def specimen():
    c=json.loads(Path('handoff/evidence/20261002-x20-83104-constrained-candidate.json').read_text())
    mats=[[[rational(v) for v in row] for row in c[k]] for k in ('objective_gram','radiation_gram','heating_gram')]
    faces=[([rational(v) for v in row['normal']],rational(row['limit'])) for row in c['constraints']]
    return c,*mats,faces


def test_frozen_current_candidate_certificate():
    args=specimen();assert require_candidate(*args)==[-5.171447326928601,-2.028552673071399,.9]

@pytest.mark.parametrize('kind',['scope','coefficient','gram','constraint','multiplier','safety'])
def test_changed_certificate_is_rejected(kind):
    c,g,gr,gh,faces=deepcopy(specimen())
    if kind=='scope':c['full_field_nonnegative_verified']=True
    if kind=='coefficient':c['selected_coefficients'][0]+=.001
    if kind=='gram':g[0][0]+=1
    if kind=='constraint':faces[0]=(faces[0][0],faces[0][1]+1)
    if kind=='multiplier':c['multipliers_exact'][0]['numerator']='0'
    if kind=='safety':c['step_safety']=.95
    with pytest.raises((ValueError,AssertionError)):require_candidate(c,g,gr,gh,faces)
