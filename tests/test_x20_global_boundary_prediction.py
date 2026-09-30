from copy import deepcopy
import json,hashlib
from pathlib import Path
import pytest
from operations.x20_global_boundary_prediction import require_candidate


def fixture():
    root=Path(__file__).resolve().parents[1]/'handoff/evidence'
    p=root/'20261001-x20-global-boundary-candidate.json'
    return json.loads(p.read_text()),json.loads((root/'20261001-x20-global-boundary-candidate-review.json').read_text()),hashlib.sha256(p.read_bytes()).hexdigest()


def test_one_triple_is_repeated_without_frequency_variation():
    c,a,sha=fixture();rows=require_candidate(c,a,sha)
    assert len(rows)==76 and all(r==c['selected_coefficients'] for r in rows)


@pytest.mark.parametrize('damage',['hash','coefficients','safety','budget','optimality'])
def test_changed_source_or_scope_rejected(damage):
    c,a,sha=fixture();c=deepcopy(c);a=deepcopy(a)
    if damage=='hash':sha='0'*64
    elif damage=='coefficients':c['selected_coefficients'][0]+=1e-10
    elif damage=='safety':c['raw_coefficients'][0]+=1e-10
    elif damage=='budget':c['new_maps']=1
    else:a['global_optimality_claimed']=True
    with pytest.raises(ValueError):require_candidate(c,a,sha)
