from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from operations.x20_85856_boundary_prediction import source_identity,field_stats,require_unchanged,EXPECTED_COEFFICIENTS,EXPECTED_ORDER,live_path,OLD
from operations.x20_window_fields import basis_fields
from handoff.audit_tools.watch_x20_85856_prediction import has_child_exit

def identities():
    a=json.loads(Path('handoff/evidence/20261006-x20-current-basis-85856-review.json').read_text())
    c=json.loads(Path('handoff/evidence/20261006-x20-85856-boundary-candidate.json').read_text())
    d=dict(fields=deepcopy(c['fields']),field_order=EXPECTED_ORDER.copy(),source_jobs=[85821,84026,82989])
    return c,a,d

def test_new_bound_source_identity():source_identity(*identities())

@pytest.mark.parametrize('kind',['job','commit','old_coefficient','order','source_scheduler','missing_source_scheduler','field','dirty'])
def test_reject_wrong_experiment(kind):
    c,a,d=identities()
    if kind=='job':c['source_job']=85744
    if kind=='commit':a['commit']='old'
    if kind=='old_coefficient':c['selected_coefficients']=[-6.846213173701946,-.3537868262980542,.0659556218584672]
    if kind=='order':d['field_order'][0],d['field_order'][2]=d['field_order'][2],d['field_order'][0]
    if kind=='source_scheduler':a['source_84026_scheduler_terminal_verified']=True
    if kind=='missing_source_scheduler':a['source_85821_scheduler_terminal_verified']=False
    if kind=='field':d['fields'][0]['sha256']='bad'
    if kind=='dirty':a['git_clean_verified']=False
    with pytest.raises(ValueError):source_identity(c,a,d)

def test_field_identity_change_and_old_level_mapping(tmp_path):
    p=tmp_path/'a';p.write_bytes(b'a');before=field_stats([p]);require_unchanged(before,field_stats([p]));p.write_bytes(b'bb')
    with pytest.raises(ValueError):require_unchanged(before,field_stats([p]))
    assert str(live_path(OLD))=='outputs/hpc/common-feedback-bridge-v2-20260923/inputs/physical_old_time_level.npz'

def test_actual_new_coefficients_preserve_affine_pair_and_half():
    x=np.linspace(2.,4.,64).reshape(4,4,4);op=lambda z:.8*z+.7
    aa=[z for q in (x,x+.001,x-.001,x+.002) for z in (q,op(q))]
    q,p=basis_fields(aa,EXPECTED_COEFFICIENTS)
    np.testing.assert_allclose(p,op(q),rtol=3e-15,atol=0)
    np.testing.assert_allclose(.5*aa[1]+.5*p,op(.5*aa[0]+.5*q),rtol=3e-15,atol=0)

def test_child_exit_requires_job_identity_and_never_scheduler_claim():
    assert not has_child_exit({},123)
    assert has_child_exit(dict(batch_exit=dict(job_id='123',child_exit_status=0,scheduler_terminal_verified=False)),123)
    with pytest.raises(ValueError):has_child_exit(dict(batch_exit=dict(job_id='124',child_exit_status=0)),123)
