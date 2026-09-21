from copy import deepcopy
import json
import numpy as np
import pytest
from operations import second_outer_step as outer
from tests.test_response_direction_batch import zero_source


def fixture():
    accepted = outer.batch.make_trial(zero_source(), np.arange(8.)/8, 1/256)
    residual = np.arange(8.)/16 + .01
    old = {'density_g_cm3': np.tile(accepted['density_g_cm3'], (1368,1)),
           'step_duration_s': np.full(1368, float(accepted['step_duration_s']))}
    return accepted, residual, old


def test_rebase_uses_accepted_trial_preserves_physical_fields_and_input():
    a,r,old = fixture(); before = deepcopy(a); b = outer.rebase_trial(a,r,old)
    for k in (*outer.PHYSICAL_FIELDS, *outer.DECODED_FIELDS, 'encoded_state'):
        assert np.array_equal(a[k], b[k])
    assert np.array_equal(b['base_encoded_state'], a['encoded_state'])
    assert not np.array_equal(b['base_encoded_state'], a['base_encoded_state'])
    for alpha in outer.batch.ALPHAS.values():
        t = outer.batch.make_trial(b,r,alpha); outer.validate_trial(t,b,r)
        assert np.array_equal(t['encoded_state'], a['encoded_state']+alpha*r)
    outer.identical_material(a,before)


@pytest.mark.parametrize('fault',['dt','density','decode','nan','shape','zero'])
def test_invalid_rebase_refused(fault):
    a,r,old = fixture()
    if fault=='dt':old['step_duration_s'][-1] *= 2
    if fault=='density':old['density_g_cm3'][-1] *= 2
    if fault=='decode':a['temperature_k'][0] *= 2
    if fault=='nan':r[0]=np.nan
    if fault=='shape':r=r[:-1]
    if fault=='zero':r*=0
    with pytest.raises(ValueError):outer.rebase_trial(a,r,old)


@pytest.mark.parametrize('field',['base_encoded_state','base_residual','finite_direction','encoded_state',
                                'density_g_cm3','step_duration_s','phase_index','temperature_k'])
def test_trial_cannot_leak_old_base_or_change_physics(field):
    a,r,old = fixture(); b=outer.rebase_trial(a,r,old);t=outer.batch.make_trial(b,r,1/256)
    t[field] = t[field]+1
    with pytest.raises(ValueError):outer.validate_trial(t,b,r)


def protocol_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(outer,'ROOT',tmp_path)
    monkeypatch.setattr(outer.reused,'ROOT',tmp_path)
    a,r,old=fixture();b=outer.rebase_trial(a,r,old);t=outer.batch.make_trial(b,r,1/256)
    np.savez(tmp_path/'base.npz',**b);np.savez(tmp_path/'trial.npz',**t);np.save(tmp_path/'r.npy',r)
    (tmp_path/'old.json').write_text('{}')
    import hashlib
    def claim(name):
        p=tmp_path/name;return {'path':name,'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    cfg={'outer_baseline':{'material':claim('base.npz'),'residual':claim('r.npy'),
                          'physical_old_time_level':claim('old.json')}}
    payload={'sources':{'trial_material':claim('trial.npz'),'physical_old_time_level':claim('old.json'),
        'base_residual':{'path':'original-r.npy','sha256':'old','size_bytes':9}},
        'acceptance_gates':{'heat':.001,'radiation':1e-4},'formal_state_gates':{'rss':6},
        'authorization':{'full_orbit':False},'configuration':{'output':'round/summary.json'}}
    return cfg,payload


def test_explicit_new_protocol_preserves_all_other_gates_and_original_bytes(tmp_path,monkeypatch):
    cfg,payload=protocol_fixture(tmp_path,monkeypatch);before=deepcopy(payload)
    legacy=tmp_path/'feedback_protocol.json';legacy.write_text(json.dumps(payload))
    original_bytes=legacy.read_bytes();original=lambda *a:legacy
    monkeypatch.setattr(outer.pipeline,'feedback_protocol',original)
    with outer.rebased_protocols():
        p=outer.pipeline.feedback_protocol(cfg,{})
        changed=json.loads(p.read_text())
        assert p!=legacy and legacy.read_bytes()==original_bytes
        assert changed['sources']['base_residual']==cfg['outer_baseline']['residual']
        for k in ('acceptance_gates','formal_state_gates','authorization','configuration'):
            assert changed[k]==before[k]
        assert outer.pipeline.feedback_protocol(cfg,{})==p
        bad=json.loads(p.read_text());bad['sources']['base_residual']=payload['sources']['base_residual']
        p.write_text(json.dumps(bad))
        with pytest.raises(RuntimeError,match='immutable'):outer.pipeline.feedback_protocol(cfg,{})
    assert outer.pipeline.feedback_protocol is original


def test_baseline_file_tamper_and_physical_old_time_change_refused(tmp_path,monkeypatch):
    cfg,payload=protocol_fixture(tmp_path,monkeypatch)
    bad=deepcopy(payload);bad['sources']['physical_old_time_level']['sha256']='wrong'
    with pytest.raises(RuntimeError,match='old time'):outer.rebase_payload(bad,cfg)
    (tmp_path/'r.npy').write_bytes(b'broken')
    with pytest.raises(RuntimeError,match='identity'):outer.rebase_payload(payload,cfg)


def test_real_round_builder_publishes_rebased_canonical_protocol(tmp_path,monkeypatch):
    cfg,payload=protocol_fixture(tmp_path,monkeypatch)
    driver=outer.batch.driver;monkeypatch.setattr(driver,'ROOT',tmp_path)
    run=tmp_path/'run';run.mkdir();(run/'trial_material.npz').write_bytes((tmp_path/'trial.npz').read_bytes())
    rd=run/'feedback-round1';rd.mkdir()
    rows=[{'input_path':'a.dat','input_sha256':'a','output_sha256':'b'},
          {'input_path':'b.dat','input_sha256':'b','output_sha256':'c'}]
    for name,row in zip(('previous','final'),rows):
        payload['sources'][name+'_radiation']={'path':row['input_path'],'sha256':row['input_sha256']}
    def legacy(c,s):
        path=tmp_path/c['run']/'feedback_protocol.json';path.write_text(json.dumps(payload));return path
    monkeypatch.setattr(outer.pipeline,'feedback_protocol',legacy)
    with outer.rebased_protocols():
        result=driver.build_round_protocol(run,cfg,{'history':rows},rd)
    assert result==rd/'feedback_protocol.json'
    actual=json.loads(result.read_text())
    assert actual['sources']['base_residual']==cfg['outer_baseline']['residual']
    assert actual['configuration']['summary_path']=='run/feedback-round1/feedback_summary.json'
    assert actual['acceptance_gates']==payload['acceptance_gates']
    assert json.loads((rd/'inputs/feedback_protocol.json').read_text())==payload


def test_stage_adapter_restored_after_failure(monkeypatch,tmp_path):
    original=outer.batch.prepare;proto=outer.pipeline.feedback_protocol
    def fail(out):
        assert outer.batch.prepare is outer.prepare
        assert outer.pipeline.feedback_protocol is not proto
        raise RuntimeError('synthetic failure')
    monkeypatch.setattr(outer.batch,'execute',fail)
    with pytest.raises(RuntimeError,match='synthetic'):outer.execute(tmp_path)
    assert outer.batch.prepare is original and outer.pipeline.feedback_protocol is proto


@pytest.mark.parametrize('fault',['pending','gate','confirmation','case','parent'])
def test_unconfirmed_source_cannot_be_rebased(fault):
    parent={'status':'complete','precision_confirmation_passed':True}
    conf={'precision_confirmation_passed':True,'cases':{k:{'all_original_gates':True,'fresh_control_contraction':True} for k in ('confirm2','confirm4')}}
    s={'status':'one_material_trial_accepted','history':[{},{}]}
    summary={'gate_checks':{k:True for k in outer.REQUIRED_GATES},'decision':{'finite_trial_accepted_as_one_nonlinear_step':True}}
    outer.confirmed_source(parent,conf,s,summary)
    if fault=='pending':s['pending_feedback']={'stage':'ledger'}
    if fault=='gate':summary['gate_checks'][next(iter(outer.REQUIRED_GATES))]=False
    if fault=='confirmation':conf['precision_confirmation_passed']=False
    if fault=='case':conf['cases']['confirm4']['fresh_control_contraction']=False
    if fault=='parent':parent['status']='mapping'
    with pytest.raises(RuntimeError):outer.confirmed_source(parent,conf,s,summary)
