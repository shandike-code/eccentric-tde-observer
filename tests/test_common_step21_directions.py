from copy import deepcopy
import numpy as np
import pytest
from operations import common_step21_directions as step
from operations.prepare_half_step_after_audit import REQUIRED_GATES


def fixture():
    codec=step.GroundStateLogSimplexCodec(2)
    x=codec.encode(np.array([1e4,2e4]),np.array([[.5,.5],[.4,.6]]),np.array([[.4,.3,.3],[.2,.3,.5]]))
    d=codec.decode(x);t={k:np.array(getattr(d,k)) for k in ('temperature_k','hydrogen_fraction','helium_fraction','specific_material_energy_erg_g')}
    t.update(encoded_state=x,base_encoded_state=x.copy(),base_residual=np.ones_like(x)*.01,finite_direction=np.ones_like(x)*.01,
        relaxation=np.array(0.),phase_index=np.array(0),step_duration_s=np.array(3.),density_g_cm3=np.ones(2))
    return t,{'step_duration_s':np.array([3.]),'density_g_cm3':np.ones((1,2))}


@pytest.mark.parametrize('name',['control','thermal','population'])
def test_trial_preserves_base_denominator_and_physical_time(name):
    base,old=fixture();r=base['base_residual'];t=step.make_trial(base,r,old,name)
    step.exact_trial(t,base,r,old,name)
    assert np.array_equal(t['encoded_state'],base['encoded_state']+step.ALPHAS[name]*step.split_direction(r,name))
    for k in ('base_encoded_state','base_residual','density_g_cm3','phase_index','step_duration_s'):
        assert np.array_equal(t[k],base[k])


def test_directions_partition_all_cells_without_dropping_residual_components():
    r=np.arange(12,dtype=float)+1
    thermal=step.split_direction(r,'thermal').reshape(3,4)
    population=step.split_direction(r,'population').reshape(3,4)
    assert np.array_equal((thermal+population).ravel(),r)
    assert np.all(thermal[:,1:]==0) and np.all(population[:,0]==0)
    assert np.array_equal(thermal[:,0],r.reshape(3,4)[:,0])
    assert np.array_equal(population[:,1:],r.reshape(3,4)[:,1:])


def test_population_probe_fixes_gas_energy_not_temperature():
    base,old=fixture();r=base['base_residual'].copy();r[1::4]=4
    base['base_residual']=r.copy();base['finite_direction']=r.copy()
    t=step.make_trial(base,r,old,'population')
    assert np.array_equal(t['encoded_state'].reshape(-1,4)[:,0],base['encoded_state'].reshape(-1,4)[:,0])
    assert not np.array_equal(t['temperature_k'],base['temperature_k'])
    assert np.allclose(t['helium_fraction'].sum(axis=1),1)


@pytest.mark.parametrize('mutation',['amplitude','direction','denominator','dt','old_dt','decode','base'])
def test_wrong_diagnostic_trial_is_rejected(mutation):
    base,old=fixture();r=base['base_residual'].copy();t=step.make_trial(base,r,old,'thermal')
    if mutation=='amplitude':t['relaxation']=np.array(1/128)
    if mutation=='direction':t['finite_direction']=r.copy()
    if mutation=='denominator':base['base_residual']*=2
    if mutation=='dt':t['step_duration_s']=np.array(2.)
    if mutation=='old_dt':old['step_duration_s'][0]=2
    if mutation=='decode':t['temperature_k']*=1.001
    if mutation=='base':base['relaxation']=np.array(1/256)
    with pytest.raises(ValueError):step.exact_trial(t,base,r,old,'thermal')


@pytest.mark.parametrize('mode,expected',[
 ('baseline_unstable',['control']),('physical_domain_rejected',['control','thermal']),
 ('diagnostic_budget_complete',['control','thermal','population'])])
def test_sequence_stops_on_domain_failure_and_never_adds_a_third_direction(mode,expected):
    seen=[]
    def evaluate(name):
        seen.append(name)
        if name=='control':return mode if mode=='baseline_unstable' else 'baseline_stable'
        return mode
    result=step.direction_sequence(evaluate)
    assert seen==expected
    assert 'supported' not in result
    assert step.LIMITS=={'control':4,'thermal':8,'population':8}


@pytest.mark.parametrize('change',['counter','terminal','noise','heat','missing','cross'])
def test_two_amplitude_failure_provenance_is_required(change):
    gates={k:True for k in REQUIRED_GATES};gates['candidate_maximum_cell_contraction_pass']=False
    audit={'accepted_outer_steps':20,'pairs':{'control':{},'half04':{},'half08':{'gate_checks':gates,'fresh_baseline_comparison':{'passed':False}}}}
    terminal={'job_id':76871,'state':'COMPLETED'}
    step.validate_failure_audit(audit,terminal)
    if change=='counter':audit['accepted_outer_steps']=19
    if change=='terminal':terminal['state']='FAILED'
    if change=='noise':gates['inner_noise_resolved_pass']=False
    if change=='heat':gates['last_two_atomic_heating_pass']=False
    if change=='missing':gates.pop('population_nonnegative_pass')
    if change=='cross':audit['pairs']['half08']['fresh_baseline_comparison']['passed']=True
    with pytest.raises(RuntimeError):step.validate_failure_audit(audit,terminal)


def test_undeclared_or_nonfinite_direction_and_trust_violation_rejected():
    base,old=fixture();r=base['base_residual'].copy()
    with pytest.raises(ValueError):step.split_direction(r,'helium_only')
    with pytest.raises(ValueError):step.split_direction(np.full(8,np.nan),'thermal')
    # exp(200/256)-1 > 0.5，确保热能方向实际越过温度信赖域。
    r*=20000;base['base_residual']=r.copy();base['finite_direction']=r.copy()
    with pytest.raises(ValueError):step.make_trial(base,r,old,'thermal')


def test_zero_control_does_not_call_finite_step_acceptance(monkeypatch,tmp_path):
    p={'sources':{e+'_radiation':{'sha256':e} for e in ('previous','final')},'acceptance_gates':{}}
    path=tmp_path/'p.json';path.write_text('{}')
    for e in ('previous','final'):np.savez(tmp_path/(e+'_feedback.npz'),value=np.ones(2))
    monkeypatch.setattr(step.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(step.pair,'run_pair',lambda *a:pytest.fail('finite acceptance invoked on zero control'))
    monkeypatch.setattr(step.pair,'_run_feedback_state',lambda p,path,sha,e:dict(status='complete',state_gate_passed=True,protocol_sha256=sha,state_sha256=e,feedback_artifact_sha256=step.pipeline.sha256(tmp_path/(e+'_feedback.npz'))))
    monkeypatch.setattr(step.pair,'_material_response_residual',lambda *a:(None,np.ones(8),{}))
    monkeypatch.setattr(step.pair,'_feedback_stability_comparison',lambda *a:{})
    monkeypatch.setattr(step.pair,'_feedback_stability_gate_checks',lambda *a:{'stable':True})
    monkeypatch.setattr(step.pipeline,'pair_ready',lambda *a:True)
    seen=[];monkeypatch.setattr(step,'verify_step21_pair',lambda folder,p,result:seen.append(result))
    assert step.zero_feedback(tmp_path,p,path,[]) is True
    assert not seen[0]['decision']['finite_trial_accepted_as_one_nonlinear_step']


def test_baseline_reversal_or_failure_stops_probe():
    report={'physical_response_failures':{},'prior_rejected_candidates':{'pair08':{'passed':False}}}
    assert step.control_allows_probe(True,report)
    assert not step.control_allows_probe(False,report)
    report['prior_rejected_candidates']['pair08']['passed']=True
    assert not step.control_allows_probe(True,report)
    report['prior_rejected_candidates']['pair08']['passed']=False
    report['physical_response_failures']={'final':'bad'}
    assert not step.control_allows_probe(True,report)
