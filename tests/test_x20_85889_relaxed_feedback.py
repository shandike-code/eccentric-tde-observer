from copy import deepcopy
from pathlib import Path
import json
import numpy as np
import pytest
from operations import x20_85889_relaxed_feedback as c
from handoff.audit_tools import review_x20_85889_relaxed_feedback as audit


def test_one_new_window_each_branch():
    visits=[]
    assert c.sequence(lambda name,n:visits.append((name,n)) or 'pass')=='paired_seed_windows_complete_requires_review'
    assert visits==[('accelerated',8),('historical',8)]


@pytest.mark.parametrize('index',[0,1])
def test_failure_never_dispatches_later_branch(index):
    visits=[]
    def evaluate(name,n):
        visits.append((name,n));return 'physical_domain_rejected' if len(visits)==index+1 else 'pass'
    assert c.sequence(evaluate).endswith('physical_domain_rejected')
    assert len(visits)==index+1


def comparison(ratio=.005,signal=.5):
    keys=[a+'_vs_'+b for a in ('previous','final') for b in ('previous','final')]
    return dict(frozen_r20=dict(vector_difference_over_frozen_r20_norms={k:[ratio]*3 for k in keys},passed=False,tolerance=.001),
        vector_difference_over_frozen_80195_signal={k:[signal]*3 for k in keys},passed=False,signal_tolerance=.1)


def test_old_failure_is_preserved_and_new_gate_is_explicit():
    x=comparison();before=deepcopy(x);y=c.annotate(x)
    assert x==before and y['passed'] is False
    assert y['relaxed_response_consistency']['passed'] is True
    assert y['relaxed_response_consistency']['reference_calibration_eligible'] is False


@pytest.mark.parametrize('ratio,signal',[(.01,.5),(.005,1.),(.011,.5),(.005,1.1)])
def test_strict_equality_or_excess_is_failure(ratio,signal):
    assert not c.annotate(comparison(ratio,signal))['relaxed_response_consistency']['passed']


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1.,True])
def test_invalid_ratios_rejected(value):
    with pytest.raises(ValueError):c.annotate(comparison(value,.5))


@pytest.mark.parametrize('damage',['missing','short','extra','order'])
def test_all_combinations_and_norms_required(damage):
    x=comparison();rows=x['frozen_r20']['vector_difference_over_frozen_r20_norms']
    if damage=='missing':rows.pop('final_vs_final')
    if damage=='short':rows['final_vs_final'].pop()
    if damage=='extra':rows['extra']=[0.]*3
    if damage=='order':x['frozen_r20']['vector_difference_over_frozen_r20_norms']=dict(reversed(list(rows.items())))
    with pytest.raises(ValueError):c.annotate(x)


def experiment():
    row=dict(feedback_evaluated=True,zero_pair_stable=True,physical_response_failures={},original_zero_gates={str(i):True for i in range(7)},
        eight_map_window=c.annotate(comparison()))
    return {name:{'8':deepcopy(row)} for name in c.LIMITS},{'8':dict(residual_comparison=c.annotate(comparison()),cross_rate_pass=True)}


@pytest.mark.parametrize('damage',['none','rate','physics','oldgate','window','cross','missing','incomplete'])
def test_eligibility_requires_hard_gates_and_complete_matched_window(damage):
    reports,cross=experiment();terminal='paired_seed_windows_complete_requires_review'
    if damage=='rate':cross['8']['cross_rate_pass']=False
    if damage=='physics':reports['accelerated']['8']['physical_response_failures']={'cell':3}
    if damage=='oldgate':reports['historical']['8']['original_zero_gates']['0']=False
    if damage=='window':reports['accelerated']['8']['eight_map_window']['relaxed_response_consistency']['passed']=False
    if damage=='cross':cross['8']['residual_comparison']['relaxed_response_consistency']['passed']=False
    if damage=='incomplete':terminal='interrupted'
    if damage=='missing':
        del reports['historical']['8']
        with pytest.raises(ValueError):c.relaxed_consistency_pass(terminal,reports,cross)
    else:assert c.relaxed_consistency_pass(terminal,reports,cross)==(damage=='none')


def test_independent_full_vector_comparison():
    mass=np.linspace(1.,2.,128);r20=np.linspace(1.,3.,512)
    old={e:r20*i for i,e in enumerate(('previous','final'))}
    new={e:x+.003*r20 for e,x in old.items()};scale=np.array([1.,.1,.2])
    actual=c.vector_comparison(new,old,r20,mass,scale)
    expected=audit.comparison(new,old,r20,mass,scale)
    audit.prior.same_record(actual,expected)


def source():
    p=c.ROOT/'outputs/review-20260925/x20-85875-matched-85889-received'
    return p if p.exists() else c.ROOT/c.SOURCES['accelerated'][0]


def test_real_source_seeds_and_trial():
    p=source();cfgs=[];trials=[]
    for name in c.LIMITS:
        c.require_source(c.pipeline.read(c.ROOT/'handoff/evidence'/c.SOURCES[name][2]),c.pipeline.read(p/'summary.json'),name)
        st=c.pipeline.read(p/name/'state.json');m=c.pipeline.read(p/name/'endpoints-map16/manifest.json')
        seed=c.seed_claim(name,st,m);assert seed['sha256']==c.SEED_SHA[name] and seed!=m['endpoints']['final']
        bad=deepcopy(m);bad['endpoints']['mapped_final']=bad['endpoints']['final']
        with pytest.raises(ValueError):c.seed_claim(name,st,bad)
        cfgs.append(c.pipeline.read(p/name/'config.json'));trials.append(c.v.load_arrays(p/name/'trial_material.npz'))
    c.core.same_operator_config(*cfgs);c.fixed.same_trial(*trials)


@pytest.mark.parametrize('key,value',[('scheduler_terminal_verified',False),('source_84026_scheduler_terminal_verified',True),('child_exit_status',False),('map_process_receipts',0),('numerical_commit','wrong'),('new_material_steps',1)])
def test_bad_source_rejected(key,value):
    p=source();a=c.pipeline.read(c.ROOT/'handoff/evidence'/c.SOURCES['accelerated'][2]);a[key]=value
    with pytest.raises(ValueError):c.require_source(a,c.pipeline.read(p/'summary.json'),'accelerated')


def test_old_85889_cross_still_fails_new_mass_gates():
    x=c.pipeline.read(source()/'summary.json')['cross_history']['16']['residual_comparison'];y=c.annotate(x)
    assert not y['relaxed_response_consistency']['passed']
    a=np.max(list(x['frozen_r20']['vector_difference_over_frozen_r20_norms'].values()),axis=0)
    b=np.max(list(x['vector_difference_over_frozen_80195_signal'].values()),axis=0)
    assert a[0]<.01 and a[1]>.01 and a[2]<.01 and b[0]<1 and b[1]>1 and b[2]<1


def test_eight_map_cap_before_dispatch(monkeypatch):
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    for limit,history in [(8,[{}]*8),(16,[]),(True,[])]:
        with pytest.raises(RuntimeError):c.map_once(Path('/unused'),{},dict(history=history),limit)


@pytest.mark.parametrize('fault',['partial','count','active','rss','missing_receipt'])
def test_map_completion_and_resource_guards(tmp_path,monkeypatch,fault):
    state=dict(history=[],active_map=None,status='radiation')
    monkeypatch.setattr(c.reused,'checkpoint',lambda:None)
    def run(folder,cfg,st,path):
        if fault=='partial':return False
        st['history'].extend([{}]*(2 if fault=='count' else 1));st['active_map']={} if fault=='active' else None
        d=folder/f"map{len(st['history']):04d}";d.mkdir()
        for i in range(75 if fault=='missing_receipt' else 76):
            c.pipeline.write_json(d/f'block{i:02d}.process-1.json',dict(returncode=0,memory_guard_passed=True,native_observed_peak_kib=6*1024**2 if fault=='rss' else 1000))
        return True
    monkeypatch.setattr(c.old.recovery.original.driver,'run_one_map',run)
    with pytest.raises((RuntimeError,c.reused.Stopped)):c.map_once(tmp_path,{},state,8)
