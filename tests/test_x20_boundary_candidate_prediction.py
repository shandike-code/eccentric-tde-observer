from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from operations.x20_boundary_candidate_prediction import require_candidate


def fixture():
    root=Path(__file__).resolve().parents[1]/'handoff/evidence'
    p=root/'20261001-x20-boundary-constrained-selection.json'
    return json.loads(p.read_text()),json.loads((root/'20261001-x20-boundary-candidate-feasibility.json').read_text()),hashlib.sha256(p.read_bytes()).hexdigest()


def test_finite_candidate_preserves_unsuccessful_optimization():
    candidate,audit,sha=fixture()
    assert len(require_candidate(candidate,audit,sha))==76
    assert candidate['solver_success'] is False


@pytest.mark.parametrize('change',['hash','coefficient','factor','budget','claim_optimality'])
def test_wrong_identity_or_scope_is_rejected(change):
    candidate,audit,sha=fixture();candidate=deepcopy(candidate);audit=deepcopy(audit)
    if change=='hash':sha='0'*64
    elif change=='coefficient':candidate['selected_coefficients'][24][0]+=1e-10
    elif change=='factor':candidate['block_factors'][24]=1.1
    elif change=='budget':candidate['new_maps']=1
    elif change=='claim_optimality':audit['global_optimality_claimed']=True
    with pytest.raises(ValueError):require_candidate(candidate,audit,sha)
