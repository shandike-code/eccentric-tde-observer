import pytest
from handoff.audit_tools.review_step21_wide_plane import six_cut


def witness():
    a=[1.,2.,4.,1e-310,2e-310,4e-310]
    return dict(label='p',index=[9500,0,1],inputs_hex=[x.hex() for x in a],row=[-.5,-.75],lower=-1.)


def test_six_state_negative_weak_witness():
    assert six_cut(witness(),(3.,0.))<0


def test_forged_cut_or_positive_witness_rejected():
    c=witness();c['row']=[0.,0.]
    with pytest.raises(AssertionError):six_cut(c,(3.,0.))
    with pytest.raises(AssertionError):six_cut(witness(),(0.,0.))


def test_four_state_witness_not_accepted():
    c=witness();c['inputs_hex']=c['inputs_hex'][:4]
    with pytest.raises(AssertionError):six_cut(c,(3.,0.))
