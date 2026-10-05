import json
from pathlib import Path
from copy import deepcopy
import pytest
from operations import x20_84026_basis as r
from handoff.audit_tools.watch_x20_84026_basis import has_child_exit

def audit():return json.loads(Path('handoff/evidence/20261005-x20-84026-final-review.json').read_text())

def test_numerical_completion_does_not_invent_scheduler_completion():
    a=audit();r.require_source(a,84026)
    assert a['numerical_artifacts_complete'] and not a['scheduler_terminal_verified']

@pytest.mark.parametrize('damage',['job','gates','material','baseline','scheduler'])
def test_invalid_source_rejected(damage):
    a=audit()
    if damage=='job':a['job_id']=82989
    elif damage=='gates':a['all_original_zero_gates_passed']=False
    elif damage=='material':a['new_material_steps']=1
    elif damage=='baseline':a['baseline_replaced']=True
    else:a['scheduler_terminal_verified']=True
    with pytest.raises(ValueError):r.require_source(a,84026)


def test_previously_audited_source_pair_is_iteration15_not16():
    p=Path('outputs/review-20260925/x20-83514-feedback-84026-received/historical/endpoints-map16/manifest.json')
    if not p.exists():p=Path('outputs/hpc/x20-83514-seed-feedback-20261002/historical/endpoints-map16/manifest.json')
    m=json.loads(p.read_text());fields=r.pair_fields(m,16)
    assert fields==[m['endpoints'][k] for k in ('previous','final')]
    bad=deepcopy(m);bad['endpoints']['previous']=m['endpoints']['final']
    with pytest.raises(ValueError):r.pair_fields(bad,16)


def test_no_source_collection_outside_allocation(tmp_path,monkeypatch):
    monkeypatch.delenv('SLURM_JOB_ID',raising=False)
    with pytest.raises(RuntimeError,match='allocation'):r.run(tmp_path/'blocked')
    assert not (tmp_path/'blocked').exists()


def test_missing_and_failed_child_exit_are_distinct_from_scheduler_state():
    assert not has_child_exit({},123)
    assert has_child_exit({'batch_exit':{'job_id':'123','child_exit_status':1}},123)
    with pytest.raises(ValueError):has_child_exit({'batch_exit':{'job_id':'456','child_exit_status':0}},123)
