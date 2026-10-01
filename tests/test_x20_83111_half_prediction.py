import json
from pathlib import Path
from copy import deepcopy
import pytest
from operations.x20_83111_half_prediction import reviewed_half_coefficients


def evidence():return json.loads(Path('handoff/evidence/20261002-x20-constrained-prediction-83111-review.json').read_text())


def test_explicit_current_half_selection():
    a=evidence();assert reviewed_half_coefficients(a,a['coefficients'])==[-2.5857236634643006,-1.0142763365356995,.45]

@pytest.mark.parametrize('damage',['source','review','failure','l2','linf','negative','boundary','coefficient','radiation'])
def test_missing_premise_stops_selection(damage):
    a=deepcopy(evidence());c=list(a['coefficients']);z=a['result']
    if damage=='source':a['source_job']=82686
    if damage=='review':a['small_problem_kkt_reverified']=False
    if damage=='failure':z['checks']['full_l2_benefit']=False
    if damage=='l2':z['l2_ratios'][2]=.81
    if damage=='linf':z['linf_ratios'][2]=1.001
    if damage=='negative':z['minima'][2]=-5e-324
    if damage=='boundary':z['boundary'][2]['boundary_l1']=z['boundary'][0]['boundary_l1']*1.01
    if damage=='coefficient':c[0]+=.01
    if damage=='radiation':z['boundary'][2]['residual']=1.01e-4
    with pytest.raises(ValueError):reviewed_half_coefficients(a,c)
