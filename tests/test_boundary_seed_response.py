from copy import deepcopy
import pytest
from operations import diagnose_boundary_seed_response as diagnostic


def source():
    row=dict(iteration=1,input_sha256='candidate',output_path='outputs/test/mapped.dat',output_sha256='mapped',
             residual=5e-7,boundary_l1=2e-8,boundary_bolometric=1e-9)
    old={**row,'boundary_l1':6e-8,'boundary_bolometric':1e-8}
    q={**row,'boundary_l1':3e-8,'boundary_bolometric':3e-8}
    h={**row,'boundary_l1':4e-8,'boundary_bolometric':5e-9}
    d=dict(source_row=old,prior_q_row=q,coefficients=dict(a=.4892755093069306,b=1.))
    val=dict(field_comparison=dict(fixed_scale_l2_ratios=[1.,.42,.69,1e-9],fixed_scale_linf_ratios=[1.,.93,.71,2e-9]),
             prior_q_comparison=dict(fixed_scale_l2_ratios=[1.,.43,.72],fixed_scale_linf_ratios=[1.,.93,.71]),
             actual_map=row,half_map=h,candidate=dict(sha256='candidate'),validated=False)
    val['checks']=diagnostic.foundation.fields.checks(val['field_comparison'],val['prior_q_comparison'],old,q,row,h)
    audit=dict(job_id=80052,accepted_outer_steps=20,new_material_steps=0,independent_slab_and_block_reduction=True,
               validated=False,checks=deepcopy(val['checks']))
    summary=dict(status='stopped_at_full_half_validation',maps=2,new_material_steps=0)
    state=dict(active_map=None,history=[deepcopy(row)],current_sha256='mapped',current_slot=0,slots=[row['output_path']])
    return audit,summary,d,val,state


def test_only_the_audited_mapped_field_can_seed_diagnostic():
    data=source();seed=diagnostic.require_rejected_source(*data)
    assert seed==dict(path='outputs/test/mapped.dat',sha256='mapped',size_bytes=10099884032)
    assert data[0]['validated'] is False and data[3]['validated'] is False


@pytest.mark.parametrize('index,key,value',[(0,'job_id',79878),(0,'validated',True),
    (0,'independent_slab_and_block_reduction',False),(0,'new_material_steps',1),
    (1,'status','passed'),(1,'maps',3),(2,'coefficients',dict(a=.5,b=1.)),
    (3,'validated',True),(4,'active_map',dict(pending=True))])
def test_crossed_or_reinterpreted_experiment_is_rejected(index,key,value):
    data=source();data[index][key]=value
    with pytest.raises(RuntimeError):diagnostic.require_rejected_source(*data)


def test_claimed_checks_are_recomputed_and_not_trusted():
    data=source();data[3]['actual_map']['boundary_l1']=9e-8
    with pytest.raises(RuntimeError):diagnostic.require_rejected_source(*data)


@pytest.mark.parametrize('field,value',[('current_sha256','bad'),('slots',['wrong/path'])])
def test_seed_must_be_the_settled_output(field,value):
    data=source();data[4][field]=value
    with pytest.raises(RuntimeError,match='settled'):diagnostic.require_rejected_source(*data)


@pytest.mark.parametrize('gate',sorted(diagnostic.REQUIRED_GATES))
def test_every_noncontraction_science_gate_stops_diagnostic(gate):
    gates={k:True for k in diagnostic.REQUIRED_GATES|diagnostic.CONTRACTION_GATES};gates[gate]=False
    r=diagnostic.diagnostic_gate_report(gates)
    assert r['required_gate_failures']==[gate] and not r['may_continue_diagnostic'] and not r['accepted_material_step']


def test_failed_contraction_is_preserved_without_promotion():
    gates={k:True for k in diagnostic.REQUIRED_GATES}
    gates.update({k:False for k in diagnostic.CONTRACTION_GATES})
    r=diagnostic.diagnostic_gate_report(gates)
    assert r['may_continue_diagnostic'] and len(r['contraction_gate_failures'])==3
    assert r['historical_acceleration_veto_retained'] and not r['original_all_16_pass'] and not r['accepted_material_step']
    gates.update({k:True for k in diagnostic.CONTRACTION_GATES})
    assert not diagnostic.diagnostic_gate_report(gates)['accepted_material_step']
    gates.pop('inner_noise_resolved_pass')
    with pytest.raises(RuntimeError):diagnostic.diagnostic_gate_report(gates)


@pytest.mark.parametrize('stop_at',range(4))
def test_failure_stops_before_dispatching_any_later_window(stop_at):
    order=[]
    def evaluate(name,n):
        order.append((name,n));return 'domain_failed' if len(order)-1==stop_at else 'pass'
    status=diagnostic.sequence(evaluate)
    expected=[('control',2),('population',2),('control',10),('population',10)]
    assert order==expected[:stop_at+1] and status.endswith('domain_failed')


def test_complete_budget_stays_diagnostic():
    order=[]
    result=diagnostic.sequence(lambda name,n:(order.append((name,n)) or 'pass'))
    assert order==[('control',2),('population',2),('control',10),('population',10)]
    assert result=='diagnostic_response_windows_complete_requires_review'
    assert diagnostic.LIMITS==dict(control=10,population=10)


def test_actual_received_seed_provenance():
    root=diagnostic.ROOT/'outputs/review-20260925/boundary-global-80052-received'
    if not root.exists():pytest.skip('Mac-only received metadata; school preflight reads its own immutable source')
    read=diagnostic.pipeline.read
    data=[read(diagnostic.ROOT/'handoff/evidence/20260928-boundary-global-review.json'),
          read(root/'summary.json'),read(root/'declaration.json'),read(root/'population/validation.json'),read(root/'population/state.json')]
    seed=diagnostic.require_rejected_source(*data)
    assert seed['sha256']=='23bd9f957813f3d7dc1734342b7789804fa9f9563f8c69118dd0368a285796cb'
