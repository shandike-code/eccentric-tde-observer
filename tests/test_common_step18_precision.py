from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace
import numpy as np
import pytest
from operations import common_step18_precision as step


def source():
    summary=dict(status='budget_complete_not_accepted',accepted_outer_steps=17,new_material_steps=0,
        pairs={str(n):dict(inner_pair_ready=False,feedback_evaluated=False) for n in (4,8)})
    rows=[dict(residual=.00018-i*.00001,boundary_l1=.0005,boundary_bolometric=.0004,
        maximum_worker_rss_mib=3500) for i in range(8)]
    return summary,rows


@pytest.mark.parametrize('change',['feedback','accepted','growth','nan','memory','boundary','budget'])
def test_only_audited_inner_budget_exhaustion_is_eligible(change):
    summary,rows=source();assert step.eligible(summary,rows)
    if change=='feedback':summary['pairs']['8']['feedback_evaluated']=True
    if change=='accepted':summary['new_material_steps']=1
    if change=='growth':rows[-1]['residual']=rows[0]['residual']
    if change=='nan':rows[3]['residual']=float('nan')
    if change=='memory':rows[3]['maximum_worker_rss_mib']=6144
    if change=='boundary':rows[-1]['boundary_l1']=.001
    if change=='budget':rows.pop()
    assert not step.eligible(summary,rows)


@pytest.mark.parametrize('mode,expected_maps,expected_pairs,terminal',[
    ('inner',4,0,'stopped_after_four_inner_not_ready'),
    ('physical',4,1,'physical_domain_rejected'),
    ('valid',8,2,'candidate_supported_requires_review'),
])
def test_conditional_budget_runs_no_unearned_maps(monkeypatch,tmp_path,mode,expected_maps,expected_pairs,terminal):
    root=tmp_path;parent=root/'outputs/hpc';parent.mkdir(parents=True);out=parent/'precision'
    monkeypatch.setattr(step,'ROOT',root);monkeypatch.setenv('NUMPY_MADVISE_HUGEPAGE','0')
    monkeypatch.setattr(step.pipeline,'require_allocation',lambda *a:None)
    monkeypatch.setattr(step.shutil,'disk_usage',lambda *a:SimpleNamespace(free=10**15))
    monkeypatch.setattr(step,'prepare',lambda *a:({'seed':{},'code':[],'claims':[]},{},{},np.ones(2)))
    monkeypatch.setattr(step,'relay_dispatch',nullcontext)
    monkeypatch.setattr(step.reused,'checkpoint',lambda:None)
    monkeypatch.setattr(step.reused,'verify',lambda *a:None)
    archives=[];monkeypatch.setattr(step.reused,'archive',lambda out,name:archives.append(name))
    monkeypatch.setattr(step.reused,'feedback_stop_guard',nullcontext)
    state={'history':[],'status':'radiation'}
    def child(out,*args):
        folder=out/'maps';folder.mkdir();(folder/'trial_material.npz').write_bytes(b'trial')
        return folder,{},state
    monkeypatch.setattr(step.reused,'child',child)
    def mapping(*args):
        n=len(state['history'])
        state['history'].append(dict(residual=(.0002 if mode=='inner' else .00009)-n*.000001,
            boundary_l1=.0001,boundary_bolometric=.0001,maximum_worker_rss_mib=3500))
        return True
    monkeypatch.setattr(step.driver,'run_one_map',mapping)
    def retain(out,state):
        dest=out/f"endpoints-map{len(state['history']):02d}";dest.mkdir()
        step.pipeline.write_json(dest/'manifest.json',dict(endpoints={},history_rows=state['history'][-2:]))
    monkeypatch.setattr(step,'retain_pair',retain)
    monkeypatch.setattr(step.pipeline,'claim',lambda p:{'path':str(p),'sha256':'synthetic'})
    monkeypatch.setattr(step.fresh,'new_protocol',lambda *a:dict(sources={},common_code_claims=[]))
    monkeypatch.setattr(step.fresh,'attach_code',lambda *a:None)
    monkeypatch.setattr(step.fresh,'exact_identity',lambda *a:None)
    pairs=[]
    def feedback(*a):
        pairs.append(1)
        return dict(gate_checks={},material_response_failures={'final':'nonpositive gas'} if mode=='physical' else {})
    monkeypatch.setattr(step.pair,'run_pair',feedback)
    monkeypatch.setattr(step,'verify_step18_pair',lambda *a:None)
    monkeypatch.setattr(step,'all_pair_gates',lambda *a:True)
    monkeypatch.setattr(step,'load_arrays',lambda *a:dict(residual=np.ones(2)))
    monkeypatch.setattr(step,'cross_comparisons',lambda *a:dict(passed=True,ratios={}))
    step.execute(out)
    assert len(state['history'])==expected_maps and len(pairs)==expected_pairs
    result=step.pipeline.read(out/'status.json')
    assert result['status']==terminal and result['accepted_outer_steps']==17 and result['new_material_steps']==0
    assert archives
