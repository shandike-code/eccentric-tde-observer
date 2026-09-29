from types import SimpleNamespace
import json
import numpy as np
import pytest
from operations import x20_long_chord as module


def test_expanded_gram_matches_direct_affine_defect_and_original_prefix():
    rng=np.random.default_rng(27);fields=[rng.uniform(.1,1,(4,2,3)) for _ in range(8)]
    a,b,c,h,j,k,x,y=fields;r=c-b
    f=[r,(b-a)-r,(j-h)-r,(k-j)-r,(y-x)-r]
    direct=np.array([[np.vdot(u,v) for v in f] for u in f])
    measured=module.basis_moments(fields)
    np.testing.assert_allclose(measured,direct,rtol=2e-15,atol=1e-14)
    coeff=np.array([.1,-.2,.3,.15]);z=b+coeff[0]*(a-b)+coeff[1]*(h-b)+coeff[2]*(j-b)+coeff[3]*(x-b)
    p=c+coeff[0]*(b-c)+coeff[1]*(j-c)+coeff[2]*(k-c)+coeff[3]*(y-c)
    u=np.r_[1,coeff];assert np.isclose(u@measured@u,np.sum((p-z)**2),rtol=1e-14)


def fake_driver(folder,receipts=76):
    def run(run,cfg,state,path):
        n=len(state['history'])+1;d=folder/f'map{n:04d}';d.mkdir()
        for i in range(receipts):(d/f'block{i:02d}.process-1.json').write_text(json.dumps(dict(returncode=0,memory_guard_passed=True,native_observed_peak_kib=10)))
        state['history'].append(dict(residual=1e-6,boundary_l1=1e-8,boundary_bolometric=1e-8,maximum_worker_rss_mib=1))
        return True
    return SimpleNamespace(run_one_map=run,FAULT_STATUSES=('failed',))


def test_exactly_four_maps_and_no_feedback_dispatch(tmp_path,monkeypatch):
    monkeypatch.setattr(module.reused,'checkpoint',lambda:None)
    state=dict(history=[],active_map=None,status='radiation');before=[]
    module.advance_four(tmp_path,{},state,fake_driver(tmp_path),before.append)
    assert before==[0,1,2,3] and len(state['history'])==4
    with pytest.raises(ValueError):module.advance_four(tmp_path,{},state,fake_driver(tmp_path),before.append)


def test_missing_receipt_stops_before_second_map(tmp_path,monkeypatch):
    monkeypatch.setattr(module.reused,'checkpoint',lambda:None)
    state=dict(history=[],active_map=None,status='radiation')
    with pytest.raises(RuntimeError,match='receipt'):module.advance_four(tmp_path,{},state,fake_driver(tmp_path,75),lambda n:None)
    assert len(state['history'])==1


def test_stop_prevents_dispatch(tmp_path,monkeypatch):
    def stop():raise module.reused.Stopped('test signal')
    monkeypatch.setattr(module.reused,'checkpoint',stop)
    state=dict(history=[],active_map=None,status='radiation')
    with pytest.raises(module.reused.Stopped):module.advance_four(tmp_path,{},state,fake_driver(tmp_path),lambda n:None)
    assert state['history']==[] and not list(tmp_path.iterdir())


def test_unreviewed_exclusion_is_not_a_launch_basis():
    with pytest.raises(ValueError):module.require_fullspace_review({},dict(status='no_20pct_candidate_in_full_registered_cap'))
