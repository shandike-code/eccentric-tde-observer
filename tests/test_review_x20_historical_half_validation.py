import json
from pathlib import Path
import pytest
from handoff.audit_tools.review_x20_historical_half_validation import actual_numbers


def original_fixture():
    root=Path('outputs/review-20260925/x20-global-boundary-validation-82515-received')
    if not root.exists():root=Path('outputs/hpc/x20-global-boundary-validation-20261001')
    assert root.exists(), 'previously audited real artifact required'
    v=json.loads((root/'validation.json').read_text())
    d=json.loads((root/'declaration.json').read_text())
    return v,d['source_row']


def test_previous_real_stats_pass_zero_absolute_tolerance():
    v,row=original_fixture();assert actual_numbers(v,row)['validated']


@pytest.mark.parametrize('damage',['small_norm','small_prediction_error'])
def test_small_statistic_mismatch_is_not_hidden_by_default_absolute_tolerance(damage):
    v,row=original_fixture()
    if damage=='small_norm':v['field_comparison']['original_defect_l2']*=1+1e-5
    else:v['prediction_affinity']['l2_ratios'][1]+=1e-10
    with pytest.raises(AssertionError):actual_numbers(v,row)
