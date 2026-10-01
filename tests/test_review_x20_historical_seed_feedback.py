from copy import deepcopy
from pathlib import Path
import pytest
from handoff.audit_tools import review_x20_historical_seed_feedback as r
ROOT=Path('outputs/review-20260925/x20-historical-seed-feedback-82989-received')


def test_real_single_branch_plan():
    d=r.read(ROOT/'declaration.json');s=r.read(ROOT/'seed-claims.json')
    r.verify_plan(d,s,82989)
    for field,value in [('maximum_maps',32),('reference_calibration_eligible',True),('matched_new_two_branch_experiment',True),('source_jobs',[76727,80195,82273,82515])]:
        bad=deepcopy(d);bad[field]=value
        with pytest.raises(AssertionError):r.verify_plan(bad,s,82989)


def test_real_failed_cross_history_still_valid_audit_input():
    for n in (8,16):
        dec=r.read(ROOT/f'historical/pair{n:02d}/decision.json')
        r.verify_pair(dec,'historical',n)
        assert not dec['vs_saved_reference']['residual_comparison']['passed']
        assert not dec['vs_saved_reference']['cross_rate_pass']
        bad=deepcopy(dec);bad['original_zero_gates']['physical_response_pass']=False
        with pytest.raises(AssertionError):r.verify_pair(bad,'historical',n)


def test_complete_order_has_no_new_reference_branch():
    assert r.settled_entries(ROOT)==[('historical',8),('historical',16)]
    assert not (ROOT/'accelerated').exists()
