import numpy as np
import pytest
from operations import common_confirmation_batch as c


@pytest.mark.parametrize('fail,expected', [('control',['control']),('confirm1',['control','confirm1']),
    ('confirm2',['control','confirm1','confirm2']),(None,['control','confirm1','confirm2'])])
def test_sequence_never_dispatches_past_failed_prerequisite(fail,expected):
    calls=[]
    def run(name,count):
        calls.append(name);assert count=={'control':4,'confirm1':2,'confirm2':2}[name]
        return name!=fail
    status=c.sequence(run)
    assert calls==expected
    assert status==('confirmed_requires_mac_review' if fail is None else 'stopped_at_'+fail)


def test_four_combinations_expose_unfavorable_baseline():
    base={'previous':np.ones(8),'final':np.ones(8)*3}
    trial={'previous':np.ones(8)*2,'final':np.ones(8)*.5}
    result=c.cross_comparisons(trial,base,np.array([1.,3.]))
    assert len(result['ratios'])==4 and not result['passed']
    assert result['ratios']['previous_vs_previous']['l2']==2
    assert result['ratios']['previous_vs_final']['l2']<1


def test_zero_baseline_cannot_create_fake_contraction():
    with pytest.raises(ValueError):
        c.cross_comparisons({'previous':np.ones(8),'final':np.ones(8)},
            {'previous':np.zeros(8),'final':np.ones(8)},np.ones(2))


def test_missing_endpoint_and_missing_gate_rejected():
    with pytest.raises(ValueError):c.cross_comparisons({'final':np.ones(8)},{},np.ones(2))
    assert not c.all_pair_gates({'gate_checks':{}})
    assert not c.all_pair_gates({'gate_checks':{k:(k!=next(iter(c.REQUIRED_GATES))) for k in c.REQUIRED_GATES}})


def zero_fixture():
    codec=c.pair.GroundStateLogSimplexCodec(2)
    x=codec.encode(np.array([1e4,2e4]),np.array([[.5,.5],[.4,.6]]),np.array([[.4,.3,.3],[.2,.3,.5]]))
    d=codec.decode(x)
    t={k:np.array(getattr(d,k)) for k in ('temperature_k','hydrogen_fraction','helium_fraction')}
    t.update(encoded_state=x,base_encoded_state=x.copy(),base_residual=np.ones_like(x),finite_direction=np.ones_like(x),
             relaxation=np.array(0.),phase_index=np.array(0),step_duration_s=np.array(3.),density_g_cm3=np.ones(2))
    old={'step_duration_s':np.array([3.]),'density_g_cm3':np.ones((1,2))}
    return t,old


def test_zero_identity_rejects_dt_and_decode_substitution():
    t,old=zero_fixture();base={k:v.copy() for k,v in t.items()}
    c.validate_zero(t,base,t['base_residual'],old)
    old['step_duration_s'][0]=2
    with pytest.raises(RuntimeError):c.validate_zero(t,base,t['base_residual'],old)
    old['step_duration_s'][0]=3;t['temperature_k'][0]*=1.01
    with pytest.raises(ValueError):c.validate_zero(t,base,t['base_residual'],old)


def test_exception_cannot_advance_sequence():
    calls=[]
    def crash(name,count):
        calls.append(name);raise RuntimeError('resource failure')
    with pytest.raises(RuntimeError):c.sequence(crash)
    assert calls==['control']


def test_zero_feedback_does_not_call_finite_trial_acceptance(monkeypatch,tmp_path):
    protocol={'sources':{e+'_radiation':{'sha256':e} for e in ('previous','final')},'acceptance_gates':{}}
    path=tmp_path/'p.json';path.write_text('{}')
    for e in ('previous','final'):np.savez(tmp_path/(e+'_feedback.npz'),value=np.ones(2))
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(c.pair,'run_pair',lambda *a:pytest.fail('zero control called finite-trial acceptance'))
    monkeypatch.setattr(c.pair,'_run_feedback_state',lambda p,path,sha,e:{'status':'complete','state_gate_passed':True,
        'protocol_sha256':sha,'state_sha256':e,'feedback_artifact_sha256':c.pipeline.sha256(tmp_path/(e+'_feedback.npz'))})
    monkeypatch.setattr(c.pair,'_material_response_residual',lambda *a:(None,np.ones(8),{}))
    monkeypatch.setattr(c.pair,'_feedback_stability_comparison',lambda *a:{})
    monkeypatch.setattr(c.pair,'_feedback_stability_gate_checks',lambda *a:{'stable':True})
    monkeypatch.setattr(c.pipeline,'pair_ready',lambda *a:True)
    seen=[];monkeypatch.setattr(c.fresh,'verify_complete_pair',lambda folder,p,result:seen.append(result))
    assert c.zero_feedback(tmp_path,protocol,path,[]) is True
    assert seen[0]['decision']['finite_trial_accepted_as_one_nonlinear_step'] is False
