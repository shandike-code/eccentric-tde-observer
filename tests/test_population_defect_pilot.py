from copy import deepcopy
import json
from pathlib import Path
import numpy as np
import pytest
from operations import pilot_population_defect_blocks as p


def test_complete_core_selection_uses_squared_defect_and_deterministic_ties():
    rows=[dict(block=i,squared_l2=[0.,1.,0.,0.]) for i in range(76)]
    assert p.choose_cores(rows)==((3,10),14/76)
    assert p.choose_cores(rows[::-1])==p.choose_cores(rows)
    assert p.core_interval(23)==(2560,3456) and p.core_interval(30)==(3456,4352)
    for i in (True,23.,37,44,72):
        with pytest.raises(ValueError):p.core_interval(i)
    rows[75]['squared_l2'][1]=1000.
    assert max(p.choose_cores(rows)[0])<=71  # 不能把末尾32组凑成896组核心


@pytest.mark.parametrize('bad',['missing','duplicate','negative','nan','zero'])
def test_invalid_block_budget_rejected(bad):
    rows=[dict(block=i,squared_l2=[0.,1.,0.,0.]) for i in range(76)]
    if bad=='missing':rows.pop()
    if bad=='duplicate':rows[-1]['block']=0
    if bad=='negative':rows[0]['squared_l2'][1]=-1.
    if bad=='nan':rows[0]['squared_l2'][1]=float('nan')
    if bad=='zero':
        for r in rows:r['squared_l2'][1]=0.
    with pytest.raises(ValueError):p.choose_cores(rows)


def synthetic_source():
    values=[float(i in range(20,34)) for i in range(76)]
    checks={k:k not in {'full_l2_benefit','full_boundary_bolometric','half_boundary_bolometric'} for k in
        ('full_l2_benefit','full_boundary_bolometric','half_boundary_bolometric','independent_half_affinity')}
    row=dict(iteration=1,input_sha256='input',output_sha256='output',output_path='measured.dat')
    audit=dict(job_id=79631,source_job_id=79151,frozen_material_case='population',validated=False,maps=2,
        feedback_pairs=0,new_material_steps=0,checks=checks,
        defect_budget=dict(blocks=[dict(block=i,squared_l2=[0.,v,0.,0.]) for i,v in enumerate(values)]))
    summary=dict(status='stopped_at_full_half_validation',maps=2,map_counts=dict(population=1,half=1),
        new_material_steps=0,accepted_outer_steps=20,baseline_replaced=False)
    val=dict(validated=False,checks=deepcopy(checks),actual_map=row,candidate=dict(path='full.dat',sha256='input',size_bytes=p.pipeline.STATE_BYTES),
        field_comparison=dict(all_groups_evaluated=9632,slabs=deepcopy(audit['defect_budget']['blocks'])))
    state=dict(active_map=None,history=[row],current_sha256='output',slots=['measured.dat'],current_slot=0)
    return audit,summary,val,state


def test_rejected_field_can_be_measured_start_but_is_not_accepted():
    args=synthetic_source();before=deepcopy(args)
    x,y,share=p.validate_source(*args)
    assert x['sha256']=='input' and y['sha256']=='output' and share==1.
    assert args==before and args[1]['accepted_outer_steps']==20 and not args[2]['validated']


@pytest.mark.parametrize('bad',['job','promotion','rebase','accept','failure','partial','unmeasured','successor','slab'])
def test_wrong_source_or_retracted_failure_rejected(bad):
    a,s,v,st=synthetic_source()
    if bad=='job':a['job_id']=79296
    if bad=='promotion':s['new_material_steps']=1
    if bad=='rebase':s['baseline_replaced']=True
    if bad=='accept':v['validated']=True
    if bad=='failure':v['checks']['full_l2_benefit']=True
    if bad=='partial':st['active_map']={}
    if bad=='unmeasured':v['candidate']['sha256']='output'
    if bad=='successor':st['current_sha256']='other'
    if bad=='slab':v['field_comparison']['slabs'][24]['squared_l2'][1]=10.
    with pytest.raises(RuntimeError):p.validate_source(a,s,v,st)


def test_actual_received_source_and_frozen_full_pair():
    root=p.ROOT/'outputs/review-20260925/late-population-global-79631-received'
    if not root.exists():pytest.skip('Mac-only received source; school performs metadata preflight')
    read=lambda path:json.loads(path.read_text())
    args=(read(p.ROOT/'handoff/evidence/20260928-late-population-global-review.json'),
        read(root/'summary.json'),read(root/'population/validation.json'),read(root/'population/state.json'))
    x,y,fraction=p.validate_source(*args)
    assert x['sha256']=='216a31295427601920d77569c31f6433f400fbdc7bbe1f6c17c39d11e35c0fa4'
    assert y['sha256']=='f95b96e06d81347209344904d44e7c27a06b632eb1e4b7254cc27b8278ed4a01'
    assert np.isclose(fraction,.9595429264209813,rtol=1e-15)


def test_bytewise_replay_remains_mandatory():
    x=np.ones(3);mapped=x+.1;changed=mapped.copy();changed[1]=np.nextafter(changed[1],2.)
    assert p.exact_replay(x,mapped,mapped)['array_equal']
    with pytest.raises(RuntimeError):p.exact_replay(x,mapped,changed)
