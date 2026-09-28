import math
import pytest
from handoff.audit_tools.population_global_decomposition import defect_budget,boundary_ledger


def test_disjoint_budget_and_conditional_ceiling_are_not_local_gain():
    rows=[dict(block=i,squared_l2=[a,b,(a+b)/2,0.],linf=[1.]*4,output_change_linf=c)
        for i,a,b,c in [(33,81.,81.,0.),(34,9.,.09,1.),(48,10.,11.,.1)]]
    result=defect_budget(rows,selected=(34,))
    assert result['regions']['selected']['original_square_fraction']==.09
    assert result['regions']['unselected_changed_output']['blocks']==[48]
    assert result['regions']['unselected_unchanged_output']['blocks']==[33]
    assert result['hypothetical_ratio_if_selected_zero_and_all_others_unchanged']==math.sqrt(.91)
    assert not result['strict_solution_error_bound']


def test_signed_cancellation_can_increase_net_while_absolute_decreases():
    def ledger(ds):return boundary_ledger([dict(block_index=i,current_boundary_bolometric=100.,mapped_boundary_bolometric=100.+d) for i,d in enumerate(ds)])
    a,b=ledger([10.,-9.]),ledger([5.,-2.])
    assert b['absolute_block_change_sum']<a['absolute_block_change_sum']
    assert b['net_block_sum_over_scale']>a['net_block_sum_over_scale']
    assert a['summation_closure_over_scale']==b['summation_closure_over_scale']==0


def test_zero_flux_and_nonfinite_rejected():
    for value in (0.,float('nan')):
        with pytest.raises(ValueError):boundary_ledger([dict(block_index=0,current_boundary_bolometric=value,mapped_boundary_bolometric=value)])
