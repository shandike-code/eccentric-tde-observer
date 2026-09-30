import pytest
from handoff.audit_tools.review_x20_cross_seed_chord import reduce_independent,verify_slabs


def test_analytical_decay():
    r=reduce_independent([dict(dd=4.,de=-.8,ee=.16,difference_linf=2.,change_linf=.4)])
    assert r['rayleigh_action']==pytest.approx(.8) and r['mapped_difference_l2_ratio']==pytest.approx(.8)


def test_gram_impossible_moments_rejected():
    with pytest.raises(ValueError):reduce_independent([dict(dd=1.,de=2.,ee=1.,difference_linf=1.,change_linf=1.)])


def test_black_block_has_no_defined_ratio():
    r=reduce_independent([dict(dd=0.,de=0.,ee=0.,difference_linf=0.,change_linf=0.)])
    assert r['zero_difference'] and r['rayleigh_action'] is None


def test_frequency_hole_rejected():
    rows=[dict(first_group=i*32,group_count=32,block=i//4) for i in range(301)]
    verify_slabs(rows);rows[75]['first_group']+=1
    with pytest.raises(AssertionError):verify_slabs(rows)
