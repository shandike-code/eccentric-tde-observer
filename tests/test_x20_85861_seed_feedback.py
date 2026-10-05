from copy import deepcopy
import numpy as np
import pytest
from operations import x20_85861_seed_feedback as c


def source_roots():
    root=c.ROOT/'outputs/review-20260925'
    true=root/'x20-85859-true-85861-received'
    saved=root/'x20-global-feedback-82518-complete-received'
    if not true.exists():true=c.ROOT/'outputs/hpc/x20-85859-true-validation-20261006'
    if not saved.exists():saved=c.ROOT/'outputs/hpc/x20-global-window-feedback-20261001'
    assert true.exists() and saved.exists(), 'real audited inputs required'
    return true,saved


def test_single_new_branch_two_windows_and_hard_stop():
    calls=[]
    assert c.sequence(lambda name,n:calls.append((name,n)) or 'pass')=='historical_seed_windows_complete_requires_review'
    assert calls==[('historical',8),('historical',16)] and c.LIMITS=={'historical':16}
    calls=[]
    assert c.sequence(lambda name,n:calls.append((name,n)) or 'physical_domain_rejected').endswith('physical_domain_rejected')
    assert calls==[('historical',8)]


def test_true_output_and_frozen_reference_real_identity():
    true,saved=source_roots()
    audit=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85859-true-85861-review.json')
    c.require_validation(audit,c.pipeline.read(true/'summary.json'))
    c.require_saved_reference(c.pipeline.read(c.ROOT/'handoff/evidence/20261001-x20-82518-final-review.json'),c.pipeline.read(saved/'summary.json'))
    claim=c.seed_claim(c.pipeline.read(true/'validation.json'),c.pipeline.read(true/'full/state.json'))
    assert claim['sha256']=='64992a047808bc99eed6463d11fba4cff655970b426f1141ee2efbdf164135de'
    assert claim['sha256']!=c.pipeline.read(true/'candidate-claims.json')['full']['sha256']
    for name in ('historical','accelerated'):
        c.seed_operator_config(c.pipeline.read(true/'full/config.json'),c.pipeline.read(saved/name/'config.json'))
        c.fixed.same_trial(c.v.load_arrays(true/'full/trial_material.npz'),c.v.load_arrays(saved/name/'trial_material.npz'))


@pytest.mark.parametrize('damage',['wrong_job','missing_gate','failed_gate','unreviewed','commit','scheduler','field_stats','receipts','child_exit','boolean_child','ancestral_terminal'])
def test_requires_all_85861_gates(damage):
    true,_=source_roots();a=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85859-true-85861-review.json')
    if damage=='wrong_job':a['job_id']=82515
    if damage=='missing_gate':a['actual']['checks'].pop('full_l2_affinity')
    if damage=='failed_gate':a['actual']['checks']['full_l2_affinity']=False
    if damage=='unreviewed':a['true_maps_independently_validated']=False
    if damage=='commit':a['numerical_commit']='bad'
    if damage=='scheduler':a['execution']['scheduler_terminal_verified']=False
    if damage=='field_stats':a['field_stats_verified']=False
    if damage=='receipts':a['map_process_receipts']=151
    if damage=='boolean_child':a['execution']['child_exit_status']=False
    if damage=='child_exit':a['execution']['child_exit_status']=1
    if damage=='ancestral_terminal':a['source_84026_scheduler_terminal_verified']=True
    with pytest.raises(ValueError):c.require_validation(a,c.pipeline.read(true/'summary.json'))


@pytest.mark.parametrize('damage',['active','input_instead_of_output','wrong_current'])
def test_rejects_unsettled_or_wrong_seed(damage):
    true,_=source_roots();s=c.pipeline.read(true/'full/state.json');actual=c.pipeline.read(true/'validation.json')
    if damage=='active':s['active_map']={}
    if damage=='input_instead_of_output':s['history'][0]['output_sha256']=s['history'][0]['input_sha256']
    if damage=='wrong_current':s['current_sha256']='bad'
    with pytest.raises(ValueError):c.seed_claim(actual,s)


def test_saved_reference_is_not_promoted_or_unstable():
    _,saved=source_roots();a=c.pipeline.read(c.ROOT/'handoff/evidence/20261001-x20-82518-final-review.json');s=c.pipeline.read(saved/'summary.json')
    s['cases']['accelerated']['16']['eight_map_window']['passed']=False
    with pytest.raises(ValueError):c.require_saved_reference(a,s)


def test_four_comparisons_use_complete_vector_difference():
    from operations.calibrate_x20_radiation_histories import vector_comparison
    x=np.ones(512);r=np.ones(512);mass=np.ones(128)
    same={'previous':x,'final':x};opposite={'previous':-x,'final':-x}
    assert vector_comparison(same,same,r,mass,np.ones(3))['passed']
    q=vector_comparison(same,opposite,r,mass,np.ones(3))
    assert not q['passed'] and len(q['vector_difference_over_frozen_80195_signal'])==4
    assert all(max(row)>0 for row in q['vector_difference_over_frozen_80195_signal'].values())


def test_four_saved_feedback_combinations_and_labels():
    _,saved=source_roots()
    vec={e:c.v.load_arrays(saved/f'accelerated/pair16/{e}_response.npz')['residual'] for e in ('previous','final')}
    fb={e:c.v.load_arrays(saved/f'accelerated/pair16/{e}_feedback.npz') for e in ('previous','final')}
    protocol=c.pipeline.read(saved/'accelerated/pair16/feedback_protocol.json')
    # 自身比较仍包含previous/final两个不同端点；只断言组合数、来源标签与原率门。
    result=c.compare_saved(vec,fb,vec,fb,np.ones(512),np.ones(128),np.ones(3),protocol['acceptance_gates'])
    assert len(result['all_four_rate_gate_checks'])==4 and result['cross_rate_pass']
    assert result['saved_reference_job']==82518 and not result['reference_recomputed']

@pytest.mark.parametrize('damage',['none','job','scope','response','scheduler','incomplete'])
def test_origin_is_audited_85821_and_not_saved_82518(damage):
    root=c.ROOT/'outputs/review-20260925/x20-85800-feedback-85821-received'
    if not root.exists():root=c.ROOT/'outputs/hpc/x20-85800-seed-feedback-20261006'
    a=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85821-final-review.json');s=c.pipeline.read(root/'summary.json')
    if damage=='none':c.require_origin(a,s);return
    if damage=='job':a['job_id']=82518
    elif damage=='scope':s['maps']=32
    elif damage=='scheduler':a['scheduler_terminal_verified']=False
    elif damage=='incomplete':a['numerical_artifacts_complete']=False
    else:s['cases']['historical']['16']['physical_response_failures']={'bad':'response'}
    with pytest.raises(ValueError):c.require_origin(a,s)



def test_origin_real_terminal_and_ancestral_unknown():
    a=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85821-final-review.json')
    t=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85821-terminal.json')
    c.validate_origin(a,t)
    for change in ('source_84026_scheduler_terminal_verified','map_process_receipts'):
        broken=deepcopy(a);broken[change]=True if change.startswith('source') else 1215
        with pytest.raises(ValueError):c.validate_origin(broken,t)
    t['scontrol']=t['scontrol'].replace('JobState=COMPLETED','JobState=RUNNING')
    with pytest.raises(ValueError):c.validate_origin(a,t)


@pytest.mark.parametrize('tamper',[False,True])
def test_origin_archive_binds_actual_live_bytes(tmp_path,monkeypatch,tamper):
    import hashlib,json,tarfile,io
    a=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85821-final-review.json')
    terminal=c.pipeline.read(c.ROOT/'handoff/evidence/20261006-x20-85821-terminal.json')
    source=c.ROOT/'outputs/review-20260925/x20-85800-feedback-85821-received/summary.json'
    if not source.exists():source=c.ROOT/'outputs/hpc/x20-85800-seed-feedback-20261006/summary.json'
    root=tmp_path/'origin';root.mkdir();(root/'summary.json').write_text(source.read_text())
    (root/'declaration.json').write_text('{"code":[]}');(root/'input.bin').write_bytes(b'audited numerical bytes')
    ep=tmp_path/'handoff/evidence';ep.mkdir(parents=True)
    (ep/'20261006-x20-85821-terminal.json').write_text(json.dumps(terminal))
    monkeypatch.setattr(c,'ROOT',tmp_path);monkeypatch.setattr(c.pipeline,'ROOT',tmp_path);monkeypatch.setattr(c.v,'ROOT',tmp_path)
    item=c.pipeline.claim(root/'input.bin');item['path']='input.bin'
    data=json.dumps({'files':[item]}).encode();arc=tmp_path/'origin.tar.gz'
    with tarfile.open(arc,'w:gz') as t:
        h=tarfile.TarInfo('ARCHIVE_MANIFEST.json');h.size=len(data);t.addfile(h,io.BytesIO(data))
    a['archive']=c.pipeline.claim(arc);ap=tmp_path/'audit.json';ap.write_text(json.dumps(a))
    def verify(claims):
        for claim in claims:
            b=(tmp_path/claim['path']).read_bytes()
            assert len(b)==claim['size_bytes'] and hashlib.sha256(b).hexdigest()==claim['sha256']
    monkeypatch.setattr(c.reused,'verify',verify)
    if tamper:
        (root/'input.bin').write_bytes(b'changed numerical bytes')
        with pytest.raises(RuntimeError,match='audited source changed'):c.audited_origin_inputs(root,ap,['input.bin'])
    else:
        assert len(c.audited_origin_inputs(root,ap,['input.bin']))==4
