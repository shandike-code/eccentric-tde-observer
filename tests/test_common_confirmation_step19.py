from copy import deepcopy
import numpy as np
import pytest
from operations import common_confirmation_step19 as step


def state():
    return {'active_map':None,'history':[{'output_path':'state_2.dat','output_sha256':'final'}],
            'slots':['state_0.dat','state_1.dat','state_2.dat'],'current_slot':2,'current_sha256':'final'}


def test_latest_seed_uses_measured_successor():
    s=state();assert step.latest_seed(s)=={'path':'state_2.dat','sha256':'final','size_bytes':step.pipeline.STATE_BYTES}


@pytest.mark.parametrize('mutation',['pending','active','slot','hash'])
def test_unsettled_or_wrong_seed_is_rejected(mutation):
    s=state()
    if mutation=='pending':s['pending_feedback']={'stage':'feedback'}
    if mutation=='active':s['active_map']={'iteration':2}
    if mutation=='slot':s['current_slot']=1
    if mutation=='hash':s['current_sha256']='wrong'
    with pytest.raises(RuntimeError):step.latest_seed(s)


def test_zero_relabel_cannot_change_material_or_time():
    keys=('encoded_state','temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g',
          'density_g_cm3','phase_index','step_duration_s')
    accepted={k:np.ones(2) for k in keys};base=deepcopy(accepted)
    accepted['relaxation']=np.array(1/64);base['relaxation']=np.array(0.)
    step.validate_base_against_accepted(base,accepted)
    for k in keys:
        changed=deepcopy(base);changed[k][0]+=1
        with pytest.raises(RuntimeError):step.validate_base_against_accepted(changed,accepted)


def test_zero_feedback_uses_step18_postcheck_without_trial_acceptance(monkeypatch,tmp_path):
    protocol={'sources':{e+'_radiation':{'sha256':e} for e in ('previous','final')},'acceptance_gates':{}}
    path=tmp_path/'p.json';path.write_text('{}')
    for e in ('previous','final'):np.savez(tmp_path/(e+'_feedback.npz'),value=np.ones(2))
    monkeypatch.setattr(step.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(step.pair,'run_pair',lambda *a:pytest.fail('zero control invoked finite-step acceptance'))
    monkeypatch.setattr(step.pair,'_run_feedback_state',lambda p,path,sha,e:{'status':'complete','state_gate_passed':True,
        'protocol_sha256':sha,'state_sha256':e,'feedback_artifact_sha256':step.pipeline.sha256(tmp_path/(e+'_feedback.npz'))})
    monkeypatch.setattr(step.pair,'_material_response_residual',lambda *a:(None,np.ones(8),{}))
    monkeypatch.setattr(step.pair,'_feedback_stability_comparison',lambda *a:{})
    monkeypatch.setattr(step.pair,'_feedback_stability_gate_checks',lambda *a:{'stable':True})
    monkeypatch.setattr(step.pipeline,'pair_ready',lambda *a:True)
    seen=[];monkeypatch.setattr(step,'verify_step19_pair',lambda folder,p,result:seen.append(result))
    assert step.zero_feedback(tmp_path,protocol,path,[]) is True
    assert seen[0]['decision']['finite_trial_accepted_as_one_nonlinear_step'] is False


def test_confirmation_keeps_half_amplitude_and_original_dt():
    from test_common_step18_backtrack import fixture
    from operations.common_step18_backtrack import make_trial
    base,old=fixture();r=base['base_residual'];trial=make_trial(base,r,old,1/128)
    step.exact_trial(trial,base,r,old,1/128)
    trial['relaxation']=np.array(1/64)
    with pytest.raises(ValueError):step.exact_trial(trial,base,r,old,1/128)


@pytest.mark.parametrize('is_control,alpha',[(True,0.),(False,1/128)])
def test_protocol_does_not_mislabel_ancestor_endpoints(monkeypatch,is_control,alpha):
    monkeypatch.setattr(step.fresh,'new_protocol',lambda *a:{'sources':{'retained_manifest':{'path':'ancestor'},'outer_base_material':{'path':'fixed'}},'numerical_backtracking':{'alpha':1/128}})
    trial={'path':'new-trial'};p=step.confirmation_protocol({},None,{},[],trial,is_control)
    assert 'retained_manifest' not in p['sources'] and p['sources']['trial_material']==trial
    assert p['sources']['outer_base_material']=={'path':'fixed'}
    assert p['numerical_backtracking']['alpha']==alpha and not p['numerical_backtracking']['physical_time_advanced']


def test_protocol_keeps_step18_direction_and_counter(monkeypatch):
    monkeypatch.setattr(step.fresh,'new_protocol',lambda *a:{'sources':{}})
    p=step.confirmation_protocol({},None,{},[],{},False)
    assert p['numerical_backtracking']==dict(alpha=1/128,fixed_base_accepted_index=18,fixed_direction='r18',physical_time_advanced=False)
