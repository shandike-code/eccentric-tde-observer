import numpy as np
import pytest
from operations.x20_83063_subnormal_audit import exact_sign,audit_slab


def test_true_negative_half_can_round_to_zero_without_being_positive():
    tiny=float.fromhex('0x0.0000000000001p-1022')
    r=exact_sign([0.,tiny,0.,0.],[-1.,0.,0.])
    assert r['full']['sign']==r['half']['sign']==-1
    assert float.fromhex(r['half']['rounded_binary64_hex'])==0


def test_exact_cancellation_is_not_reported_as_negative():
    t=float.fromhex('0x0.0000000000001p-1022')
    r=exact_sign([t,2*t,0.,0.],[-1.,0.,0.])
    assert r['full']['sign']==0 and r['half']['sign']==1


def test_counts_cover_every_duplicate_and_keep_global_indices():
    aa=[np.zeros((2,2,2)) for _ in range(8)];aa[2][:]=float.fromhex('0x0.0000000000001p-1022')
    rows=audit_slab(aa,[-1.,0.,0.],9440)
    assert len(rows)==1 and rows[0]['negative_count']==8 and rows[0]['unique_count']==1
    assert rows[0]['cases'][0]['first_index']==[9440,0,0]
    assert rows[0]['exact_half_sign_counts']['-1']==8


def test_exact_audit_budget_failure_is_not_sampling():
    aa=[np.zeros((1,1,2)) for _ in range(8)];aa[2][0,0]=[1.,2.]
    with pytest.raises(RuntimeError):audit_slab(aa,[-1.,0.,0.],0,max_unique=1)


def test_nonfinite_inputs_rejected():
    with pytest.raises(ValueError):exact_sign([0.,float('nan'),0.,0.],[1.,0.,0.])


def test_full_and_half_are_both_covered():
    aa=[np.zeros((1,1,3)) for _ in range(8)];aa[2][:]=1.;aa[3][:]=1.
    rows=audit_slab(aa,[-1.,0.,0.],9440)
    assert {r['kind'] for r in rows}=={'input','predicted_output','half_input','half_predicted_output'}
    assert all(r['negative_count']==3 for r in rows)
    assert all(r['cases'][0]['full_direction_upper_fraction']['numerator']=='0' for r in rows)


def test_exact_fraction_bound_does_not_assume_half_safe():
    from operations.x20_83063_subnormal_audit import upper_fraction
    assert upper_fraction([1.,2.,0.,0.],[-4.,0.,0.])==dict(numerator='1',denominator='4',float=.25)
