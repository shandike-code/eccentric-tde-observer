import json
from pathlib import Path
from copy import deepcopy
import pytest
from operations import x20_85821_basis as r
from handoff.audit_tools.watch_x20_85821_basis import has_child_exit


def audit(job=85821):
    return json.loads((Path('handoff/evidence')/r.SOURCES[job][1]).read_text())


def test_current_audit_and_unknown_prior_are_separate():
    r.require_source(audit(),85821)
    r.require_source(audit(84026),84026)
    r.require_source(audit(82989),82989)
    assert r.ORDER==((85821,16),(85821,8),(84026,16),(82989,16))


@pytest.mark.parametrize('key,value',[
    ('job_id',84026),('completed_experiment',False),('independent_vector_reduction',False),
    ('all_original_zero_gates_passed',False),('new_material_steps',1),('accepted_outer_steps',21),
    ('baseline_replaced',True),('reference_calibration_eligible',True),('numerical_commit','wrong'),
    ('numerical_artifacts_complete',False),('child_exit_status',1),('scheduler_terminal_verified',False),
    ('scheduler_terminal_state',None),('map_counts',{'historical':8}),('map_process_receipts',608),
    ('feedback_process_receipts',152),('source_84026_scheduler_terminal_verified',True)])
def test_incomplete_or_changed_current_source_rejected(key,value):
    a=audit();a[key]=value
    with pytest.raises(ValueError):r.require_source(a,85821)


def test_84026_terminal_not_inferred_from_new_success():
    a=audit(84026);a['scheduler_terminal_verified']=True
    with pytest.raises(ValueError):r.require_source(a,84026)


@pytest.mark.parametrize('n',[8,16])
def test_source_pair_is_previous_to_final(n):
    root=Path('outputs/review-20260925/x20-85800-feedback-85821-received')
    if not root.exists():root=Path('outputs/hpc')/r.SOURCES[85821][0]
    m=json.loads((root/f'historical/endpoints-map{n:02d}/manifest.json').read_text())
    assert r.pair_fields(m,n)==[m['endpoints'][e] for e in ('previous','final')]
    bad=deepcopy(m);bad['endpoints']['previous']=m['endpoints']['final']
    with pytest.raises(ValueError):r.pair_fields(bad,n)


@pytest.mark.parametrize('damage',['none','parent','prediction','geometry'])
def test_geometry_declaration_chain_is_enforced(damage):
    v={'path':'validation','sha256':'v','size_bytes':1}
    p={'path':'prediction','sha256':'p','size_bytes':2}
    g={'path':'geometry','sha256':'g','size_bytes':3}
    parents=[deepcopy(v)];known=[deepcopy(p),deepcopy(g)]
    if damage=='parent':parents[0]['sha256']='bad'
    if damage=='prediction':known[0]['sha256']='bad'
    if damage=='geometry':known[1]['size_bytes']=9
    if damage=='none':r.bind_geometry(parents,v,p,g,known)
    else:
        with pytest.raises(ValueError):r.bind_geometry(parents,v,p,g,known)


def test_no_source_collection_outside_allocation(tmp_path,monkeypatch):
    monkeypatch.delenv('SLURM_JOB_ID',raising=False)
    with pytest.raises(RuntimeError,match='allocation'):r.run(tmp_path/'blocked')
    assert not (tmp_path/'blocked').exists()


def test_child_exit_is_not_scheduler_state():
    assert not has_child_exit({},123)
    assert has_child_exit({'batch_exit':{'job_id':'123','child_exit_status':1}},123)
    with pytest.raises(ValueError):has_child_exit({'batch_exit':{'job_id':'456','child_exit_status':0}},123)
