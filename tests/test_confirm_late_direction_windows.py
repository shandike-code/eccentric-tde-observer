from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from operations import confirm_late_direction_windows as late
from test_remeasure_step21_directions import source_fixture as old_fixture


def fixture():
    old, _, state, retained = old_fixture()
    w = old['windows']['16']['window_comparison']
    measure = dict(endpoint_signal_resolved=True,eight_map_signal_persistent=False,
                   strict_error_bound=False,exact_jacobian=False)
    summary = dict(status='refreshed_direction_measurement_requires_review',maps=48,
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,cases={})
    audit = dict(job_id=78950,final_summary_present=True,events=[[n,k] for n in (8,16) for k in late.NAMES],
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,maps={},pairs={})
    states, retaineds = {}, {}
    for k in late.NAMES:
        summary['cases'][k]={};audit['maps'][k]=list(range(16))
        states[k]=deepcopy(state);retaineds[k]=deepcopy(retained)
        for row in states[k]['history']:
            row['input_sha256']=k+row['input_sha256'];row['output_sha256']=k+row['output_sha256']
        retaineds[k]['history_rows']=deepcopy(states[k]['history'][-2:])
        for c in retaineds[k]['endpoints'].values():c['sha256']=k+c['sha256']
        retaineds[k]['endpoints']['mapped_final']['path']=k+'/latest.dat'
        for n in (8,16):
            s=dict(feedback_evaluated=True,physical_response_failures={},promoted=False,baseline_replaced=False,
                   original_gates=deepcopy(old['windows']['16']['original_gates']))
            a=dict(gate_checks=deepcopy(s['original_gates']))
            if k=='control':
                s.update(control_pass=True,window_comparison=deepcopy(w),from_78594_comparison=deepcopy(w))
                a.update(control_pass=True,window=deepcopy(w),cumulative=deepcopy(w))
            else:s['response_measurement']=deepcopy(measure);a['response_measurement']=deepcopy(measure)
            summary['cases'][k][str(n)]=s;audit['pairs'][f'{k}{n:02d}']=a
    return summary,audit,states,retaineds


def test_continuation_preserves_each_own_successor_and_source():
    args=fixture();before=deepcopy(args);seeds=late.validate_source(*args)
    assert args==before
    assert len({s['sha256'] for s in seeds.values()})==3
    for k in late.NAMES:assert seeds[k]==args[3][k]['endpoints']['mapped_final']


@pytest.mark.parametrize('bad',['partial','job','counter','rebase','strict','domain','promoted','control_gate',
    'control_window','endpoint','persistence','map_count','chain','input','swapped_seed','seed_size'])
def test_invalid_source_fails_closed(bad):
    s,a,st,ret=fixture()
    if bad=='partial':a['final_summary_present']=False
    if bad=='job':a['job_id']=78594
    if bad=='counter':s['new_material_steps']=1
    if bad=='rebase':s['baseline_replaced']=True
    if bad=='strict':a['strict_error_bound']=True
    if bad=='domain':s['cases']['population']['16']['physical_response_failures']={'final':'no gas'}
    if bad=='promoted':s['cases']['thermal']['16']['promoted']=True
    if bad=='control_gate':
        s['cases']['control']['16']['original_gates']={};a['pairs']['control16']['gate_checks']={}
    if bad=='control_window':a['pairs']['control16']['cumulative']['passed']=False
    if bad=='endpoint':s['cases']['population']['16']['response_measurement']['endpoint_signal_resolved']=False
    if bad=='persistence':a['pairs']['thermal16']['response_measurement']['eight_map_signal_persistent']=True
    if bad=='map_count':st['control']['history'].pop()
    if bad=='chain':st['thermal']['history'][2]['output_sha256']='wrong'
    if bad=='input':ret['population']['endpoints']['previous']['sha256']='wrong'
    if bad=='swapped_seed':ret['population']['endpoints']['mapped_final']=ret['control']['endpoints']['mapped_final']
    if bad=='seed_size':ret['thermal']['endpoints']['mapped_final']['size_bytes']=1
    with pytest.raises((RuntimeError,ValueError)):late.validate_source(s,a,st,ret)


@pytest.mark.parametrize('failed_at',range(7))
def test_first_failed_late_window_stops_all_later_work(failed_at):
    order=[(k,n) for n in (8,16) for k in late.NAMES];seen=[]
    def evaluate(k,n):
        seen.append((k,n));return 'late_window_not_confirmed' if len(seen)==failed_at else 'late_window_pass'
    status=late.sequence(evaluate)
    assert seen==(order[:failed_at] if failed_at else order)
    assert (status=='late_direction_windows_complete_requires_review')==(failed_at==0)


def test_numerical_fault_is_not_converted_to_pass_or_next_case():
    seen=[]
    def evaluate(*args):seen.append(args);raise RuntimeError('worker failed')
    with pytest.raises(RuntimeError,match='worker failed'):late.sequence(evaluate)
    assert seen==[('control',8)]


def window(delta):
    pair=dict(previous=np.ones(8),final=np.ones(8))
    current={k:v+delta for k,v in pair.items()}
    return late.station.original.window_comparison(current,pair,np.ones(8),np.ones(2))


def test_historical_exceedance_is_retained_without_claiming_original_stability():
    result=late.control_decision(True,window(.0001),window(.0002),window(.002))
    assert result==dict(control_pass=True,historical_78594_cumulative_pass=False,
                       original_78594_cumulative_stability_claim=False)


@pytest.mark.parametrize('which',['seven_gates','window','cumulative'])
def test_local_control_rejects_each_required_condition(which):
    result=late.control_decision(which!='seven_gates',window(.002 if which=='window' else .0001),
        window(.002 if which=='cumulative' else .0002),window(.0003))
    assert not result['control_pass']


def test_small_last_window_cannot_hide_cumulative_direction_drift():
    control=dict(previous=np.ones(8),final=np.ones(8))
    origin={k:v+1 for k,v in control.items()};earlier={k:v+1.11 for k,v in control.items()}
    current={k:v+1.2 for k,v in control.items()}
    measure=late.prior.response_measurement
    first=measure(origin,control,np.ones(2),1/256)[1]
    last=measure(earlier,control,np.ones(2),1/256)[1]
    w,_=measure(current,control,np.ones(2),1/256,last)
    c,_=measure(current,control,np.ones(2),1/256,first)
    assert w['eight_map_signal_persistent'] and not c['eight_map_signal_persistent']
    assert not late.direction_pass(w,c)


def test_zero_or_unresolved_direction_cannot_pass():
    pair=dict(previous=np.ones(8),final=np.ones(8))
    measure,signals=late.prior.response_measurement(pair,pair,np.ones(2),1/256)
    later,_=late.prior.response_measurement(pair,pair,np.ones(2),1/256,signals)
    assert not late.direction_pass(later,later) and not measure['endpoint_signal_resolved']


def test_real_complete_source_and_unmodified_original_gates():
    root=Path('outputs/review-20260925/refreshed-directions-78950-complete-received')
    if not root.exists():pytest.skip('Mac archive not installed; use school small-input preflight')
    read=late.pipeline.read
    states={k:read(root/k/'state.json') for k in late.NAMES}
    retained={k:read(root/k/'endpoints-map16/manifest.json') for k in late.NAMES}
    seeds=late.validate_source(read(root/'summary.json'),read(late.ROOT/late.AUDIT),states,retained)
    zero=read(root/'control/pair16/feedback_protocol.json');finite=read(root/'thermal/pair16/feedback_protocol.json')
    for k in late.NAMES:
        assert seeds[k]==retained[k]['endpoints']['mapped_final']
        p=late.prior.make_protocol(finite,zero,late.ROOT/'outputs/preview'/k,retained[k],
            zero['sources']['trial_material'],zero['sources']['retained_manifest'],zero['sources']['refreshed_direction_declaration'],k)
        assert p['acceptance_gates']==zero['acceptance_gates'] and p['formal_state_gates']==zero['formal_state_gates']
        assert p['authorization'].get('zero_displacement_control',False)==(k=='control')
