import json
from copy import deepcopy
from pathlib import Path
import pytest
from operations.x20_historical_half_prediction import backtracked_coefficients


def evidence():
    return json.loads(Path('handoff/evidence/20261001-x20-subnormal-82740-review.json').read_text())


def test_exact_audit_supports_only_global_half_backtrack():
    assert backtracked_coefficients(evidence(),[-7.2,1.7918845939882053,0.])==[-3.6,.8959422969941027,0.]


def test_negative_half_or_missing_points_reject():
    for mutation in ('sign','count'):
        a=deepcopy(evidence())
        if mutation=='sign':a['counts'][0]['half']['-1']=1
        else:a['counts'][0]['negative_count']-=1
        with pytest.raises(ValueError):backtracked_coefficients(a,[-7.2,1.7918845939882053,0.])


def test_unreviewed_or_changed_direction_reject():
    a=evidence();a['integer_certificates_verified']=False
    with pytest.raises(ValueError):backtracked_coefficients(a,[-7.2,1.7918845939882053,0.])
    with pytest.raises(ValueError):backtracked_coefficients(evidence(),[-8.,1.9,0.])
