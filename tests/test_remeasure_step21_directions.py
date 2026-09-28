from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from operations import remeasure_step21_directions as r
from test_common_step21_directions import fixture as material_fixture


def source_fixture():
    pair = dict(previous=np.ones(8), final=np.ones(8))
    w = r.station.original.window_comparison(pair, pair, np.ones(8), np.ones(2))
    gates = {k:True for k in r.station.ZERO_GATES}
    summary = dict(status='persistent_control_stationarity_requires_review', maps=16,
        accepted_outer_steps=20, new_material_steps=0, baseline_replaced=False, strict_error_bound=False,
        windows={n:dict(confirmation_pass=True, zero_control_stable=True, original_gates=deepcopy(gates),
            window_comparison=deepcopy(w), from_78548_comparison=deepcopy(w)) for n in ('8','16')})
    audit = dict(job_id=78594, final_summary_present=True, feedback_rounds=[8,16], maps=list(range(16)),
        accepted_outer_steps=20, new_material_steps=0, baseline_replaced=False, strict_error_bound=False,
        windows={n:dict(confirmation_pass=True, gate_checks=deepcopy(gates), window=deepcopy(w), from_78548=deepcopy(w)) for n in ('8','16')})
    history = [dict(iteration=i+1, input_sha256=str(i), output_sha256=str(i+1)) for i in range(16)]
    state = dict(active_map=None, history=history)
    ret = dict(history_rows=deepcopy(history[-2:]), endpoints=dict(previous=dict(sha256='14'), final=dict(sha256='15'),
        mapped_final=dict(path='latest.dat', sha256='16', size_bytes=r.pipeline.STATE_BYTES)))
    return summary, audit, state, ret


def test_audited_source_selects_latest_successor_without_mutation():
    args=source_fixture(); before=deepcopy(args)
    assert r.source_seed(*args)==args[3]['endpoints']['mapped_final'] and args==before


@pytest.mark.parametrize('bad', ['status','job','partial','counter','rebase','strict','gate','cumulative','audit_drift','chain','map_count','input','seed','size'])
def test_unreviewed_or_unstable_source_is_rejected(bad):
    s,a,st,ret=source_fixture()
    if bad=='status':s['status']='stationarity_not_confirmed'
    if bad=='job':a['job_id']=78548
    if bad=='partial':a['final_summary_present']=False
    if bad=='counter':a['new_material_steps']=1
    if bad=='rebase':s['baseline_replaced']=True
    if bad=='strict':a['strict_error_bound']=True
    if bad=='gate':s['windows']['16']['original_gates']={}
    if bad=='cumulative':s['windows']['16']['from_78548_comparison']['passed']=False
    if bad=='audit_drift':a['windows']['16']['from_78548']['vector_difference_over_frozen_r20_norms']['final_vs_final'][1]=.001
    if bad=='chain':st['history'][2]['output_sha256']='wrong'
    if bad=='map_count':st['history'].pop()
    if bad=='input':ret['endpoints']['final']['sha256']='wrong'
    if bad=='seed':ret['endpoints']['mapped_final']['sha256']='wrong'
    if bad=='size':ret['endpoints']['mapped_final']['size_bytes']=1
    with pytest.raises((RuntimeError,ValueError)):r.source_seed(s,a,st,ret)


@pytest.mark.parametrize('failure', ['none','control8','control16','thermal8','population16'])
def test_control_first_and_bounded_fail_closed_schedule(failure):
    seen=[]
    def evaluate(name,n):
        seen.append((name,n))
        if name+str(n)==failure:
            return 'control_unstable' if name=='control' else 'physical_domain_rejected'
        return 'control_stable' if name=='control' else 'direction_measured'
    outcome=r.sequence(evaluate)
    expected=[(name,n) for n in (8,16) for name in r.NAMES]
    if failure!='none':expected=expected[:next(i for i,v in enumerate(expected) if v[0]+str(v[1])==failure)+1]
    assert seen==expected
    if failure=='none':assert outcome=='refreshed_direction_measurement_requires_review'
    else:assert outcome.startswith('stopped_at_')
    assert r.LIMITS==dict(control=16,thermal=16,population=16)


def test_direction_gate_failure_is_a_measurement_not_an_automatic_promotion():
    seen=[]
    r.sequence(lambda name,n: seen.append((name,n)) or ('control_stable' if name=='control' else 'inner_not_ready'))
    assert len(seen)==6


def test_numerical_fault_does_not_dispatch_next_case():
    def fail(*_):raise RuntimeError('worker failed')
    with pytest.raises(RuntimeError):r.sequence(fail)


def test_signal_uses_vector_differences_not_difference_of_norms():
    x=np.arange(1,9,dtype=float); control=dict(previous=x,final=x)
    candidate=dict(previous=-x,final=-x)
    row,signals=r.response_measurement(candidate,control,np.ones(2),1/256)
    assert all(np.array_equal(v,-2*x) for v in signals.values())
    assert all(v>0 for v in row['minimum_signal_norms'].values())
    assert row['endpoint_signal_resolved'] and not row['exact_jacobian'] and not row['baseline_replaced']


def test_four_endpoint_combinations_and_two_window_signal_drift():
    x=np.ones(8);control=dict(previous=x,final=x*1.001)
    candidate=dict(previous=x*1.1,final=x*1.101)
    row,signals=r.response_measurement(candidate,control,np.ones(2),1/256)
    assert len(signals)==4 and row['endpoint_signal_resolved']
    shifted={k:v+.2 for k,v in candidate.items()}
    row,_=r.response_measurement(shifted,control,np.ones(2),1/256,signals)
    assert row['endpoint_signal_resolved'] and not row['eight_map_signal_persistent']


def test_zero_signal_is_unresolved_without_floor_or_infinity():
    pair=dict(previous=np.ones(8),final=np.ones(8))
    row,_=r.response_measurement(pair,pair,np.ones(2),1/256)
    assert not row['endpoint_signal_resolved'] and all(v is None for v in row['endpoint_spread_over_signal'].values())


@pytest.mark.parametrize('bad',['missing','nan','shape','alpha','earlier'])
def test_invalid_signal_inputs_fail(bad):
    control=dict(previous=np.ones(8),final=np.ones(8));candidate=deepcopy(control);alpha=1/256;earlier=None
    if bad=='missing':candidate.pop('previous')
    if bad=='nan':candidate['final'][0]=np.nan
    if bad=='shape':candidate['final']=np.ones(4)
    if bad=='alpha':alpha=1/128
    if bad=='earlier':earlier={}
    with pytest.raises(ValueError):r.response_measurement(candidate,control,np.ones(2),alpha,earlier)


@pytest.mark.parametrize('name',r.NAMES)
def test_trials_keep_original_direction_denominator_and_physical_old_level(name):
    base,old=material_fixture(); residual=base['base_residual']
    trial=r.directions.make_trial(base,residual,old,name)
    r.fixed.exact_trial(trial,base,residual,old,name)
    assert np.array_equal(trial['base_residual'],residual)
    assert np.array_equal(trial['encoded_state'],base['encoded_state']+r.directions.ALPHAS[name]*r.directions.split_direction(residual,name))


def test_real_archived_source_gate_and_protocol_factory():
    root=Path('outputs/review-20260925/stationarity-78594-complete-received')
    audit=Path('handoff/evidence/20260928-stationarity-complete-review.json')
    if not root.exists():pytest.skip('Mac received archive is not on this host')
    read=r.pipeline.read
    ret=read(root/'control/endpoints-map16/manifest.json')
    assert r.source_seed(read(root/'summary.json'),read(audit),read(root/'control/state.json'),ret)==ret['endpoints']['mapped_final']
    zero=read(root/'control/pair16/feedback_protocol.json')
    # The archived finite source is a genuine production template, not a mock.
    finite_path=Path('outputs/review-20260925/step21-positive-validation-77126-complete-received/thermal/pair03/feedback_protocol.json')
    if not finite_path.exists():pytest.skip('finite template preflight is performed on the school host')
    finite=read(finite_path)
    for name in r.NAMES:
        p=r.make_protocol(finite,zero,r.ROOT/'outputs/review-20260925/preview'/name,ret,
            zero['sources']['trial_material'],zero['sources']['retained_manifest'],zero['sources']['stationarity_confirmation_declaration'],name)
        assert p['acceptance_gates']==zero['acceptance_gates']
        assert p['authorization'].get('zero_displacement_control',False)==(name=='control')
