from copy import deepcopy
import numpy as np
import pytest
from operations import validate_population_defect_global as valid
from test_recover_step21_control_windows import templates, endpoints


def test_full_half_before_feedback_and_bounded_paired_windows():
    events=[]
    def validation():events.append('full-and-half');return True
    def evaluate(name,n):events.append((name,n));return 'pass'
    assert valid.sequence(validation,evaluate)=='population_global_windows_complete_requires_review'
    assert events==['full-and-half',('control',2),('population',2),('control',10),('population',10)]
    assert sum(valid.LIMITS.values())==21


@pytest.mark.parametrize('failed',[None,('control',2),('population',2),('control',10),('population',10)])
def test_failure_dispatches_no_later_stage(failed):
    calls=[]
    def evaluate(name,n):
        calls.append((name,n));return 'physical_domain_rejected' if (name,n)==failed else 'pass'
    outcome=valid.sequence(lambda:failed is not None,evaluate)
    assert outcome.startswith('stopped_at_')
    if failed is None:assert calls==[]
    else:assert calls[-1]==failed


def test_signal_interrupt_never_runs_feedback():
    def stop():raise valid.reused.Stopped('signal')
    with pytest.raises(valid.reused.Stopped):
        valid.sequence(stop,lambda *_:pytest.fail('feedback after interruption'))


def test_first_pair_does_not_claim_persistence_and_zero_signal_rejects():
    mass=np.array([1.,2.]);c={e:np.zeros(8) for e in ('previous','final')}
    p={e:np.ones(8) for e in c}
    measured,signals=valid.directions.response_measurement(p,c,mass,1/256)
    assert valid.signal_gate(2,measured) and 'eight_map_signal_persistent' not in measured
    with pytest.raises(KeyError):valid.signal_gate(10,measured)
    later,_=valid.directions.response_measurement(p,c,mass,1/256,signals)
    assert valid.signal_gate(10,later)
    shifted={e:1.3*a for e,a in p.items()}
    later,_=valid.directions.response_measurement(shifted,c,mass,1/256,signals)
    assert valid.signal_gate(2,later) and not valid.signal_gate(10,later)
    unresolved,_=valid.directions.response_measurement(c,c,mass,1/256)
    assert not valid.signal_gate(2,unresolved)
    with pytest.raises(ValueError):valid.signal_gate(8,measured)


def test_population_and_control_protocols_keep_distinct_trial_and_authorization():
    finite,zero=templates();before=deepcopy((finite,zero));es,rows=endpoints()
    ret=dict(endpoints=es,history_rows=rows)
    for name in ('population','control'):
        trial={'path':name+'-trial.npz'}
        p=valid.directions.make_protocol(finite,zero,valid.ROOT/('outputs/hpc/test-pop-'+name),ret,trial,{}, {},name)
        assert p['sources']['trial_material']==trial
        assert p['numerical_backtracking']['alpha']==(1/256 if name=='population' else 0)
        assert not p['numerical_backtracking']['physical_time_advanced']
        if name=='control':assert p['authorization']['accept_material_step'] is False
        else:
            # 原16门适配器要求保留其有限候选判决授权；外层诊断不据此提升物质态。
            assert p['authorization']['accept_finite_trial_as_one_nonlinear_step_only_if_all_gates_pass'] is True
            assert p['outer_iteration']['diagnostic_only'] is True
    assert (finite,zero)==before


def test_exact_real_core_inventory_and_global_neighbor_check(tmp_path):
    shape=(6400,2,3);x=np.ones(shape);x[-1]=np.nextafter(0.,1.)
    source=tmp_path/'source.dat';x.tofile(source);original=source.read_bytes();repl={}
    for i in (23,30):
        path=tmp_path/f'{i}.npz';np.savez(path,candidate=np.full((896,2,3),2.));repl[i]=path
    qpath=tmp_path/'full.dat';hpath=tmp_path/'half.dat'
    valid.write_candidates(source,repl,qpath,hpath,shape)
    q=np.fromfile(qpath).reshape(shape);h=np.fromfile(hpath).reshape(shape)
    assert np.array_equal(q[2560:4352],np.full((1792,2,3),2.))
    assert np.array_equal(q[:2560],x[:2560]) and np.array_equal(q[4352:],x[4352:])
    assert np.array_equal(h[2560:4352],.5*x[2560:4352]+.5*q[2560:4352])
    assert np.array_equal(h[4352:],x[4352:]) and source.read_bytes()==original
    # 邻频耦合使未改输入的block34输出变化；审计不能只遍历被改核心。
    op=lambda a:.25*a+.05*np.roll(a,1,axis=0)+1.
    paths=[]
    for i,a in enumerate((x,op(x),q,op(q),h,op(h))):
        p=tmp_path/f'field{i}.dat';a.tofile(p);paths.append(p)
    report,reference=valid.validate_fields(paths,paths[:2],shape)
    assert report['selected_blocks']==list(range(20,34))
    assert report['all_groups_evaluated']==6400 and report['fixed_scale_l2_ratios'][3]<1e-14
    assert any(r['block']==34 and r['output_change_linf']>0 for r in report['slabs'])
    bad=q.copy();bad[0]=2.;bad.tofile(paths[2])
    with pytest.raises(ValueError,match='unselected'):valid.validate_fields(paths,paths[:2],shape)


def review():
    return dict(job_id=79850,source_job_id=79747,frozen_material_case='population',verified_frequency_rows=1792,
        mac_independent_fsum=True,school_raw_arrays_scanned=True,operator_recomputed=False,new_material_steps=0)


@pytest.mark.parametrize('key,value',[('job_id',78405),('source_job_id',78253),('frozen_material_case','control'),
    ('verified_frequency_rows',1791),('mac_independent_fsum',False),('school_raw_arrays_scanned',False),
    ('operator_recomputed',True),('new_material_steps',1)])
def test_array_evidence_cannot_be_crossed_or_partial(key,value):
    r=review();terminal=dict(job_id=79850,state='COMPLETED',scontrol='JobState=COMPLETED ExitCode=0:0')
    valid.require_array_review(r,terminal)
    r[key]=value
    with pytest.raises(RuntimeError,match='array scan'):valid.require_array_review(r,terminal)


def test_failed_scheduler_is_not_a_successful_array_audit():
    with pytest.raises(RuntimeError):valid.require_array_review(review(),dict(job_id=79850,state='FAILED',scontrol='ExitCode=1:0'))


def test_population_source_rejects_stale_control_and_partial_state():
    # 用本次接收的真实小元数据检验最后map输入/输出，而非另造一个近似状态。
    root=valid.ROOT/'outputs/review-20260925'
    if not (root/'population-defect-79747-received/declaration.json').exists():
        pytest.skip('Mac-only downloaded metadata; synthetic cases and school prepare cover platform')
    prior=valid.pipeline.read(root/'population-defect-79747-received/declaration.json')
    run=root/'late-population-global-79631-received/population'
    state=valid.pipeline.read(run/'state.json');ret=valid.pipeline.read(run/'validation.json')
    a,b=valid.source_pair(prior,state,ret)
    assert a==prior['cases']['population']['input'] and b==prior['cases']['population']['output']
    bad=deepcopy(prior);bad['frozen_material_case']='control'
    with pytest.raises(RuntimeError,match='population'):valid.source_pair(bad,state,ret)
    bad=deepcopy(state);bad['active_map']={'incomplete':True}
    with pytest.raises(RuntimeError,match='settled'):valid.source_pair(prior,bad,ret)
    bad=deepcopy(ret);bad['candidate']['sha256']='wrong'
    with pytest.raises(RuntimeError,match='actual rejected'):valid.source_pair(prior,state,bad)


def test_old_reference_cannot_be_hidden_by_current_reference():
    current=dict(fixed_scale_l2_ratios=[1.,.6,.8,1e-10],fixed_scale_linf_ratios=[1.,.6,.8,1e-10])
    original=dict(fixed_scale_l2_ratios=[1.,.6,.8],fixed_scale_linf_ratios=[1.,.6,.8])
    row=dict(residual=1e-6,boundary_l1=1e-7,boundary_bolometric=3e-8)
    old={**row,'boundary_bolometric':1e-8};new={**row,'boundary_bolometric':2e-8}
    checks=valid.fields.checks(current,original,row,old,new,new)
    assert len(checks)==21 and checks['current_full_boundary_bolometric']
    assert not checks['original_full_boundary_bolometric'] and not all(checks.values())
    original['fixed_scale_l2_ratios'][1]=.81
    assert not valid.fields.checks(current,original,row,row,new,new)['original_full_l2_benefit']


def test_original_reference_is_not_used_to_construct_half_affinity(tmp_path):
    shape=(6400,2,3);x=np.ones(shape);q=x.copy();q[4352:6144]=2.
    full=q.copy();full[2560:4352]=3.;half=.5*q+.5*full
    op=lambda a:.25*a+.05*np.roll(a,1,axis=0)+1.
    paths=[]
    for i,a in enumerate((q,op(q),full,op(full),half,op(half),x,op(x))):
        p=tmp_path/f'dual{i}.dat';a.tofile(p);paths.append(p)
    current,original=valid.validate_fields(paths[:6],paths[6:],shape)
    assert current['fixed_scale_l2_ratios'][3]<1e-14
    assert original['affinity_tested_here'] is False and len(original['fixed_scale_l2_ratios'])==3
    assert not np.array_equal(half,.5*x+.5*full)
    bad=half.copy();bad[4352:6144]=.5*x[4352:6144]+.5*full[4352:6144];bad.tofile(paths[4])
    with pytest.raises(ValueError,match='unselected'):valid.validate_fields(paths[:6],paths[6:],shape)
