from copy import deepcopy
import numpy as np
import pytest
from operations import confirm_step21_stationarity as c


def window():
    return c.original.window_comparison({'previous':np.ones(8),'final':np.ones(8)},
        {'previous':np.ones(8),'final':np.ones(8)},np.ones(8),np.ones(2))


def fixture():
    w=window();g={k:True for k in c.ZERO_GATES}
    row=dict(zero_control_stable=True,conditional_continuation_pass=True,original_gates=g,window_comparison=w)
    summary=dict(status='seven_refresh_short_validation_complete_requires_review',maps=11,control_maps=10,half_maps=1,
        accepted_outer_steps=20,new_material_steps=0,baseline_replaced=False,strict_error_bound=False,cases={'2':row,'10':deepcopy(row)})
    audit=dict(job_id=78548,final_summary_present=True,feedback_rounds=[2,10],accepted_outer_steps=20,new_material_steps=0,
        baseline_replaced=False,strict_error_bound=False,windows={n:dict(window=deepcopy(w),gate_checks=deepcopy(g)) for n in ('2','10')})
    history=[dict(input_sha256=str(i),output_sha256=str(i+1)) for i in range(10)]
    state=dict(history=history,active_map=None)
    retained=dict(history_rows=deepcopy(history[-2:]),endpoints={'previous':dict(sha256='8'),'final':dict(sha256='9'),
        'mapped_final':dict(path='latest.dat',sha256='10',size_bytes=c.pipeline.STATE_BYTES)})
    return summary,audit,state,retained


def test_source_is_last_audited_successor_without_replacing_residual():
    args=fixture();before=deepcopy(args);seed=c.source_seed(*args)
    assert seed==args[3]['endpoints']['mapped_final'] and args==before


@pytest.mark.parametrize('bad',['status','new_step','rebased','job','partial_audit','gate','missing_gate','audit_gate','window',
    'partial_map','history','chain','input','seed','size'])
def test_source_must_be_complete_stable_and_exact(bad):
    s,a,st,r=fixture()
    if bad=='status':s['status']='second_control_pair_not_stable'
    if bad=='new_step':s['new_material_steps']=1
    if bad=='rebased':s['baseline_replaced']=True
    if bad=='job':a['job_id']=78161
    if bad=='partial_audit':a['final_summary_present']=False
    if bad=='gate':s['cases']['10']['original_gates']['physical_response_pass']=False
    if bad=='missing_gate':s['cases']['10']['original_gates']={}
    if bad=='audit_gate':a['windows']['10']['gate_checks']['physical_response_pass']=False
    if bad=='window':s['cases']['10']['window_comparison']['passed']=False
    if bad=='partial_map':st['active_map']={}
    if bad=='history':st['history'].pop()
    if bad=='chain':st['history'][1]['output_sha256']='wrong'
    if bad=='input':r['endpoints']['final']['sha256']='wrong'
    if bad=='seed':r['endpoints']['mapped_final']['sha256']='9'
    if bad=='size':r['endpoints']['mapped_final']['size_bytes']=1
    with pytest.raises(RuntimeError):c.source_seed(s,a,st,r)


@pytest.mark.parametrize('bad',['missing','shape','nan','negative','threshold','strict_bound','rebased','verdict'])
def test_window_does_not_trust_passed_flag(bad):
    w=window();rows=w['vector_difference_over_frozen_r20_norms']
    if bad=='missing':rows.pop('final_vs_final')
    if bad=='shape':rows['final_vs_final'].pop()
    if bad=='nan':rows['final_vs_final'][0]=np.nan
    if bad=='negative':rows['final_vs_final'][0]=-1
    if bad=='threshold':w['tolerance']=.01
    if bad=='strict_bound':w['strict_error_bound']=True
    if bad=='rebased':w['baseline_replaced']=True
    if bad=='verdict':rows['final_vs_final'][0]=.002
    with pytest.raises((RuntimeError,ValueError)):c.validate_window(w)


def test_equality_to_threshold_fails_and_all_components_remain():
    w=window();w['vector_difference_over_frozen_r20_norms']['final_vs_final'][2]=.001;w['passed']=False
    assert not c.validate_window(w)


def test_sequence_stops_after_first_failed_window():
    maps=[];pairs=[]
    result=c.sequence(maps.append,lambda n:pairs.append(n) or False)
    assert maps==list(range(1,9)) and pairs==[8] and result=='stationarity_not_confirmed'


def test_sequence_full_budget_and_second_failed_window():
    for fail in (False,True):
        maps=[];pairs=[]
        result=c.sequence(maps.append,lambda n:pairs.append(n) or not(fail and n==16))
        assert maps==list(range(1,17)) and pairs==[8,16]
        assert result==('stationarity_not_confirmed' if fail else 'persistent_control_stationarity_requires_review')


def test_mapping_failure_never_dispatches_feedback():
    def stop(_):raise c.reused.Stopped('partial')
    with pytest.raises(c.reused.Stopped):c.sequence(stop,lambda _:pytest.fail('partial feedback'))


def test_cumulative_can_fail_while_individual_windows_pass():
    mass=np.ones(2);r=np.ones(8)
    pair=lambda scale:{'previous':r*scale,'final':r*scale}
    a,b,z=pair(1.0006),pair(1.0012),pair(1.)
    assert c.validate_window(c.original.window_comparison(a,z,r,mass))
    assert c.validate_window(c.original.window_comparison(b,a,r,mass))
    assert not c.validate_window(c.original.window_comparison(b,z,r,mass))
