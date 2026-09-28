import pytest
from handoff.audit_tools.defect_boundary_feasibility import current_anchor_bound


def ledger(d, scale=100.):
    return dict(total_input=scale,total_mapped=scale+d,signed_block_sum=d)


def test_triangle_bound_flags_infeasible_current_anchor():
    r=current_anchor_bound(ledger(-1),ledger(-4),ledger(-1.1),ledger(-2.55),.01)
    assert r['conditional_infeasible'] and r['excess_over_capacity']>0
    assert r['measured_half_signed_error']<1e-14
    assert not r['global_operator_affinity_proved'] and r['observed_error_is_not_uniform_bound']


def test_feasible_limit_and_flux_scale_are_not_discarded():
    assert not current_anchor_bound(ledger(-1),ledger(-2.9),ledger(1),ledger(-.95),.01)['conditional_infeasible']
    assert not current_anchor_bound(ledger(-1),ledger(-4),ledger(-1,200),ledger(-2.5,150),.01)['conditional_infeasible']


@pytest.mark.parametrize('theta',[0,-1,float('nan')])
def test_invalid_gate_is_rejected(theta):
    with pytest.raises(ValueError):current_anchor_bound(*([ledger(-1)]*4),theta)
