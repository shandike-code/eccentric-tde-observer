from copy import deepcopy
import json
from pathlib import Path
import pytest
from operations import scan_step21_restarted_plane as scan


def lineage():
    rows=[dict(iteration=i,input_sha256=f'h{i-1}',output_sha256=f'h{i}') for i in range(1,12)]
    ret={n:dict(history_rows=deepcopy(rows[n-2:n]),endpoints={
        k:dict(path=f'x{i}',sha256=f'h{i}') for k,i in zip(
            ('previous','final','mapped_final'),(n-2,n-1,n))}) for n in (3,11)}
    return dict(history=rows,active_map=None),ret


def test_restart_pairs_are_actual_successors():
    s,r=lineage();cases=scan.paired_basis(s,r)
    assert [c['path'] for c in cases['x1-x9-x10']['basis']]==['x1','x9','x10','x2','x10','x11']
    assert [c['path'] for c in cases['x2-x9-x10']['basis']]==['x2','x9','x10','x3','x10','x11']


@pytest.mark.parametrize('fault',['missing','reorder','broken','endpoint','retained_row','active'])
def test_bad_pairing_refused(fault):
    s,r=lineage()
    if fault=='missing':s['history'].pop()
    if fault=='reorder':s['history'][0]['iteration']=2
    if fault=='broken':s['history'][4]['output_sha256']='bad'
    if fault=='endpoint':r[3]['endpoints']['mapped_final']['sha256']='bad'
    if fault=='retained_row':r[11]['history_rows'][0]['iteration']=1
    if fault=='active':s['active_map']={}
    with pytest.raises(ValueError):scan.paired_basis(s,r)


def audit():
    return json.loads(Path('handoff/evidence/20260925-wide-validation-complete-review.json').read_text())


def test_real_review_authorizes_readonly_scan():
    scan.validate_audit(audit())


@pytest.mark.parametrize('fault',['incomplete','accepted','rebase','failed_gate','missing_gate','wrong_window','already_stable'])
def test_wrong_scientific_preconditions_refused(fault):
    a=audit()
    if fault=='incomplete':a['final_summary_present']=False
    if fault=='accepted':a['new_material_steps']=1
    if fault=='rebase':a['baseline_replaced']=True
    if fault=='failed_gate':a['windows']['3']['gate_checks']['physical_response_pass']=False
    if fault=='missing_gate':a['windows']['11']['gate_checks'].pop('inner_pair_ready')
    if fault=='wrong_window':a['windows']['11']['comparison_kind']='post_extrapolation_shift'
    if fault=='already_stable':a['windows']['11']['window']['passed']=True
    with pytest.raises(ValueError):scan.validate_audit(a)
