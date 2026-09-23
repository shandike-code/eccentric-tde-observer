from copy import deepcopy
import pytest
from operations import common_precision_maps as maps


def test_only_precision_failures_authorize_this_refinement():
    gates={k:k not in maps.FAILED for k in maps.REQUIRED_GATES}
    r={'pair_gate_checks':gates,'accepted_outer_steps_remain':15,'material_step_promoted':False,'responses':{k:{'minimum_gas_heat_erg_g':1.} for k in ('previous','final')}}
    assert maps.eligible(r)
    bad=deepcopy(r);bad['responses']['final']['minimum_gas_heat_erg_g']=0;assert not maps.eligible(bad)
    bad=deepcopy(r);bad['pair_gate_checks']['candidate_l2_contraction_pass']=False;assert not maps.eligible(bad)
    bad=deepcopy(r);bad['pair_gate_checks']['fake']=bad['pair_gate_checks'].pop('candidate_l2_contraction_pass');assert not maps.eligible(bad)


def test_second_four_maps_need_progress_and_two_inner_states():
    rows=[dict(residual=r,boundary_l1=.0005,boundary_bolometric=.0004,maximum_worker_rss_mib=3500) for r in (.00008,.00007,.00006,.00005)]
    assert maps.allow_second_half(rows)
    for field,value in [('residual',.0001),('boundary_l1',.001),('maximum_worker_rss_mib',6144),('boundary_bolometric',float('nan'))]:
        bad=deepcopy(rows);bad[-1][field]=value;assert not maps.allow_second_half(bad)
    bad=deepcopy(rows);bad[-1]['residual']=bad[0]['residual'];assert not maps.allow_second_half(bad)
    with pytest.raises(ValueError):maps.allow_second_half(rows[:3])
